#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Gateway API 模型调用文件 - GLM-5

调用 LLM Gateway 网关的 POST /api/v1/llm/chat 接口。
"""

import json
import time
import traceback
import requests

from .api_keys import OPENAI_URL, OPENAI_API_KEY, OPENAI_MODEL

API_URL = OPENAI_URL.rstrip("/") + "/api/v1/llm/chat"
API_KEY = OPENAI_API_KEY
MODEL = OPENAI_MODEL


def llm_response(prompt: str) -> str | None:
    """
    调用 LLM Gateway LLM Chat API。

    参数:
        prompt: 用户提示词

    返回:
        str: 模型回复内容
    """
    max_retries = 8
    tried = 0
    last_error = ""
    base_delay = 2

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "prompt": prompt,
        "model": MODEL,
    }

    while tried < max_retries:
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=300,
            )

            status_code = response.status_code
            response_text = response.text

            if status_code == 504:
                # 服务端网关超时（模型推理时间超过网关限制）
                delay = base_delay * (2 ** tried)
                last_error = "HTTP 504 (服务端超时)"
                print(f"[Retry {tried + 1}/{max_retries}] 推理超时，等待 {delay}s 后重试...")
                tried += 1
                time.sleep(delay)
                continue
            elif status_code == 503:
                delay = base_delay * (2 ** tried)
                last_error = "HTTP 503 (服务暂时不可用)"
                print(f"[Retry {tried + 1}/{max_retries}] 服务器繁忙，等待 {delay}s 后重试...")
                tried += 1
                time.sleep(delay)
                continue
            elif status_code == 429 or (status_code == 500 and "429" in response_text):
                # LLM Gateway 将上游 OpenAI 429 包装为 500
                delay = base_delay * (2 ** tried) * 2
                last_error = "HTTP 429/500 (上游限流)"
                print(f"[Retry {tried + 1}/{max_retries}] 上游限流，等待 {delay}s 后重试...")
                tried += 1
                time.sleep(delay)
                continue
            elif status_code != 200:
                last_error = f"HTTP {status_code}"
                print(f"[Retry {tried + 1}/{max_retries}] {last_error}: {response_text[:200]}")
                tried += 1
                time.sleep(base_delay * tried)
                continue

            resp_data = response.json()

            if resp_data.get("status") == "OK":
                content = resp_data.get("data", {}).get("content", "")
                if content:
                    return content
                else:
                    last_error = "返回内容为空"
                    print(f"[Retry {tried + 1}/{max_retries}] 返回内容为空")
                    tried += 1
                    time.sleep(base_delay)
                    continue
            else:
                last_error = resp_data.get("message", "未知错误")
                print(f"[Retry {tried + 1}/{max_retries}] API 错误: {last_error}")
                tried += 1
                time.sleep(base_delay)
                continue

        except requests.exceptions.Timeout:
            delay = base_delay * (2 ** tried)
            last_error = "请求超时"
            print(f"[Retry {tried + 1}/{max_retries}] 超时，等待 {delay}s 后重试...")
            tried += 1
            time.sleep(delay)

        except requests.exceptions.ConnectionError as e:
            delay = base_delay * (2 ** tried)
            last_error = f"连接失败: {e}"
            print(f"[Retry {tried + 1}/{max_retries}] 连接失败，等待 {delay}s 后重试...")
            tried += 1
            time.sleep(delay)

        except json.JSONDecodeError as e:
            last_error = f"响应JSON解析失败: {e}"
            print(f"[Retry {tried + 1}/{max_retries}] {last_error}")
            tried += 1
            time.sleep(base_delay)

        except Exception as e:
            last_error = f"未知错误: {e}"
            print(f"[Retry {tried + 1}/{max_retries}] {last_error}")
            traceback.print_exc()
            tried += 1
            time.sleep(base_delay)

    print(f"模型调用最终失败: {last_error}")
    return None


if __name__ == "__main__":
    result = llm_response("你好，请用一句话自我介绍。")
    print("模型输出：", result)
