#!/usr/bin/env python3
"""LLM Gateway 上下文、模板与 LLM 接口 CLI。

通过 HTTP 调用 LLM Gateway 已配置的上下文/模板/LLM 路由。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_BASE_URL = os.getenv("GATEWAY_BASE_URL") or os.getenv("STREAMBRIDGE_BASE_URL", "http://127.0.0.1:8080")


@dataclass(frozen=True)
class ClientConfig:
    """CLI 运行配置。"""

    base_url: str
    api_key: str
    timeout: float


class CliError(Exception):
    """CLI 业务异常。"""


def _read_text_file(path: str, arg_name: str) -> str:
    """读取 UTF-8 文本文件。"""
    file_path = Path(path).expanduser()
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CliError(f"参数错误：{arg_name} 指向的文件不存在: {path}") from exc
    except IsADirectoryError as exc:
        raise CliError(f"参数错误：{arg_name} 不能是目录: {path}") from exc
    except OSError as exc:
        raise CliError(f"读取文件失败（{arg_name}）: {path}，原因: {exc}") from exc


def _parse_kv_pairs(items: list[str]) -> dict[str, str]:
    """解析 k=v 形式参数。"""
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise CliError(f"参数错误：无效键值对 {item!r}，需要 k=v 格式")
        key, value = item.split("=", 1)
        k = key.strip()
        if not k:
            raise CliError(f"参数错误：无效键值对 {item!r}，key 不能为空")
        parsed[k] = value
    return parsed


def _build_chat_options(args: argparse.Namespace) -> dict[str, Any]:
    """构建 LLM ChatOptions。"""
    options: dict[str, Any] = {}
    if args.temperature is not None:
        options["temperature"] = args.temperature
    if args.max_tokens is not None:
        options["max_tokens"] = args.max_tokens
    if args.top_p is not None:
        options["top_p"] = args.top_p
    if args.stop:
        options["stop"] = args.stop
    if args.extra:
        options["extra"] = _parse_kv_pairs(args.extra)
    return options


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise CliError("参数错误：--base-url 不能为空")
    return normalized


def _post_json(
    cfg: ClientConfig,
    path: str,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=f"{cfg.base_url}{path}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
    )

    try:
        with request.urlopen(req, timeout=cfg.timeout) as resp:
            raw = resp.read()
            status = int(resp.status)
    except error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw.decode("utf-8", errors="replace")}
        return int(exc.code), data
    except error.URLError as exc:
        raise CliError(f"请求失败：{exc.reason}") from exc

    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw.decode("utf-8", errors="replace")}

    return status, parsed


def _print_result(status: int, data: dict[str, Any]) -> int:
    print(f"HTTP {status}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if 200 <= status < 300:
        return 0
    return 1


def _run_context_get(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {
        "namespace": args.namespace,
        "field": args.field,
        "use_hook": args.use_hook,
        "timeout_ms": args.timeout_ms,
    }
    status, data = _post_json(cfg, "/api/v1/context/get", payload)
    return _print_result(status, data)


def _run_context_set(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "namespace": args.namespace,
        "field": args.field,
        "value": args.value,
    }
    if args.alias:
        payload["alias"] = args.alias
    status, data = _post_json(cfg, "/api/v1/context/set", payload)
    return _print_result(status, data)


def _run_alias_bind(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {
        "alias": args.alias,
        "namespace": args.namespace,
        "field": args.field,
        "lifecycle_scope": args.lifecycle_scope,
    }
    status, data = _post_json(cfg, "/api/v1/context/alias/bind", payload)
    return _print_result(status, data)


def _run_alias_cleanup(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {"aliases": args.aliases}
    status, data = _post_json(cfg, "/api/v1/context/alias/cleanup", payload)
    return _print_result(status, data)


def _run_template_validate(cfg: ClientConfig, args: argparse.Namespace) -> int:
    template_content = args.template_content
    if args.template_file:
        template_content = _read_text_file(args.template_file, "--template-file")
    payload = {
        "template_content": template_content,
        "expected_vars": args.expected_vars,
    }
    status, data = _post_json(cfg, "/api/v1/template/validate", payload)
    return _print_result(status, data)


def _run_template_info(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {"template_id": args.template_id}
    status, data = _post_json(cfg, "/api/v1/template/info", payload)
    return _print_result(status, data)


def _run_template_create(cfg: ClientConfig, args: argparse.Namespace) -> int:
    content = args.content
    if args.content_file:
        content = _read_text_file(args.content_file, "--content-file")
    payload = {
        "namespace": args.namespace,
        "name": args.name,
        "content": content,
        "description": args.description,
        "is_active": args.is_active,
    }
    status, data = _post_json(cfg, "/api/v1/template/create", payload)
    return _print_result(status, data)


def _run_template_get(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {
        "namespace": args.namespace,
        "template_id": args.template_id,
        "version": args.version,
    }
    status, data = _post_json(cfg, "/api/v1/template/get", payload)
    return _print_result(status, data)


def _run_template_update(cfg: ClientConfig, args: argparse.Namespace) -> int:
    content = args.content
    if args.content_file:
        content = _read_text_file(args.content_file, "--content-file")
    if content is None:
        content = ""
    payload = {
        "namespace": args.namespace,
        "template_id": args.template_id,
        "name": args.name,
        "content": content,
        "description": args.description,
        "is_active": args.is_active,
        "is_active_set": args.is_active_set,
    }
    status, data = _post_json(cfg, "/api/v1/template/update", payload)
    return _print_result(status, data)


def _run_template_delete(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {
        "namespace": args.namespace,
        "template_id": args.template_id,
    }
    status, data = _post_json(cfg, "/api/v1/template/delete", payload)
    return _print_result(status, data)


def _run_template_list(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload = {
        "namespace": args.namespace,
        "page_size": args.page_size,
        "page_token": args.page_token,
    }
    status, data = _post_json(cfg, "/api/v1/template/list", payload)
    return _print_result(status, data)


def _run_llm_chat(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "prompt": args.prompt,
        "model": args.model,
    }
    options = _build_chat_options(args)
    if options:
        payload["options"] = options
    status, data = _post_json(cfg, "/api/v1/llm/chat", payload)
    return _print_result(status, data)


def _run_llm_chat_stream(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "prompt": args.prompt,
        "model": args.model,
    }
    options = _build_chat_options(args)
    if options:
        payload["options"] = options
    status, data = _post_json(cfg, "/api/v1/llm/chat/stream", payload)
    return _print_result(status, data)


def _run_llm_build_and_chat(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "user_id": args.user_id,
        "template_id": args.template_id,
        "params": _parse_kv_pairs(args.params),
        "model": args.model,
    }
    options = _build_chat_options(args)
    if options:
        payload["options"] = options
    status, data = _post_json(cfg, "/api/v1/llm/build-and-chat", payload)
    return _print_result(status, data)


def _run_llm_build_and_chat_stream(cfg: ClientConfig, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "user_id": args.user_id,
        "template_id": args.template_id,
        "params": _parse_kv_pairs(args.params),
        "model": args.model,
    }
    options = _build_chat_options(args)
    if options:
        payload["options"] = options
    status, data = _post_json(cfg, "/api/v1/llm/build-and-chat/stream", payload)
    return _print_result(status, data)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""
    parser = argparse.ArgumentParser(description="LLM Gateway 上下文、模板与 LLM CLI")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"网关地址（默认: {DEFAULT_BASE_URL}）",
    )
    parser.add_argument("--api-key", required=True, help="API Key（将放入 Bearer 头）")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP 超时秒数（默认: 10）")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_context_get = subparsers.add_parser("context-get", help="获取上下文")
    p_context_get.add_argument("--namespace", required=True, help="命名空间")
    p_context_get.add_argument("--field", required=True, help="字段名")
    p_context_get.add_argument("--use-hook", action="store_true", help="允许 hook 取数")
    p_context_get.add_argument("--timeout-ms", type=int, default=0, help="hook 超时毫秒")
    p_context_get.set_defaults(handler=_run_context_get)

    p_context_set = subparsers.add_parser("context-set", help="设置上下文")
    p_context_set.add_argument("--namespace", required=True, help="命名空间")
    p_context_set.add_argument("--field", required=True, help="字段名")
    p_context_set.add_argument("--value", required=True, help="字段值")
    p_context_set.add_argument("--alias", default="", help="可选别名")
    p_context_set.set_defaults(handler=_run_context_set)

    p_alias_bind = subparsers.add_parser("alias-bind", help="绑定别名")
    p_alias_bind.add_argument("--alias", required=True, help="别名")
    p_alias_bind.add_argument("--namespace", required=True, help="命名空间")
    p_alias_bind.add_argument("--field", required=True, help="字段名")
    p_alias_bind.add_argument(
        "--lifecycle-scope",
        default="session",
        help="生命周期范围（默认: session）",
    )
    p_alias_bind.set_defaults(handler=_run_alias_bind)

    p_alias_cleanup = subparsers.add_parser("alias-cleanup", help="按别名清理")
    p_alias_cleanup.add_argument(
        "--aliases",
        nargs="+",
        required=True,
        help="别名列表，如 alias_a alias_b",
    )
    p_alias_cleanup.set_defaults(handler=_run_alias_cleanup)

    p_template_validate = subparsers.add_parser("template-validate", help="验证模板语法")
    g_template_validate_content = p_template_validate.add_mutually_exclusive_group(required=True)
    g_template_validate_content.add_argument("--template-content", help="模板内容")
    g_template_validate_content.add_argument(
        "--template-file",
        help="模板文件路径（UTF-8）",
    )
    p_template_validate.add_argument(
        "--expected-vars",
        nargs="*",
        default=[],
        help="期望变量列表",
    )
    p_template_validate.set_defaults(handler=_run_template_validate)

    p_template_info = subparsers.add_parser("template-info", help="查询模板信息")
    p_template_info.add_argument("--template-id", required=True, help="模板 ID")
    p_template_info.set_defaults(handler=_run_template_info)

    p_template_create = subparsers.add_parser("template-create", help="创建模板")
    p_template_create.add_argument("--namespace", default="default", help="命名空间")
    p_template_create.add_argument("--name", required=True, help="模板名")
    g_template_create_content = p_template_create.add_mutually_exclusive_group(required=True)
    g_template_create_content.add_argument("--content", help="模板内容")
    g_template_create_content.add_argument(
        "--content-file",
        help="模板文件路径（UTF-8）",
    )
    p_template_create.add_argument("--description", default="", help="描述")
    p_template_create.add_argument(
        "--is-active",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否激活（默认: true）",
    )
    p_template_create.set_defaults(handler=_run_template_create)

    p_template_get = subparsers.add_parser("template-get", help="查询模板")
    p_template_get.add_argument("--namespace", default="default", help="命名空间")
    p_template_get.add_argument("--template-id", required=True, help="模板 ID")
    p_template_get.add_argument("--version", default="", help="版本")
    p_template_get.set_defaults(handler=_run_template_get)

    p_template_update = subparsers.add_parser("template-update", help="更新模板")
    p_template_update.add_argument("--namespace", default="default", help="命名空间")
    p_template_update.add_argument("--template-id", required=True, help="模板 ID")
    p_template_update.add_argument("--name", default="", help="新模板名")
    g_template_update_content = p_template_update.add_mutually_exclusive_group(required=False)
    g_template_update_content.add_argument("--content", default=None, help="新模板内容")
    g_template_update_content.add_argument(
        "--content-file",
        default="",
        help="新模板文件路径（UTF-8）",
    )
    p_template_update.add_argument("--description", default="", help="新描述")
    p_template_update.add_argument(
        "--is-active",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="激活状态值",
    )
    p_template_update.add_argument(
        "--is-active-set",
        action="store_true",
        help="显式设置 is_active（不传表示不更新激活状态）",
    )
    p_template_update.set_defaults(handler=_run_template_update)

    p_template_delete = subparsers.add_parser("template-delete", help="删除模板")
    p_template_delete.add_argument("--namespace", default="default", help="命名空间")
    p_template_delete.add_argument("--template-id", required=True, help="模板 ID")
    p_template_delete.set_defaults(handler=_run_template_delete)

    p_template_list = subparsers.add_parser("template-list", help="分页查询模板")
    p_template_list.add_argument("--namespace", default="default", help="命名空间")
    p_template_list.add_argument("--page-size", type=int, default=20, help="每页数量")
    p_template_list.add_argument("--page-token", default="", help="分页游标")
    p_template_list.set_defaults(handler=_run_template_list)

    p_llm_chat = subparsers.add_parser("llm-chat", help="调用 LLM Chat")
    p_llm_chat.add_argument("--prompt", required=True, help="Prompt 内容")
    p_llm_chat.add_argument("--model", default="", help="模型名，空则走服务默认")
    p_llm_chat.add_argument("--temperature", type=float, default=None, help="采样温度")
    p_llm_chat.add_argument("--max-tokens", type=int, default=None, help="最大输出 token")
    p_llm_chat.add_argument("--top-p", type=float, default=None, help="top_p 参数")
    p_llm_chat.add_argument("--stop", nargs="*", default=[], help="停止词列表")
    p_llm_chat.add_argument("--extra", nargs="*", default=[], help="扩展参数，格式 k=v")
    p_llm_chat.set_defaults(handler=_run_llm_chat)

    p_llm_chat_stream = subparsers.add_parser("llm-chat-stream", help="调用 LLM ChatStream")
    p_llm_chat_stream.add_argument("--prompt", required=True, help="Prompt 内容")
    p_llm_chat_stream.add_argument("--model", default="", help="模型名，空则走服务默认")
    p_llm_chat_stream.add_argument("--temperature", type=float, default=None, help="采样温度")
    p_llm_chat_stream.add_argument("--max-tokens", type=int, default=None, help="最大输出 token")
    p_llm_chat_stream.add_argument("--top-p", type=float, default=None, help="top_p 参数")
    p_llm_chat_stream.add_argument("--stop", nargs="*", default=[], help="停止词列表")
    p_llm_chat_stream.add_argument("--extra", nargs="*", default=[], help="扩展参数，格式 k=v")
    p_llm_chat_stream.set_defaults(handler=_run_llm_chat_stream)

    p_llm_build_and_chat = subparsers.add_parser(
        "llm-build-and-chat", help="调用 LLM BuildAndChat"
    )
    p_llm_build_and_chat.add_argument("--user-id", required=True, help="用户 ID")
    p_llm_build_and_chat.add_argument("--template-id", required=True, help="模板 ID")
    p_llm_build_and_chat.add_argument(
        "--params",
        nargs="*",
        default=[],
        help="模板参数，格式 k=v",
    )
    p_llm_build_and_chat.add_argument("--model", default="", help="模型名，空则走服务默认")
    p_llm_build_and_chat.add_argument("--temperature", type=float, default=None, help="采样温度")
    p_llm_build_and_chat.add_argument("--max-tokens", type=int, default=None, help="最大输出 token")
    p_llm_build_and_chat.add_argument("--top-p", type=float, default=None, help="top_p 参数")
    p_llm_build_and_chat.add_argument("--stop", nargs="*", default=[], help="停止词列表")
    p_llm_build_and_chat.add_argument("--extra", nargs="*", default=[], help="扩展参数，格式 k=v")
    p_llm_build_and_chat.set_defaults(handler=_run_llm_build_and_chat)

    p_llm_build_and_chat_stream = subparsers.add_parser(
        "llm-build-and-chat-stream", help="调用 LLM BuildAndChatStream"
    )
    p_llm_build_and_chat_stream.add_argument("--user-id", required=True, help="用户 ID")
    p_llm_build_and_chat_stream.add_argument("--template-id", required=True, help="模板 ID")
    p_llm_build_and_chat_stream.add_argument(
        "--params",
        nargs="*",
        default=[],
        help="模板参数，格式 k=v",
    )
    p_llm_build_and_chat_stream.add_argument("--model", default="", help="模型名，空则走服务默认")
    p_llm_build_and_chat_stream.add_argument(
        "--temperature", type=float, default=None, help="采样温度"
    )
    p_llm_build_and_chat_stream.add_argument(
        "--max-tokens", type=int, default=None, help="最大输出 token"
    )
    p_llm_build_and_chat_stream.add_argument("--top-p", type=float, default=None, help="top_p 参数")
    p_llm_build_and_chat_stream.add_argument("--stop", nargs="*", default=[], help="停止词列表")
    p_llm_build_and_chat_stream.add_argument(
        "--extra", nargs="*", default=[], help="扩展参数，格式 k=v"
    )
    p_llm_build_and_chat_stream.set_defaults(handler=_run_llm_build_and_chat_stream)

    return parser


def run(args: argparse.Namespace) -> int:
    """命令执行入口。"""
    cfg = ClientConfig(
        base_url=_normalize_base_url(args.base_url),
        api_key=args.api_key.strip(),
        timeout=args.timeout,
    )
    if not cfg.api_key:
        raise CliError("参数错误：--api-key 不能为空")

    handler = getattr(args, "handler", None)
    if handler is None:
        raise CliError("未指定子命令")
    return int(handler(cfg, args))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run(args)
    except CliError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
