#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
validate_json.py
检查一个 JSON 文件是否可被解析；若字符串字段中包含嵌套 JSON（可能多级），一并验证。
用法：
  python validate_json.py <path_to_json> [--max-str-len 200] [--strict-startend]
参数：
  --max-str-len：报错时字符串片段最大展示长度（默认 200）
  --strict-startend：仅当字符串首尾分别为 {}/[] 才尝试当作 JSON 解析（默认宽松：只要以 { 或 [ 开头就尝试）
返回码：
  0  一切正常（含所有嵌套 JSON）
  1  解析错误（顶层或嵌套）
  2  文件/读取错误
"""

import argparse
import io
import json
import os
import sys
from typing import Any, List, Tuple, Union

JsonType = Union[dict, list, str, int, float, bool, None]


def json_path_join(parent: str, key: Union[str, int]) -> str:
    if parent == "$":
        if isinstance(key, int):
            return f"$[{key}]"
        else:
            return f"$.{key}"
    else:
        if isinstance(key, int):
            return f"{parent}[{key}]"
        else:
            return f"{parent}.{key}"


def snippet(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    half = max(1, (limit - 5) // 2)
    return f"{s[:half]} ... {s[-half:]}"


def is_potential_json_string(s: str, strict_startend: bool = False) -> bool:
    t = s.strip()
    if not t:
        return False
    if strict_startend:
        return (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]"))
    else:
        return t.startswith("{") or t.startswith("[")


def explain_common_error(msg: str) -> str:
    m = msg.lower()
    hints = []
    if "expecting property name enclosed in double quotes" in m:
        hints.append("键名应使用双引号（单引号或未加引号会报错）。")
    if "invalid control character" in m:
        hints.append("字符串中可能包含未转义的控制字符（如换行应写为 \\n）。")
    if "extra data" in m:
        hints.append("顶层 JSON 后面存在多余内容（可能是多个 JSON 串未用数组包裹）。")
    if "unterminated string" in m:
        hints.append("字符串未正确闭合（缺少结尾的双引号或转义错误）。")
    if "trailing comma" in m:
        hints.append("JSON 不允许尾随逗号，请去掉最后一个元素后的逗号。")
    if "expecting value" in m and "line 1 column 1" in m:
        hints.append("文件可能为空、只有 BOM，或以非法字符开头。")
    if "single quotes" in m or "expecting ':' delimiter" in m:
        hints.append("可能误用了单引号或缺少冒号分隔键值。")
    if hints:
        return "可能原因：" + "；".join(hints)
    return ""


def format_top_level_error(e: json.JSONDecodeError, text: str, max_len: int) -> str:
    # 提取错误位置附近的片段
    # json 模块的 e.pos 是字符偏移（从 0 开始）
    start = max(0, e.pos - 40)
    end = min(len(text), e.pos + 40)
    context = text[start:end].replace("\n", "\\n")
    pointer = " " * (e.pos - start) + "^"
    extra = explain_common_error(e.msg)
    parts = [
        f"顶层 JSON 解析失败：{e.msg}",
        f"位置：行 {e.lineno}, 列 {e.colno}",
        f"上下文：\"{snippet(context, max_len)}\"",
        f"          {pointer}",
    ]
    if extra:
        parts.append(extra)
    return "\n".join(parts)


def try_parse_nested(s: str) -> Tuple[bool, Any, str]:
    try:
        return True, json.loads(s), ""
    except json.JSONDecodeError as e:
        return False, None, f"{e.msg}（在该字符串内，字符偏移 {e.pos}）"
    except Exception as e:
        return False, None, f"未知错误：{type(e).__name__}: {e}"


def validate_nested(obj: JsonType,
                    path: str = "$",
                    strict_startend: bool = False,
                    max_str_len: int = 200,
                    errors: List[str] = None,
                    max_errors: int = 50) -> List[str]:
    if errors is None:
        errors = []

    if len(errors) >= max_errors:
        return errors

    if isinstance(obj, dict):
        for k, v in obj.items():
            p = json_path_join(path, str(k))
            validate_nested(v, p, strict_startend, max_str_len, errors, max_errors)
            if len(errors) >= max_errors:
                break

    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = json_path_join(path, i)
            validate_nested(v, p, strict_startend, max_str_len, errors, max_errors)
            if len(errors) >= max_errors:
                break

    elif isinstance(obj, str):
        if is_potential_json_string(obj, strict_startend):
            ok, parsed, err = try_parse_nested(obj)
            if not ok:
                # 提供字符串片段，避免输出过长
                cleaned = obj.strip().replace("\n", " ")
                errors.append(
                    f"嵌套 JSON 解析失败于路径：{path}\n"
                    f"字符串片段：\"{snippet(cleaned, max_str_len)}\"\n"
                    f"原因：{err}"
                )
            else:
                # 继续向内层递归
                validate_nested(parsed, path + "(embedded)", strict_startend, max_str_len, errors, max_errors)

    # 其他类型无需处理
    return errors


def main():
    parser = argparse.ArgumentParser(description="验证 JSON 文件以及字符串中的嵌套 JSON。")
    parser.add_argument("file", help="待验证的 JSON 文件路径")
    parser.add_argument("--max-str-len", type=int, default=200, help="报错时显示的字符串片段最大长度")
    parser.add_argument("--strict-startend", action="store_true",
                        help="仅当字符串首尾为 {} 或 [] 才尝试解析为 JSON")
    args = parser.parse_args()

    path = args.file

    if not os.path.exists(path):
        print(f"错误：文件不存在：{path}", file=sys.stderr)
        sys.exit(2)

    try:
        with io.open(path, "r", encoding="utf-8", errors="strict") as f:
            text = f.read()
    except UnicodeDecodeError as e:
        print(f"错误：文件不是有效的 UTF-8 编码：{e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"错误：读取文件失败：{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)

    # 顶层解析
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(format_top_level_error(e, text, args.max_str_len))
        sys.exit(1)

    # 递归校验嵌套 JSON
    errors = validate_nested(
        data,
        path="$",
        strict_startend=args.strict_startend,
        max_str_len=args.max_str_len,
        errors=[],
    )

    if errors:
        print("发现嵌套 JSON 解析错误：")
        for i, err in enumerate(errors, 1):
            print(f"\n[{i}] {err}")
        sys.exit(1)

    # 一切正常
    print("OK：文件为有效 JSON，且所有可识别的嵌套 JSON 均解析通过。")
    sys.exit(0)


if __name__ == "__main__":
    main()