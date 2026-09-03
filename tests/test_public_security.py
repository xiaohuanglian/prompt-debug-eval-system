"""Offline regressions for public-release boundaries."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "Virtual-Coach-main" / "code"


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GeneratedModelTests(unittest.TestCase):
    def test_fresh_configuration_template_can_be_discovered(self):
        resolver = load_file("audit_template_resolver", CODE / "pipeline/model_resolver.py")
        with patch.object(resolver, "_get_api_keys_path", return_value=str(CODE / "models/api_keys_template.py")):
            self.assertEqual(resolver.list_available_models(), [])

    def test_generated_module_keeps_configuration_out_of_source(self):
        resolver = load_file("audit_model_resolver", CODE / "pipeline/model_resolver.py")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            models = root / "code/models"
            models.mkdir(parents=True)
            info = {"prefix": "DEMO", "module_name": "demo_adapter",
                    "api_key": "synthetic-credential-for-unit-test",
                    "url": "https://private-gateway.invalid/v1",
                    "model_name": "private-model-for-unit-test"}
            with patch.object(resolver, "_get_project_root", return_value=str(root)):
                resolver._ensure_model_file(info)
            path = models / "demo_adapter.py"
            source = path.read_text(encoding="utf-8")
            for key in ("api_key", "url", "model_name"):
                self.assertNotIn(info[key], source)
            module = load_file("audit_generated_adapter", path)
            module.configure(api_key=info["api_key"], base_url=info["url"], model=info["model_name"])
            self.assertEqual((module.API_KEY, module.BASE_URL, module.MODEL),
                             (info["api_key"], info["url"], info["model_name"]))

    def test_generated_module_loads_standalone_environment(self):
        resolver = load_file("audit_env_resolver", CODE / "pipeline/model_resolver.py")
        source = resolver._META_LLM_API_TEMPLATE.format(prefix="DEMO", model="unused", url="unused")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "adapter.py"
            path.write_text(source, encoding="utf-8")
            with patch.dict(os.environ, {"DEMO_API_KEY": "synthetic-env-key",
                                         "DEMO_URL": "https://example.com/v1/chat/completions",
                                         "DEMO_MODEL": "example-model"}, clear=True):
                module = load_file("audit_env_adapter", path)
                module.configure()
                self.assertEqual(module.BASE_URL, "https://example.com/v1")
                self.assertEqual(module.MODEL, "example-model")


class WorkflowBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        cls.TestClient = TestClient
        cls.server = load_file("audit_workflow_server", CODE / "workflow/server.py")

    def client(self, address="127.0.0.1"):
        return self.TestClient(self.server.app, base_url="http://localhost:8000",
                               client=(address, 50000))

    def test_foreign_origin_rejected_before_spawn(self):
        with patch.object(self.server.asyncio, "create_subprocess_exec") as spawn:
            response = self.client().post("/api/start", json={"demand": "example"},
                                          headers={"Origin": "https://untrusted.invalid"})
            self.assertEqual(response.status_code, 403)
            spawn.assert_not_called()

    def test_remote_client_cannot_read_logs(self):
        response = self.client("203.0.113.1").get("/api/stream/missing")
        self.assertEqual(response.status_code, 403)

    def test_null_origin_and_rebound_host_are_rejected(self):
        self.assertEqual(self.client().get("/", headers={"Origin": "null"}).status_code, 403)
        self.assertEqual(self.client().get("/", headers={"Host": "attacker.invalid"}).status_code, 400)

    def test_local_start_preserves_workflow_and_returns_only_log_filename(self):
        proc = MagicMock()
        with patch.object(self.server.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=proc)) as spawn:
            with patch.object(self.server, "_read_kv_from_stdout", new=AsyncMock(side_effect=["demo-run", "workflow_log_demo.jsonl"])):
                response = self.client().post("/api/start", json={"demand": "example",
                    "example_path": "example/wf_setup_s03_inter.json"},
                    headers={"Origin": "http://localhost:8000"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"run_id": "demo-run", "log_path": "workflow_log_demo.jsonl"})
        self.assertEqual(spawn.call_args.args[0], sys.executable)
        self.assertTrue(Path(self.server.RUNS.pop("demo-run")["log_path"]).is_absolute())

    def test_same_origin_ui_available(self):
        response = self.client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_arbitrary_local_file_rejected_before_spawn(self):
        with patch.object(self.server.asyncio, "create_subprocess_exec") as spawn:
            response = self.client().post("/api/start", json={
                "demand": "example", "example_path": "../models/api_keys.py"})
            self.assertEqual(response.status_code, 400)
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
