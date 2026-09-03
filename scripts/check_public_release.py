#!/usr/bin/env python3
"""Offline public-release checks. Findings contain locations, never matched values.

Default: tracked working files plus nonignored untracked files.
--staged: every index blob, including unchanged files.
--history: every reachable commit snapshot plus author/committer addresses.
Exit status: 0 clean, 1 findings requiring review, 2 scan could not complete.
This conservative pattern scan complements manual review; it cannot prove that
arbitrary prose, credentials in unknown formats, or encoded data are public-safe.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


PATTERNS = {
    "OPENAI_KEY": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}"),
    "GITHUB_TOKEN": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})"),
    "AWS_ACCESS_KEY_ID": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "PERSONAL_HOME_PATH": re.compile(r"(?i)(?:[a-z]:[\\/]+Users[\\/]+|/(?:Users|home)/)[^\s/\\\"'<>]+"),
}
CREDENTIAL_NAME = r"(?:[A-Za-z0-9]+_)*(?:api_?keys?|access_token|auth_token|password|passwd|secret|token)"
QUOTED_CREDENTIAL = re.compile(
    rf"(?i)\b(?P<name>{CREDENTIAL_NAME})[\"']?\s*[:=]\s*(?P<quote>[\"'])(?P<value>[^\"'\r\n]*)(?P=quote)"
)
BARE_CREDENTIAL = re.compile(
    rf"(?im)^\s*(?:export\s+|\$env:)?{CREDENTIAL_NAME}\s*[:=]\s*([A-Za-z0-9_./+=:@-]+)\s*(?:#.*)?$"
)
EMAIL = re.compile(r"(?i)(?<![\w.+-])[A-Z0-9._%+-]+@(?:[A-Z0-9-]+\.)+[A-Z]{2,}(?![\w.-])")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(value) for value in
                         ((0x0A000000, 8), (0xAC100000, 12), (0xC0A80000, 16)))
# Reviewed workflow metadata: these token fields are node types/references,
# not authentication tokens. Other values or paths remain subject to checks.
REVIEWED_WORKFLOW_TOKENS = {
    ("Virtual-Coach-main/code/workflow/nodes/between_set.py", "step"),
    *{("Virtual-Coach-main/code/workflow/" + path, "judge_report.token") for path in (
        "analysis/analysis_node_type_and_name_data.txt",
        "analysis/example/wf_setup_s03_inter.json",
        "define/node/unclass.md",
        "define/workflow/between_set.md",
        "example/wf_setup_s03_inter.json",
        "workflow_cli_skeleton/examples/wf_setup_s03_inter.json",
    )},
}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    commit: str = ""

    def render(self):
        location = f"{json.dumps(self.path, ensure_ascii=True)}:{self.line}"
        return f"{self.rule}\t{location}" + (f"\tcommit={self.commit[:12]}" if self.commit else "")


class ScanError(Exception):
    """Deliberately carries no command output or source content."""


def git(repo, *arguments, input_data=None):
    result = subprocess.run(["git", "-C", str(repo), *arguments], input=input_data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ScanError()
    return result.stdout


def is_placeholder(value):
    value = value.strip()
    lowered = value.lower()
    if not value or lowered in {"none", "null", "true", "false", "str", "string", "password", "token", "secret"}:
        return True
    if re.fullmatch(r"[xX*._-]+", value):
        return True
    if re.fullmatch(r"(?:[A-Z0-9]+_)*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|SECRET|TOKEN)", value):
        return True
    if re.fullmatch(r"(?:<[^>]+>|\$\{[^}]+\}|\{\{[^}]+\}\})", value):
        return True
    if re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", value):
        return True
    return bool(re.match(r"(?i)^(?:your|example|placeholder|replace[-_]?me|changeme|synthetic)(?:[-_ ]|$)", value))


def is_public_email(value):
    domain = value.rsplit("@", 1)[-1].lower()
    return (domain in {"example.com", "example.org", "example.net", "example.invalid", "example.test",
                       "noreply.github.com", "users.noreply.github.com"}
            or domain.endswith((".example.com", ".example.org", ".example.net")))


def path_rules(path):
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1]
    template = bool(re.search(r"(?:^|[._-])(?:example|template)(?:[._-]|$)", name))
    if not template and (name in {"api_keys.py", "llm_key.py", ".env"} or name.startswith(".env.")):
        yield "CREDENTIAL_FILE"
    if ".deploy_config" in parts:
        yield "DEPLOY_CONFIG"
    if any(part.startswith("workflow_log") for part in parts) and name.endswith((".json", ".jsonl")):
        yield "WORKFLOW_LOG"


def scan_content(path, data, commit=""):
    findings = [Finding(rule, path, 1, commit) for rule in path_rules(path)]
    try:
        if b"\0" in data:
            raise UnicodeError()
        text = data.decode("utf-8-sig")
    except UnicodeError:
        return findings + [Finding("BINARY_REVIEW", path, 0, commit)]
    for number, line in enumerate(text.splitlines(), 1):
        rules = {rule for rule, pattern in PATTERNS.items() if pattern.search(line)}
        if any(not is_placeholder(match["value"])
               and not (match["name"] == "token" and (path, match["value"]) in REVIEWED_WORKFLOW_TOKENS)
               for match in QUOTED_CREDENTIAL.finditer(line)):
            rules.add("LITERAL_CREDENTIAL")
        if not path.endswith(".py") and any(not is_placeholder(match.group(1))
                                           for match in BARE_CREDENTIAL.finditer(line)):
            rules.add("LITERAL_CREDENTIAL")
        if any(not is_public_email(match.group()) for match in EMAIL.finditer(line)):
            rules.add("PERSONAL_EMAIL")
        for match in IPV4.finditer(line):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            if any(address in network for network in PRIVATE_NETWORKS):
                rules.add("PRIVATE_IPV4")
        findings.extend(Finding(rule, path, number, commit) for rule in sorted(rules))
    return findings


def read_blobs(repo, hashes):
    """Read unique objects in one git process, honoring arbitrary binary sizes."""
    hashes = list(dict.fromkeys(hashes))
    if not hashes:
        return {}
    output = git(repo, "cat-file", "--batch", input_data=("\n".join(hashes) + "\n").encode("ascii"))
    blobs = {}
    offset = 0
    for expected in hashes:
        end = output.index(b"\n", offset)
        header = output[offset:end].split()
        if len(header) != 3 or header[0].decode("ascii") != expected or header[1] != b"blob":
            raise ScanError()
        size = int(header[2])
        offset = end + 1
        blobs[expected] = output[offset:offset + size]
        offset += size + 1
    return blobs


def scan_worktree(repo):
    raw = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    findings = []
    for encoded in sorted(set(raw.split(b"\0")) - {b""}):
        path = encoded.decode("utf-8", errors="surrogateescape")
        target = repo / path
        if target.is_symlink():
            findings.append(Finding("SYMLINK_REVIEW", path, 0))
        elif target.is_dir():
            findings.append(Finding("SUBMODULE_REVIEW", path, 0))
        else:
            try:
                data = target.read_bytes()
            except FileNotFoundError:
                continue  # A tracked file deleted from the working tree.
            except OSError:
                findings.append(Finding("UNREADABLE_FILE", path, 0))
                continue
            findings.extend(scan_content(path, data))
    return findings


def scan_snapshots(repo, snapshots):
    """Scan each distinct path/blob once; history output names its first snapshot."""
    findings = []
    seen = set()
    cached_blobs = {}
    for commit, raw in snapshots:
        entries = []
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            metadata, encoded = entry.split(b"\t", 1)
            mode, kind, blob = metadata.decode("ascii").split()
            path = encoded.decode("utf-8", errors="surrogateescape")
            if not commit:
                mode, blob, stage = mode, kind, blob
                kind = "blob"
                if stage != "0":
                    findings.append(Finding("INDEX_CONFLICT", path, 0))
            marker = (mode, blob, path)
            if marker in seen:
                continue
            seen.add(marker)
            if mode == "160000" or kind != "blob":
                findings.append(Finding("SUBMODULE_REVIEW", path, 0, commit))
            elif mode == "120000":
                findings.append(Finding("SYMLINK_REVIEW", path, 0, commit))
            else:
                entries.append((path, blob))
        cached_blobs.update(read_blobs(repo, [blob for _, blob in entries if blob not in cached_blobs]))
        for path, blob in entries:
            findings.extend(scan_content(path, cached_blobs[blob], commit))
    return findings


def scan_history(repo):
    identities = git(repo, "log", "--all", "--format=%H%x00%ae%x00%ce").splitlines()
    findings = []
    commits = []
    for identity in identities:
        commit, author, committer = identity.decode("utf-8", errors="replace").split("\0")
        commits.append(commit)
        for path, email in (("<author-email>", author), ("<committer-email>", committer)):
            if email and not is_public_email(email):
                findings.append(Finding("PERSONAL_EMAIL", path, 0, commit))
    snapshots = ((commit, git(repo, "ls-tree", "-rz", commit)) for commit in commits)
    return findings + scan_snapshots(repo, snapshots)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--staged", action="store_true", help="Scan the complete index")
    modes.add_argument("--history", action="store_true", help="Scan all reachable history and commit emails")
    args = parser.parse_args(argv)
    try:
        repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode("utf-8").strip())
        if args.history:
            findings = scan_history(repo)
        elif args.staged:
            findings = scan_snapshots(repo, [("", git(repo, "ls-files", "--stage", "-z"))])
        else:
            findings = scan_worktree(repo)
        for finding in sorted(set(findings), key=lambda item: (item.commit, item.path, item.line, item.rule)):
            print(finding.render())
        return 1 if findings else 0
    except (OSError, UnicodeError, ValueError, ScanError):
        print(Finding("SCAN_ERROR", ".", 0).render(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
