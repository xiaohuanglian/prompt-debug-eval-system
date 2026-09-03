import requests
import json

# 定义厂商信息列表
from .api_keys import GLM_URL, GLM_API_KEY, GLM_MODEL


def llm_response(user_dialogue=None, system_prompt=None, history_messages=None):
    """
    发送请求到LLM API并获取响应
    
    Args:
        user_dialogue: 用户对话内容
        prompt: 系统提示词
        history_messages: 历史消息列表,格式为[{"role": "user", "content": "用户对话内容"}, {"role": "assistant", "content": "LLM的响应内容"}]
    
    Returns:
        str: LLM的响应内容
    """
    # 构造默认的messages
    default_messages = []
    if history_messages:
        default_messages.extend(history_messages)
    
    if system_prompt:
        default_messages.append({
            "role": "system",
            "content": system_prompt
        })
    # else:
    #     default_messages.append({
    #         "role": "system",
    #         "content": "你擅长从文本中提取关键信息，精确、数据驱动，重点突出关键信息，根据用户提供的文本片段提取关键数据和事实，将提取的信息以清晰的 JSON 格式呈现。"
    #     })
    
    if user_dialogue:
        default_messages.append({
            "role": "user",
            "content": user_dialogue
        })


    # 构造请求体
    data = {
        "model": GLM_MODEL,
        "messages": default_messages
    }
    
    # print("data:", data)
    
    # 设置请求头
    headers = {
        "Authorization": GLM_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        # 发送POST请求
        response = requests.post(
            GLM_URL,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        
        # 解析响应
        response_data = response.json()
        choices = response_data["choices"]
        message = choices[0]["message"]
        
        
        return message["content"].strip()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    print(llm_response(user_dialogue="健身计划"))