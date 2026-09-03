import os
import re
import sys
import importlib

system_api_config = {}


def _strip_python_string_literal(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _normalize_openai_base_url(url: str) -> str:
    # OpenAI SDK expects base URL root and appends /chat/completions itself.
    return re.sub(r"/chat/completions/?$", "", url.strip())


meta_llm_api_template = '''
# 适用版本 openai >= 1.0.0
from openai import OpenAI
import time

API_KEY = "{model_api_key}"

client = OpenAI(
    api_key=API_KEY,
    base_url="{url}"
)

def llm_response(prompt: str):
    max_retries = 3
    tried = 0
    json_error_count = 0
    target_error = "Error code: 500 - {{'code': 500, 'message': 'unexpected end of JSON input'}}"

    while tried < max_retries:
        try:
            response = client.chat.completions.create(
                model="{model}",  # 注意：改成你 YAML 中对应的 model 名称
                messages=[
                    {{"role": "user", "content": prompt}},
                ],
                # temperature=0.7,
                # max_tokens=1024,
            )
            return response.choices[0].message.content

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
    result = llm_response("我能用这些做什么菜？")
    print("模型输出：", result)
'''

def auto_generate_llm_call():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    code_dir = os.path.dirname(current_dir)
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    code_call_dir = os.path.join(code_dir, "models")
    code_api_keys_dir = os.path.join(code_call_dir,"api_keys.py")

    with open(code_api_keys_dir, "r", encoding="utf-8") as f:
        code_api_keys = f.read()
        for line in code_api_keys.split("\n"):
            if "_URL" in line or "_API_KEY" in line or "_MODEL" in line:
                if_name = line.split("_")[0]
                if if_name not in system_api_config.keys():
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

    new_system_api_config = {}
    for if_name, if_config in system_api_config.items():
        if "url" not in if_config.keys() or "api_key" not in if_config.keys() or "model" not in if_config.keys():
            continue
        elif if_config["url"] == "" or if_config["api_key"] == "" or if_config["model"] == "":
            continue
        new_system_api_config[if_name] = if_config

    for if_name, if_config in new_system_api_config.items():
        temp_url = _normalize_openai_base_url(if_config["url"])
        temp_api_key = if_config["api_key"]
        temp_model = if_config["model"]

        model_name_str = re.sub(r'[^a-zA-Z0-9]', '_', temp_model).lower()
        name2filename = model_name_str + ".py"
        filename = os.path.join(code_call_dir, name2filename)
        if not os.path.exists(filename):
            with open(filename, "w", encoding="utf-8") as f:
                f.write(meta_llm_api_template.format(model=temp_model, url=temp_url, model_api_key=temp_api_key))
            print(f"Generated model api file: {filename}")
        # test
        model_module = importlib.import_module(f"models.{model_name_str}")
        return_json = {
            "question": "你是谁？",
            "answer": model_module.llm_response("你是谁？")
        }
        print(return_json)

if __name__ == '__main__':
    auto_generate_llm_call()