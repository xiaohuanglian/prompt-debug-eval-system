import re
import json


def extract_last_complete_json(text: str):
    """
    提取文本中的最后一个完整的JSON对象。
    支持 ```json 代码块、反向扫描匹配、兜底正则三种策略。
    """
    _CODE_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.S)

    def _try_load(blob: str):
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            pass
        try:
            blob2 = blob.encode('utf-8').decode('unicode_escape')
            return json.loads(blob2)
        except Exception:
            pass
        try:
            return json.loads(blob.strip())
        except Exception:
            pass
        return None

    # 1) 先看 ```json``` 代码块
    for block in reversed(_CODE_BLOCK_RE.findall(text)):
        obj = _try_load(block)
        if obj is not None:
            return obj

    # 2) 从后往前定位 {...}
    depth = 0
    in_string = False
    escape = False
    end_idx = None

    for i in range(len(text) - 1, -1, -1):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        else:
            if ch == '"':
                in_string = True
                escape = False
                continue

        if ch == '}':
            if depth == 0:
                end_idx = i
            depth += 1
        elif ch == '{':
            depth -= 1
            if depth == 0 and end_idx is not None:
                candidate = text[i:end_idx + 1]
                obj = _try_load(candidate)
                if obj is not None:
                    return obj

    # 3) 兜底：尝试提取所有 {...} 并解析
    matches = list(re.finditer(r'\{[\s\S]*?\}', text))
    for m in reversed(matches):
        candidate = m.group()
        obj = _try_load(candidate)
        if obj is not None:
            return obj

    return None


def extract_json_array(text: str):
    """
    提取文本中的JSON数组。
    支持 ```json 代码块和直接匹配 [...] 两种策略。
    """
    _CODE_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.S)

    # 1) 先看 ```json``` 代码块
    for block in reversed(_CODE_BLOCK_RE.findall(text)):
        try:
            obj = json.loads(block)
            if isinstance(obj, list):
                return obj
        except json.JSONDecodeError:
            pass

    # 2) 直接尝试解析全文
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass

    # 3) 从后往前定位 [...]
    depth = 0
    in_string = False
    escape = False
    end_idx = None

    for i in range(len(text) - 1, -1, -1):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        else:
            if ch == '"':
                in_string = True
                escape = False
                continue

        if ch == ']':
            if depth == 0:
                end_idx = i
            depth += 1
        elif ch == '[':
            depth -= 1
            if depth == 0 and end_idx is not None:
                candidate = text[i:end_idx + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, list):
                        return obj
                except json.JSONDecodeError:
                    pass

    return None
