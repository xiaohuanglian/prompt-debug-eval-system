import re

def normalize_string(s: str) -> str:
    # 1. 把非英文字母和非数字替换为下划线
    s = re.sub(r'[^a-zA-Z0-9]', '_', s)
    # 2. 转为小写
    return s.lower()

# 示例
text = "Glm-4-air"
result = normalize_string(text)
print(result)  # 输出: glm_4_air