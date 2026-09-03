\
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .schema import WorkflowFile, WorkflowBody, NodeConfig

@dataclass
class ValidationIssue:
    level: str  # "error" or "warn"
    code: str
    message: str
    json_path: str

_INPUT_REF_RE = re.compile(r"^(?P<node>[A-Za-z0-9_\-]+)\.(?P<field>[A-Za-z0-9_\-]+)$")

def validate_workflow_file(obj: Dict[str, Any], allow_terminal: Optional[Set[str]] = None) -> Tuple[WorkflowFile, List[ValidationIssue]]:
    issues: List[ValidationIssue] = []
    allow_terminal = allow_terminal or {"finish"}
    wf = WorkflowFile.model_validate(obj)
    for wf_name, body in wf.root.items():
        issues.extend(_validate_workflow_body(wf_name, body, allow_terminal))
    return wf, issues

def _validate_workflow_body(wf_name: str, body: WorkflowBody, allow_terminal: Set[str]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    nodes = body.nodes
    name_to_node: Dict[str, NodeConfig] = {}
    ids: Set[int] = set()

    for idx, n in enumerate(nodes):
        p = f"$.{wf_name}.nodes[{idx}]"
        if n.id in ids:
            issues.append(ValidationIssue("error", "DUPLICATE_NODE_ID", f"node id duplicated: {n.id}", p + ".id"))
        ids.add(n.id)
        if n.node_name in name_to_node:
            issues.append(ValidationIssue("error", "DUPLICATE_NODE_NAME", f"node_name duplicated: {n.node_name}", p + ".node_name"))
        else:
            name_to_node[n.node_name] = n

    if body.start_node not in name_to_node:
        issues.append(ValidationIssue("error", "MISSING_START_NODE",
                                      f"start_node '{body.start_node}' not found in nodes",
                                      f"$.{wf_name}.start_node"))

    for idx, n in enumerate(nodes):
        for branch, nxt in (n.choice_map or {}).items():
            if nxt in allow_terminal:
                continue
            if nxt not in name_to_node:
                issues.append(ValidationIssue("error", "INVALID_CHOICE_TARGET",
                                              f"choice_map '{branch}' -> unknown node '{nxt}' (allowed terminals: {sorted(allow_terminal)})",
                                              f"$.{wf_name}.nodes[{idx}].choice_map.{branch}"))

    for idx, n in enumerate(nodes):
        for k, v in (n.input_map or {}).items():
            if v is None or v == "":
                continue
            m = _INPUT_REF_RE.match(str(v))
            if not m:
                issues.append(ValidationIssue("error", "INVALID_INPUT_REF",
                                              f"input_map '{k}' invalid ref '{v}', expected 'node.output'",
                                              f"$.{wf_name}.nodes[{idx}].input_map.{k}"))
                continue
            src = m.group("node")
            if src not in name_to_node:
                issues.append(ValidationIssue("error", "UNKNOWN_INPUT_SOURCE",
                                              f"input_map '{k}' references unknown node '{src}'",
                                              f"$.{wf_name}.nodes[{idx}].input_map.{k}"))

    if not nodes:
        issues.append(ValidationIssue("warn", "EMPTY_NODES", "workflow has no nodes", f"$.{wf_name}.nodes"))
    return issues
