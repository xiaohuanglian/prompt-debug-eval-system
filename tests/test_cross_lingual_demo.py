"""Offline checks for the public cross-language example."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "cross_lingual_test" / "cross_lingual_test.py"


class CrossLingualDemoTests(unittest.TestCase):
    def run_offline(self, body, extra_env=None):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CROSS_LINGUAL_") and not k.endswith("_API_KEY")}
        env["PYTHONIOENCODING"] = "utf-8"
        env.update(extra_env or {})
        guard = """
import sys, runpy, json
def guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise AssertionError('Network is forbidden in offline tests')
    if event == 'import' and (args[0] == 'openai' or args[0].startswith('code.models')):
        raise AssertionError('Offline execution must not import a model provider')
sys.addaudithook(guard)
"""
        return subprocess.run(
            [sys.executable, "-S", "-c", guard + body, str(SCRIPT)],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=15,
        )

    def test_prompt_includes_context_and_target_language(self):
        result = self.run_offline("""
demo = runpy.run_path(sys.argv[1])
first = {'output_language': '中文', 'topic': 'Borrowing books',
         'facts': ['Bring a library card', 'Return books in fourteen days']}
second = {'output_language': '中文', 'topic': 'Finding books',
          'facts': ['Search the catalog', 'Use the shelf number']}
english = dict(first, output_language='English')
print(json.dumps([demo['build_prompt'](value) for value in (first, second, english)]))
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        first, second, english = json.loads(result.stdout)
        self.assertIn("Borrowing books", first)
        self.assertIn("Return books in fourteen days", first)
        self.assertIn("中文", first)
        self.assertIn("Finding books", second)
        self.assertIn("Use the shelf number", second)
        self.assertIn("English", english)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, english)

    def test_dry_run_needs_no_credentials_sdk_or_network(self):
        result = self.run_offline("""
script = sys.argv[1]
sys.argv = [script, '--dry-run', '--single', '0']
runpy.run_path(script, run_name='__main__')
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("synthetic", result.stdout.lower())
        self.assertIn("Borrowing books", result.stdout)
        self.assertIn("中文", result.stdout)
        self.assertIn("English", result.stdout)
        self.assertIn("intro_text", result.stdout)

    def test_openai_key_is_not_used_for_an_explicit_third_party_endpoint(self):
        result = self.run_offline("""
script = sys.argv[1]
sys.argv = [script, '--model', 'demo-model', '--base-url', 'https://provider.example/v1']
runpy.run_path(script, run_name='__main__')
""", {"OPENAI_API_KEY": "synthetic-unused-secret"})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("CROSS_LINGUAL_API_KEY", result.stderr)
        self.assertNotIn("synthetic-unused-secret", result.stderr + result.stdout)
        self.assertNotIn("Offline execution must not import", result.stderr)

    def test_single_index_is_validated_before_loading_a_provider(self):
        result = self.run_offline("""
script = sys.argv[1]
sys.argv = [script, '--dry-run', '--single', '-1']
runpy.run_path(script, run_name='__main__')
""")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--single", result.stderr)

    def test_configured_run_writes_paired_outputs_using_only_explicit_settings(self):
        result = self.run_offline("""
from pathlib import Path
from types import SimpleNamespace
import tempfile
demo = runpy.run_path(sys.argv[1])
requests = []
clients = []
class OfflineClient:
    def __init__(self, **config):
        assert config['api_key'] == 'synthetic-provider-key'
        assert config['base_url'] == 'https://provider.example/v1'
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.closed = False
        clients.append(self)
    def create(self, **request):
        requests.append(request)
        assert request['model'] == 'selected-demo-model'
        prompt = request['messages'][0]['content']
        text = '图书借阅简介' if 'Output language: 中文' in prompt else 'A guide to borrowing books'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps({'intro_text': text})))])
    def close(self):
        self.closed = True
sys.modules['openai'] = SimpleNamespace(OpenAI=OfflineClient)
with tempfile.TemporaryDirectory() as directory:
    demo['main'].__globals__['OUTPUT_DIR'] = Path(directory)
    status = demo['main'](['--single', '0', '--model', 'selected-demo-model',
                          '--base-url', 'https://provider.example/v1'])
    assert status == 0
    assert clients[0].closed
    assert len(requests) == 2
    reports = list(Path(directory).glob('*.json'))
    assert len(reports) == 1
    print(json.dumps(json.loads(reports[0].read_text(encoding='utf-8'))))
""", {"CROSS_LINGUAL_API_KEY": "synthetic-provider-key",
       "OPENAI_API_KEY": "synthetic-unused-secret"})
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report["model"], "selected-demo-model")
        case = report["per_case"][0]
        self.assertTrue(case["zh"]["success"])
        self.assertTrue(case["en"]["success"])
        self.assertEqual(case["zh"]["output"]["intro_text"], "图书借阅简介")
        self.assertIn("borrowing books", case["en"]["output"]["intro_text"])
        self.assertNotIn("synthetic-provider-key", result.stdout)
        self.assertNotIn("synthetic-unused-secret", result.stdout)


if __name__ == "__main__":
    unittest.main()
