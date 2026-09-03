
# 适用版本 openai >= 1.0.0
from openai import OpenAI
import os
import time

API_KEY = os.getenv("GPT_API_KEY") or os.getenv("OPENAI_API_KEY", "")

client = OpenAI(
    api_key=API_KEY,
    base_url=os.getenv("GPT_BASE_URL", "https://api-gateway.glm.ai/v1")
)

def llm_response(prompt: str):
    max_retries = 3
    tried = 0
    json_error_count = 0
    target_error = "Error code: 500 - {'code': 500, 'message': 'unexpected end of JSON input'}"

    while tried < max_retries:
        try:
            response = client.chat.completions.create(
                model="gpt-5.4",  # 注意：改成你 YAML 中对应的 model 名称
                messages=[
                    {"role": "user", "content": prompt},
                ],
                # temperature=0.7,
                # max_tokens=1024,
            )
            return response.choices[0].message.content

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
    result = llm_response("我能用这些做什么菜？")
    print("模型输出：", result)
