"""Offline credential regression tests; fixtures contain synthetic values only."""

import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "gui_app" / "prompt_gui" / "panels.py"
CLI_PATH = ROOT / "上线prompt" / "prompt_cli.py"


def load_config_methods(root):
    """Execute the real methods without importing Qt or model providers."""
    tree = ast.parse(PANEL_PATH.read_text(encoding="utf-8"))
    panel = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DeployPanel")
    methods = [node for node in panel.body if isinstance(node, ast.FunctionDef)
               and node.name in {"_save_config", "_load_config", "_default_api_key"}]
    namespace = {"os": os, "json": json, "re": re, "PROJECT_ROOT": str(root),
                 "__file__": str(root / "gui_app" / "prompt_gui" / "panels.py")}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(PANEL_PATH), "exec"), namespace)
    return type("ConfigMethods", (), {name: namespace[name] for name in
                                     ("_save_config", "_load_config", "_default_api_key")})


class TextField:
    def __init__(self, value=""):
        self.value = value

    def text(self):
        return self.value

    def setText(self, value):
        self.value = value


class GatewayGuiCredentialsTests(unittest.TestCase):
    def setUp(self):
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        self.root = Path(contexts.enter_context(tempfile.TemporaryDirectory()))
        contexts.enter_context(mock.patch.dict(os.environ, {}, clear=True))
        self.panel = load_config_methods(self.root)()
        self.panel.STORAGE_KEY = "streambridge_config"
        self.panel.base_url_edit = TextField("http://127.0.0.1:8080")
        self.panel.api_key_edit = TextField()
        self.panel.namespace_edit = TextField("default")
        self.messages = []
        self.panel._log = self.messages.append
        self.config_path = self.root / "gui_app" / ".deploy_config" / "streambridge_config.json"
        self.config_path.parent.mkdir(parents=True)
        (self.root / "gui_app" / "prompt_gui").mkdir()

    def write_config(self, config):
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def test_provider_credentials_are_never_automatically_used(self):
        for relative, content in (
            ("code/workflow/llm_key.py", 'api_key = "synthetic-provider-key"'),
            ("code/models/api_keys.py", 'OPENAI_API_KEY = "synthetic-other-provider-key"'),
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        os.environ["OPENAI_API_KEY"] = "synthetic-provider-env"
        self.assertEqual(self.panel._default_api_key(), "")

    def test_gateway_environment_key_takes_precedence_over_alias(self):
        os.environ.update(GATEWAY_API_KEY=" synthetic-gateway ", STREAMBRIDGE_API_KEY="synthetic-alias")
        self.assertEqual(self.panel._default_api_key(), "synthetic-gateway")

    def test_alias_environment_key_is_used_when_gateway_key_is_empty(self):
        os.environ.update(GATEWAY_API_KEY="  ", STREAMBRIDGE_API_KEY=" synthetic-alias ")
        self.assertEqual(self.panel._default_api_key(), "synthetic-alias")

    def test_save_keeps_connection_settings_without_key(self):
        self.panel.api_key_edit.setText("synthetic-entered-key")
        self.panel.namespace_edit.setText("example")
        self.panel._save_config()
        self.assertEqual(json.loads(self.config_path.read_text(encoding="utf-8")),
                         {"base_url": "http://127.0.0.1:8080", "namespace": "example"})
        self.assertEqual(self.panel.api_key_edit.text(), "synthetic-entered-key")

    def test_legacy_key_is_removed_without_losing_other_settings(self):
        original = {"base_url": "http://localhost:8081", "namespace": "example",
                    "custom_setting": {"enabled": True}, "api_key": "synthetic-legacy-key"}
        self.write_config(original)
        self.panel._load_config()
        self.assertEqual(self.panel.api_key_edit.text(), "")
        self.assertEqual(self.panel.base_url_edit.text(), original["base_url"])
        self.assertEqual(self.panel.namespace_edit.text(), "example")
        self.assertEqual(json.loads(self.config_path.read_text(encoding="utf-8")),
                         {key: value for key, value in original.items() if key != "api_key"})

    def test_environment_key_replaces_legacy_key(self):
        self.write_config({"api_key": "synthetic-legacy-key"})
        os.environ["GATEWAY_API_KEY"] = "synthetic-gateway"
        self.panel._load_config()
        self.assertEqual(self.panel.api_key_edit.text(), "synthetic-gateway")

    def test_failed_legacy_cleanup_warns_without_reusing_or_logging_key(self):
        self.write_config({"api_key": "synthetic-legacy-key", "namespace": "example"})
        real_open = open

        def deny_writes(path, mode="r", *args, **kwargs):
            if "w" in mode:
                raise PermissionError("synthetic-legacy-key")
            return real_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=deny_writes):
            self.panel._load_config()
        self.assertEqual(self.panel.api_key_edit.text(), "")
        self.assertEqual(self.panel.namespace_edit.text(), "example")
        self.assertTrue(self.messages)
        self.assertNotIn("synthetic-legacy-key", " ".join(self.messages))

    def test_invalid_json_uses_environment_key_without_logging_contents(self):
        self.config_path.write_text('{"api_key": "synthetic-broken-key"', encoding="utf-8")
        os.environ["GATEWAY_API_KEY"] = "synthetic-gateway"
        self.panel._load_config()
        self.assertEqual(self.panel.api_key_edit.text(), "synthetic-gateway")
        self.assertNotIn("synthetic-broken-key", " ".join(self.messages))


class GatewayCliCredentialsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("gateway_cli_credentials_under_test", CLI_PATH)
        cls.cli = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.cli
        spec.loader.exec_module(cls.cli)

    def setUp(self):
        environment = mock.patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def parse(self, flags=()):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                return self.cli.build_parser().parse_args([*flags, "template-list"])
            except SystemExit as exc:
                self.fail(f"Credential arguments should be optional at parse time (exit {exc.code})")

    def run_key(self, args):
        received = []
        args.handler = lambda cfg, parsed: received.append(cfg.api_key) or 0
        self.assertEqual(self.cli.run(args), 0)
        return received[0]

    def test_gateway_environment_allows_omitting_command_line_key(self):
        os.environ.update(GATEWAY_API_KEY=" synthetic-gateway ", STREAMBRIDGE_API_KEY="synthetic-alias")
        self.assertEqual(self.run_key(self.parse()), "synthetic-gateway")

    def test_alias_environment_allows_omitting_command_line_key(self):
        os.environ.update(GATEWAY_API_KEY="  ", STREAMBRIDGE_API_KEY=" synthetic-alias ")
        self.assertEqual(self.run_key(self.parse()), "synthetic-alias")

    def test_explicit_argument_overrides_environment(self):
        os.environ["GATEWAY_API_KEY"] = "synthetic-gateway"
        self.assertEqual(self.run_key(self.parse(["--api-key", "synthetic-explicit"])), "synthetic-explicit")

    def test_missing_key_reports_gateway_environment_options(self):
        os.environ["OPENAI_API_KEY"] = "synthetic-provider-env"
        args = self.parse()
        with self.assertRaises(self.cli.CliError) as error:
            self.cli.run(args)
        self.assertIn("GATEWAY_API_KEY", str(error.exception))
        self.assertIn("STREAMBRIDGE_API_KEY", str(error.exception))
        self.assertNotIn("synthetic-provider-env", str(error.exception))

    def test_explicit_empty_key_does_not_fall_back_to_environment(self):
        os.environ["GATEWAY_API_KEY"] = "synthetic-gateway"
        with self.assertRaises(self.cli.CliError):
            self.cli.run(self.parse(["--api-key", " "]))


if __name__ == "__main__":
    unittest.main()
