import os
import json
import sys
import re
from datetime import datetime
from tqdm import tqdm
import time


# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

try:
    from code.models.glm_4_air import llm_response
    from data.prompt.DecisionScenario1 import DecisionScenario1
except ImportError as e:
    print(f"Import error: {e}")
    # 如果导入失败，尝试相对导入
    from ..models.glm_4_air import llm_response


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# print("CURRENT_DIR:", CURRENT_DIR)
PARENT_DIR = os.path.dirname(CURRENT_DIR)
# print("PARENT_DIR:", PARENT_DIR)
ROOT_DIR = os.path.dirname(PARENT_DIR)
# print("ROOT_DIR:", ROOT_DIR)

eval_dataset_file = os.path.join(ROOT_DIR, 'data', 'eval', 'DecisionScenario1.json')
with open(eval_dataset_file, "r", encoding="utf-8") as f:
    eval_dataset = json.load(f)
# print(eval_dataset[0])

# 获得时间戳
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
eval_dataset_result_file = os.path.join(ROOT_DIR, 'data', 'eval_result', 'DecisionScenario1_result_' + timestamp + '.json')
os.makedirs(os.path.dirname(eval_dataset_result_file), exist_ok=True)

def extract_last_complete_json(text: str):
    """
    提取文本中的最后一个完整的JSON对象
    修复点：
    1. 修正正则表达式，去除多余的转义符，确保能正确匹配 ```json ... ``` 代码块
    2. 修正字符串转义处理逻辑，确保能正确处理字符串中的转义字符
    3. 修复：部分模型输出没有 ```json ...``` 包裹，直接输出 json 或前后有多余内容
    4. 修复：部分模型输出有多余的反斜杠或特殊转义符，尝试预处理
    """
    # 优先匹配 ```json ... ``` 代码块
    _CODE_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.S)

    def _try_load(blob: str):
        # 先尝试直接解析
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            pass
        # 尝试去除多余转义符
        try:
            blob2 = blob.encode('utf-8').decode('unicode_escape')
            return json.loads(blob2)
        except Exception:
            pass
        # 尝试去除多余的换行、空格
        try:
            return json.loads(blob.strip())
        except Exception:
            pass
        return None

    # ---------- 1) 先看 ```json``` 代码块 ----------
    for block in reversed(_CODE_BLOCK_RE.findall(text)):
        obj = _try_load(block)
        if obj is not None:
            return obj

    # ---------- 2) 从后往前定位 {...} ----------
    # 允许有多余内容，找到最后一个完整的 JSON 对象
    depth = 0
    in_string = False
    escape = False
    start_idx = None

    # 反向扫描，找到最外层 '{' 对应的索引 start
    for i in range(len(text) - 1, -1, -1):
        ch = text[i]

        # 维护 in_string / escape 状态，忽略字符串内部的大括号
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
            if depth == 0:
                start_idx = i
                candidate = text[start_idx:end_idx+1] if 'end_idx' in locals() else text[start_idx:]
                obj = _try_load(candidate)
                if obj is not None:
                    return obj
                # 否则继续向左找上一层可能的 '{'

    # ---------- 3) 兜底：尝试提取所有 {...} 并解析 ----------
    # 有些模型输出会有多余内容，尝试提取所有大括号包裹的内容
    matches = list(re.finditer(r'\{[\s\S]*?\}', text))
    for m in reversed(matches):
        candidate = m.group()
        obj = _try_load(candidate)
        if obj is not None:
            return obj

    return None


def evaluate_accuracy():
    """
    评测脚本：计算模型预测的准确率
    """
    eval_dataset_result = []
    correct = 0
    total = len(eval_dataset)
    import concurrent.futures

    def process_sample(i):
        temp_data_result = {}
        temp_data = eval_dataset[i]["input"]
        temp_data_result["input"] = temp_data
        temp_data_prompt = DecisionScenario1.format(
            training_performance=temp_data["training_performance"],
            exercise_name=temp_data["exercise_name"],
            set_reps=temp_data["set_reps"]
        )
        temp_data_result["prompt"] = temp_data_prompt

        response_json = None
        successful_times = None

        start_time = time.time()
        # 尝试3次获取有效响应
        for times in range(3):
            try:
                response = llm_response(user_dialogue=temp_data_prompt)
                temp_data_result["response_" + str(times)] = response

                if response is None:
                    temp_data_result["response_json_" + str(times)] = None
                    continue

                response_json = extract_last_complete_json(response)
                temp_data_result["response_json_" + str(times)] = response_json

                if response_json is not None:
                    successful_times = times
                    break
            except Exception as e:
                print(f"样本 {i} 第 {times+1} 次尝试失败: {str(e)}")
                temp_data_result["response_" + str(times)] = f"Error: {str(e)}"
                temp_data_result["response_json_" + str(times)] = None
                continue

        # 处理结果
        if response_json is not None and successful_times is not None:
            ground_truth = eval_dataset[i]["output"]
            temp_data_result["ground_truth"] = ground_truth
            temp_data_result["time_cost"] = time.time() - start_time
            try:
                if response_json["performance_class"] == ground_truth["performance_class"]:
                    temp_data_result["is_correct"] = True
                else:
                    reason_str = f"真实={ground_truth['performance_class']}, 预测={response_json['performance_class']}"
                    print(f"样本 {i} 分类错误: {reason_str}")
                    temp_data_result["is_correct"] = False
                    temp_data_result["error_reason"] = reason_str
            except KeyError as e:
                print(f"样本 {i} JSON格式错误，缺少字段: {str(e)}")
                temp_data_result["is_correct"] = False
                temp_data_result["error_reason"] = f"JSON格式错误: {str(e)}"
        else:
            print(f"样本 {i} 无法获取有效响应")
            temp_data_result["is_correct"] = False
            temp_data_result["error_reason"] = "无法获取有效响应"

        return temp_data_result

    eval_dataset_result = []
    correct = 0
    all_time = 0
    min_time = 0
    max_time = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # tqdm 结合 as_completed 实现进度条
        future_to_idx = {executor.submit(process_sample, i): i for i in range(len(eval_dataset))}
        for future in tqdm(concurrent.futures.as_completed(future_to_idx), total=len(eval_dataset)):
            result = future.result()
            eval_dataset_result.append(result)
            if result.get("is_correct"):
                correct += 1
            time_cost = result.get("time_cost")
            all_time += time_cost
            min_time = min(min_time, time_cost)
            max_time = max(max_time, time_cost)

    accuracy = correct / total if total > 0 else 0.0
    average_time = all_time / total if total > 0 else 0.0
    print(f"\n✅ 评测完成：")
    print(f"总样本数: {total}")
    print(f"正确数: {correct}")
    print(f"准确率: {accuracy:.2%}")
    print(f"平均耗时: {average_time:.2f}秒")
    print(f"最小耗时: {min_time:.2f}秒")
    print(f"最大耗时: {max_time:.2f}秒")

    with open(eval_dataset_result_file, "w", encoding="utf-8") as f:
        json.dump(eval_dataset_result, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    evaluate_accuracy()