"""Public-release scanner tests using isolated repositories and synthetic data."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCANNER = Path(__file__).resolve().parents[1] / "scripts" / "check_public_release.py"


class ReleaseScannerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.environment = os.environ.copy()
        for name in list(self.environment):
            if name.startswith("GIT_"):
                del self.environment[name]
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q")
        self.git("config", "user.name", "Release Scanner Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.fixture_value = "sk" + "-" + "F" * 40

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.repo, env=self.environment,
                              check=True, capture_output=True).stdout

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def scan(self, *arguments):
        self.assertTrue(SCANNER.is_file(), "Release scanner must exist")
        return subprocess.run([sys.executable, str(SCANNER), *arguments], cwd=self.repo,
                              env=self.environment, capture_output=True, text=True)

    def assert_finding(self, result, rule, path, sensitive=()):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(rule, result.stdout)
        self.assertIn(path, result.stdout)
        for value in sensitive:
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_untracked_content_is_scanned_and_values_never_printed(self):
        self.write("draft.txt", "safe first line\n" + self.fixture_value + "\n")
        self.assert_finding(self.scan(), "OPENAI_KEY", "draft.txt", [self.fixture_value])
        self.assertIn(":2", self.scan().stdout)

    def test_tracked_files_are_scanned_even_when_ignored(self):
        self.write("tracked.txt", self.fixture_value)
        self.git("add", "tracked.txt")
        self.write(".gitignore", "tracked.txt\nignored.txt\n")
        self.write("ignored.txt", self.fixture_value)
        result = self.scan()
        self.assert_finding(result, "OPENAI_KEY", "tracked.txt", [self.fixture_value])
        self.assertNotIn('"ignored.txt"', result.stdout)

    def test_staged_scan_reads_complete_index_not_working_tree_or_diff(self):
        self.write("committed.txt", self.fixture_value)
        self.git("add", "committed.txt")
        self.git("commit", "-qm", "Fixture initial snapshot")
        self.write("committed.txt", "safe working copy")
        self.write("new.txt", "safe addition")
        self.git("add", "new.txt")
        self.assert_finding(self.scan("--staged"), "OPENAI_KEY", "committed.txt", [self.fixture_value])
        self.assertEqual(self.scan().returncode, 0)

    def test_staged_secret_is_found_after_working_copy_is_replaced(self):
        self.write("staged.txt", self.fixture_value)
        self.git("add", "staged.txt")
        self.write("staged.txt", "safe replacement")
        self.assert_finding(self.scan("--staged"), "OPENAI_KEY", "staged.txt", [self.fixture_value])

    def test_history_finds_deleted_content(self):
        self.write("removed.txt", self.fixture_value)
        self.git("add", "removed.txt")
        self.git("commit", "-qm", "Fixture with removed content")
        self.git("rm", "-q", "removed.txt")
        self.git("commit", "-qm", "Remove fixture")
        result = self.scan("--history")
        self.assert_finding(result, "OPENAI_KEY", "removed.txt", [self.fixture_value])
        self.assertRegex(result.stdout, r"commit=[0-9a-f]{12}")
        self.assertEqual(self.scan().returncode, 0)

    def test_history_checks_author_and_committer_emails(self):
        author = "fixture-author" + "@" + "mailhost.invalid"
        committer = "fixture-committer" + "@" + "mailhost.invalid"
        self.environment.update(GIT_AUTHOR_EMAIL=author, GIT_COMMITTER_EMAIL=committer)
        self.git("commit", "--allow-empty", "-qm", "Fixture identity")
        result = self.scan("--history")
        self.assert_finding(result, "PERSONAL_EMAIL", "<author-email>", [author, committer])
        self.assertIn("<committer-email>", result.stdout)

    def test_history_includes_other_reachable_branches(self):
        self.git("commit", "--allow-empty", "-qm", "Base fixture")
        initial = self.git("rev-parse", "HEAD").decode().strip()
        self.git("checkout", "-qb", "fixture-history")
        self.write("branch.txt", self.fixture_value)
        self.git("add", "branch.txt")
        self.git("commit", "-qm", "Other branch fixture")
        self.git("checkout", "-q", "--detach", initial)
        self.assert_finding(self.scan("--history"), "OPENAI_KEY", "branch.txt", [self.fixture_value])

    def test_common_key_formats_are_detected(self):
        cases = (("GITHUB_TOKEN", "gh" + "p_" + "A" * 36),
                 ("GITHUB_TOKEN", "github" + "_pat_" + "B" * 50),
                 ("AWS_ACCESS_KEY_ID", "AK" + "IA" + "C" * 16),
                 ("PRIVATE_KEY", "-----BEGIN " + "RSA PRIVATE KEY-----"))
        for rule, value in cases:
            with self.subTest(rule=rule):
                self.write("candidate.txt", value)
                self.assert_finding(self.scan(), rule, "candidate.txt", [value])

    def test_literal_credentials_are_detected_without_known_key_format(self):
        value = "fixture" + "Credential987654"
        for text in ('api_key = "' + value + '"', '{"password": "' + value + '"}',
                     "GATEWAY_API_KEY=" + value):
            with self.subTest(syntax=text[:12]):
                self.write("settings.txt", text)
                self.assert_finding(self.scan(), "LITERAL_CREDENTIAL", "settings.txt", [value])

    def test_personal_home_paths_are_detected(self):
        for home in ("C:" + "\\Users\\" + "fixture-user\\project",
                     "/" + "Users/" + "fixture-user/project",
                     "/" + "home/" + "fixture-user/project"):
            with self.subTest(style=home[:2]):
                self.write("notes.txt", home)
                self.assert_finding(self.scan(), "PERSONAL_HOME_PATH", "notes.txt", [home])

    def test_private_ipv4_addresses_are_detected_but_loopback_is_allowed(self):
        for address in ("10." + "23.45.67", "172." + "16.42.8", "192." + "168.42.8"):
            self.write("network.txt", address)
            self.assert_finding(self.scan(), "PRIVATE_IPV4", "network.txt", [address])
        self.write("network.txt", "http://127.0.0.1:8080\n0.0.0.0\n203.0.113.1")
        self.assertEqual(self.scan().returncode, 0)

    def test_email_detection_allows_examples_and_github_noreply(self):
        value = "fixture-person" + "@" + "mailhost.invalid"
        self.write("contacts.txt", value)
        self.assert_finding(self.scan(), "PERSONAL_EMAIL", "contacts.txt", [value])
        self.write("contacts.txt", "demo@example.com\ndemo@example.invalid\n123+demo@users.noreply.github.com")
        self.assertEqual(self.scan().returncode, 0)

    def test_sensitive_file_names_are_detected_even_if_empty(self):
        cases = (("CREDENTIAL_FILE", "models/api_keys.py"),
                 ("CREDENTIAL_FILE", "workflow/llm_key.py"),
                 ("CREDENTIAL_FILE", ".env"),
                 ("CREDENTIAL_FILE", ".env.local"),
                 ("DEPLOY_CONFIG", "gui_app/.deploy_config/settings.json"),
                 ("WORKFLOW_LOG", "workflow_log/run.jsonl"))
        for rule, path in cases:
            self.write(path, "")
        result = self.scan()
        for rule, path in cases:
            self.assert_finding(result, rule, path)

    def test_placeholder_templates_are_allowed_but_contents_still_checked(self):
        for path in ("models/api_keys.example.py", "workflow/llm_key.template.py", ".env.example"):
            self.write(path, 'API_KEY="YOUR_API_KEY"\nPASSWORD=""\nTOKEN="<your-token>"')
        self.assertEqual(self.scan().returncode, 0)
        self.write(".env.example", self.fixture_value)
        self.assert_finding(self.scan(), "OPENAI_KEY", ".env.example", [self.fixture_value])

    def test_test_directories_are_not_exempt(self):
        self.write("tests/fixture.py", self.fixture_value)
        self.assert_finding(self.scan(), "OPENAI_KEY", "tests/fixture.py", [self.fixture_value])

    def test_binary_content_requires_review(self):
        (self.repo / "unknown.bin").write_bytes(b"\x00\xff\x01")
        self.assert_finding(self.scan(), "BINARY_REVIEW", "unknown.bin")

    def test_clean_repository_and_empty_history_pass(self):
        self.write("README.md", "Public release fixture\n")
        self.assertEqual(self.scan().returncode, 0)
        self.assertEqual(self.scan("--staged").returncode, 0)
        self.assertEqual(self.scan("--history").returncode, 0)

    def test_scanner_and_its_tests_do_not_need_a_path_exemption(self):
        self.write("scanner.py", SCANNER.read_text(encoding="utf-8"))
        self.write("tests/test_scanner.py", Path(__file__).read_text(encoding="utf-8"))
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_credential_name_placeholders_are_allowed(self):
        self.write("template.txt", 'api_key="API_KEY"\napi_key="ZHIPU_API_KEY"')
        result = self.scan()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_python_variable_references_are_not_literal_credentials(self):
        self.write("settings.py", "API_KEY = provider_credential_variable\n")
        self.assertEqual(self.scan().returncode, 0)
        self.write("settings.py", 'API_KEY = "' + "fixtureCredential987654" + '"')
        self.assert_finding(self.scan(), "LITERAL_CREDENTIAL", "settings.py")

    def test_single_format_placeholder_is_allowed_but_embedded_values_are_not(self):
        field = "api_" + "key"
        self.write("template.txt", field + '="{model_api_key}"')
        self.assertEqual(self.scan().returncode, 0)
        self.write("template.txt", field + '="embedded{model_api_key}value"')
        self.assert_finding(self.scan(), "LITERAL_CREDENTIAL", "template.txt")

    def test_reviewed_workflow_metadata_exception_is_narrow(self):
        path = "Virtual-Coach-main/code/workflow/nodes/between_set.py"
        field = "to" + "ken"
        safe_line = field + ' = "' + "step" + '"'
        self.write(path, safe_line)
        self.assertEqual(self.scan().returncode, 0)
        self.write("unreviewed.py", safe_line)
        self.assert_finding(self.scan(), "LITERAL_CREDENTIAL", "unreviewed.py")
        (self.repo / "unreviewed.py").unlink()
        self.write(path, 'api_' + 'key = "' + "step" + '"')
        self.assert_finding(self.scan(), "LITERAL_CREDENTIAL", path)


if __name__ == "__main__":
    unittest.main()
