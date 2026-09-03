import os
import re
import sys
import inspect
import importlib
import importlib.util


def _strip_python_string_literal(s: str) -> str:
    """去除 Python 字符串字面量的引号。"""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _normalize_openai_base_url(url: str) -> str:
    """规范化 OpenAI base URL，移除尾部的 /chat/completions。"""
    return re.sub(r"/chat/completions/?$", "", url.strip())


def _get_project_root() -> str:
    """获取项目根目录。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_api_keys_path() -> str:
    """获取 api_keys.py 的路径。"""
    return os.path.join(_get_project_root(), "code", "models", "api_keys.py")


def list_available_models() -> list:
    """
    解析 api_keys.py，返回所有配置完整（URL/API_KEY/MODEL 均非空）的模型信息。

    返回:
        list of dict: [{"prefix": "GLM", "model_name": "glm-4.7-flash",
                        "module_name": "glm_4_7_flash"}, ...]
    """
    api_keys_path = _get_api_keys_path()
    if not os.path.exists(api_keys_path):
        print(f"警告: api_keys.py 不存在: {api_keys_path}")
        return []

    system_api_config = {}
    with open(api_keys_path, "r", encoding="utf-8") as f:
        for line in f.read().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if "_URL" in line or "_API_KEY" in line or "_MODEL" in line:
                if_name = line.split("_")[0]
                if if_name not in system_api_config:
                    system_api_config[if_name] = {}
                if f"{if_name}_URL" in line:
                    system_api_config[if_name]["url"] = _strip_python_string_literal(
                        line.split("=", 1)[1]
                    )
                elif f"{if_name}_API_KEY" in line:
                    system_api_config[if_name]["api_key"] = _strip_python_string_literal(
                        line.split("=", 1)[1]
                    )
                elif f"{if_name}_MODEL" in line:
                    system_api_config[if_name]["model"] = _strip_python_string_literal(
                        line.split("=", 1)[1]
                    )

    available = []
    for prefix, config in system_api_config.items():
        if not all(k in config and config[k] for k in ("url", "api_key", "model")):
            continue
        model_name = config["model"]
        module_name = re.sub(r'[^a-zA-Z0-9]', '_', model_name).lower()
        available.append({
            "prefix": prefix,
            "model_name": model_name,
            "module_name": module_name,
            "url": _normalize_openai_base_url(config["url"]),
            "api_key": config["api_key"],
        })

    return available


# 自动生成模型文件的模板。使用标准库 urllib，避免依赖 openai/httpx 栈。
_META_LLM_API_TEMPLATE = '''
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

RUNTIME_CONFIG_VERSION = 2
CONFIG_PREFIX = {prefix!r}
API_KEY = os.getenv(CONFIG_PREFIX + "_API_KEY", "")
BASE_URL = ""
MODEL = ""

def configure(api_key: str = "", base_url: str = "", model: str = ""):
    """运行时注入配置，避免把 API Key 写入自动生成的源码文件。"""
    global API_KEY, BASE_URL, MODEL
    ns = {{}}
    if not all((api_key, base_url, model)):
        try:
            api_keys_path = pathlib.Path(__file__).with_name("api_keys.py")
            exec(api_keys_path.read_text(encoding="utf-8"), ns)
        except FileNotFoundError:
            pass
    API_KEY = api_key or os.getenv(CONFIG_PREFIX + "_API_KEY") or ns.get(CONFIG_PREFIX + "_API_KEY", "") or API_KEY
    configured_url = base_url or os.getenv(CONFIG_PREFIX + "_URL") or ns.get(CONFIG_PREFIX + "_URL", "") or BASE_URL
    BASE_URL = re.sub(r"/chat/completions/?$", "", configured_url.strip()).rstrip("/")
    MODEL = model or os.getenv(CONFIG_PREFIX + "_MODEL") or ns.get(CONFIG_PREFIX + "_MODEL", "") or MODEL
    if not all((API_KEY, BASE_URL, MODEL)):
        raise RuntimeError("请配置模型的 API_KEY、URL 和 MODEL（本地 api_keys.py 或对应环境变量）。")

def _chat_completions(prompt: str) -> str:
    payload = json.dumps({{
        "model": MODEL,
        "messages": [{{"role": "user", "content": prompt}}],
    }}, ensure_ascii=False).encode("utf-8")
    payload_size = len(payload)
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=payload,
        method="POST",
        headers={{
            "Authorization": "Bearer " + API_KEY,
            "Content-Type": "application/json",
        }},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception as e:
        raise RuntimeError(f"chat/completions request failed; payload_bytes={{payload_size}}; error={{e}}") from e
    data = json.loads(body)
    return data["choices"][0]["message"]["content"]

def llm_response(prompt: str):
    if not all((API_KEY, BASE_URL, MODEL)):
        configure()
    max_retries = 3
    tried = 0
    json_error_count = 0
    target_error = "Error code: 500 - {{'code': 500, 'message': 'unexpected end of JSON input'}}"

    while tried < max_retries:
        try:
            return _chat_completions(prompt)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            print(f"[Retry {{tried+1}}/{{max_retries}}] HTTP {{e.code}}: {{detail}}")
        except Exception as e:
            print(f"[Retry {{tried+1}}/{{max_retries}}] 请求出错: {{e}}")
            if str(e) == target_error:
                json_error_count += 1
            if json_error_count == max_retries:
                max_retries = 6
            tried += 1
            time.sleep(2)

    if json_error_count == max_retries:
        return target_error
    return None


if __name__ == "__main__":
    result = llm_response("你是谁？")
    print("模型输出：", result)
'''


def _ensure_model_file(model_info: dict) -> str:
    """Ensure a runtime-configurable model module exists and return its module name."""
    models_dir = os.path.join(_get_project_root(), "code", "models")
    filename = model_info["module_name"] + ".py"
    filepath = os.path.join(models_dir, filename)

    should_generate = not os.path.exists(filepath)
    if not should_generate:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = f.read()
            # Older generated files embedded API keys directly and ignored later
            # edits to api_keys.py. Regenerate them into the runtime-configurable
            # template so GUI selections always use the latest settings.
            should_generate = (
                "RUNTIME_CONFIG_VERSION = 2" not in existing
                or "def configure(" not in existing
                or "CONFIG_PREFIX" not in existing
                or "urllib.request" not in existing
            )
        except Exception:
            should_generate = True

    if should_generate:
        content = _META_LLM_API_TEMPLATE.format(
            prefix=model_info["prefix"],
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"自动生成/更新模型文件: {filepath}")

    return model_info["module_name"]

def _make_unified_caller(module) -> callable:
    """
    将不同签名的 llm_response 包装为统一的 (prompt: str) -> str 接口。
    兼容两种模式：
      - llm_response(prompt: str)  — 新版简单调用
      - llm_response(user_dialogue=..., system_prompt=..., ...) — 旧版关键字调用
    """
    sig = inspect.signature(module.llm_response)
    params = list(sig.parameters.keys())
    if params and params[0] == 'prompt':
        return module.llm_response
    else:
        def wrapper(prompt: str) -> str:
            return module.llm_response(user_dialogue=prompt)
        return wrapper


def load_model(model_info: dict) -> callable:
    """
    加载模型并返回统一的调用函数 (prompt: str) -> str。

    参数:
        model_info: list_available_models() 返回的字典之一

    返回:
        callable: 接受 prompt 字符串，返回模型输出字符串
    """
    module_name = _ensure_model_file(model_info)

    models_dir = os.path.join(_get_project_root(), "code", "models")
    module_path = os.path.join(models_dir, module_name + ".py")
    unique_name = f"_prompt_eval_model_{module_name}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模型文件: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    configure = getattr(module, "configure", None)
    if callable(configure):
        configure(
            api_key=model_info.get("api_key", ""),
            base_url=model_info.get("url", ""),
            model=model_info.get("model_name", ""),
        )
    return _make_unified_caller(module)

