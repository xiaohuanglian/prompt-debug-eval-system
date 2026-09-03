# pip install zai-sdk
from __future__ import annotations

import os

from zai import ZhipuAiClient

# Support both package-relative and script-style imports.
# 真实密钥放在 gitignore 的 llm_key.py，或环境变量 ZHIPU_API_KEY / GLM_API_KEY。
try:
    from .llm_key import api_key  # type: ignore
except Exception:
    try:
        from llm_key import api_key  # type: ignore
    except Exception:
        api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("GLM_API_KEY") or ""

model = "glm-4.7"

client = ZhipuAiClient(api_key=api_key)


def llm_chat_stream(prompt: str) -> None:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        thinking={
            "type": "enabled",  # 启用深度思考模式
        },
        stream=True,  # 启用流式输出
        max_tokens=4096,  # 最大输出tokens
        temperature=0.7,  # 控制输出的随机性
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")


def llm_chat(prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        thinking={
            "type": "enabled",  # 启用深度思考模式
        },
        stream=False,
    )
    return response.choices[0].message.content


def llm_chat_with_prompt(system_prompt: str, user_prompt: str) -> str:
    chat_completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        thinking={
            "type": "enabled",  # 启用深度思考模式
        },
        stream=False,
    )
    return chat_completion.choices[0].message.content


def main() -> None:
    print(llm_chat_with_prompt("你是一个软文写手，利用提供信息形成一段话软文。", "LLM是什么"))


if __name__ == "__main__":
    main()