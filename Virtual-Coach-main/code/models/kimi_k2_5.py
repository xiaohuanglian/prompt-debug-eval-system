
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

CONFIG_PREFIX = "OPENAI"
API_KEY = os.getenv(CONFIG_PREFIX + "_API_KEY", "")
BASE_URL = "https://api.moonshot.cn/v1"
MODEL = "kimi-k2.5"

def configure(api_key: str = "", base_url: str = "", model: str = ""):
    """运行时注入配置，避免把 API Key 写入自动生成的源码文件。"""
    global API_KEY, BASE_URL, MODEL
    if not api_key:
        try:
            api_keys_path = pathlib.Path(__file__).with_name("api_keys.py")
            ns = {}
            exec(api_keys_path.read_text(encoding="utf-8"), ns)
            api_key = ns.get(CONFIG_PREFIX + "_API_KEY", "")
        except Exception:
            api_key = ""
    API_KEY = api_key or API_KEY
    BASE_URL = (base_url or BASE_URL).rstrip("/")
    MODEL = model or MODEL
    if not API_KEY:
        raise RuntimeError("API_KEY 为空，请检查 code/models/api_keys.py 或环境配置。")

def _chat_completions(prompt: str) -> str:
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }, ensure_ascii=False).encode("utf-8")
    payload_size = len(payload)
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer " + API_KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception as e:
        raise RuntimeError(f"chat/completions request failed; payload_bytes={payload_size}; error={e}") from e
    data = json.loads(body)
    return data["choices"][0]["message"]["content"]

def llm_response(prompt: str):
    if not API_KEY:
        configure()
    max_retries = 3
    tried = 0
    json_error_count = 0
    target_error = "Error code: 500 - {'code': 500, 'message': 'unexpected end of JSON input'}"

    while tried < max_retries:
        try:
            return _chat_completions(prompt)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            print(f"[Retry {tried+1}/{max_retries}] HTTP {e.code}: {detail}")
        except Exception as e:
            print(f"[Retry {tried+1}/{max_retries}] 请求出错: {e}")
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
