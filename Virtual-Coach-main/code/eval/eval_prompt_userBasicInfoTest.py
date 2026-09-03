import os
import json
import sys
import time
import concurrent.futures
from datetime import datetime
from tqdm import tqdm

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

from code.models.glm_4_7_flash import llm_response
from data.prompt.userBasicInfoTest.v1 import userBasicInfoTest

ROOT_DIR = project_root
eval_dataset_file = os.path.join(ROOT_DIR, 'data', 'eval', 'userBasicInfoTest.json')
with open(eval_dataset_file, "r", encoding="utf-8") as f:
    eval_dataset = json.load(f)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
eval_dataset_result_file = os.path.join(
    ROOT_DIR, 'data', 'eval_result',
    'userBasicInfoTest_v1_result_' + timestamp + '.json'
)
os.makedirs(os.path.dirname(eval_dataset_result_file), exist_ok=True)


def extract_last_complete_json(text: str):
    """提取文本中的最后一个完整的JSON对象。"""
    import re as _re
    _CODE_BLOCK_RE = _re.compile(r"```json\s*(.*?)\s*```", _re.S)

    def _try_load(blob: str):
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            pass
        try:
            return json.loads(blob.strip())
        except Exception:
            pass
        return None

    for block in reversed(_CODE_BLOCK_RE.findall(text)):
        obj = _try_load(block)
        if obj is not None:
            return obj

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

    matches = list(_re.finditer(r'\{[\s\S]*?\}', text))
    for m in reversed(matches):
        obj = _try_load(m.group())
        if obj is not None:
            return obj

    return None


def evaluate_accuracy():
    eval_dataset_result = []
    correct = 0
    total = len(eval_dataset)

    def process_sample(i):
        temp_data_result = {}
        temp_data = eval_dataset[i]["input"]
        temp_data_result["input"] = temp_data
        temp_data_prompt = userBasicInfoTest.format(
            user_input=temp_data["user_input"]
        )
        temp_data_result["prompt"] = temp_data_prompt

        response_json = None
        successful_times = None
        start_time = time.time()

        for times in range(3):
            try:
                response = llm_response(temp_data_prompt)
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

        if response_json is not None and successful_times is not None:
            ground_truth = eval_dataset[i]["output"]
            temp_data_result["ground_truth"] = ground_truth
            temp_data_result["time_cost"] = time.time() - start_time
            try:
                if response_json.get("name") == ground_truth.get("name") and response_json.get("gender") == ground_truth.get("gender"):
                    temp_data_result["is_correct"] = True
                else:
                    reason_str = "GT_name=" + str(ground_truth.get("name")) + " Pred_name=" + str(response_json.get("name")) + ", " + "GT_gender=" + str(ground_truth.get("gender")) + " Pred_gender=" + str(response_json.get("gender"))
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
    min_time = float('inf')
    max_time = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future_to_idx = {executor.submit(process_sample, i): i for i in range(len(eval_dataset))}
        for future in tqdm(concurrent.futures.as_completed(future_to_idx), total=len(eval_dataset)):
            result = future.result()
            eval_dataset_result.append(result)
            if result.get("is_correct"):
                correct += 1
            time_cost = result.get("time_cost", 0)
            all_time += time_cost
            min_time = min(min_time, time_cost)
            max_time = max(max_time, time_cost)

    accuracy = correct / total if total > 0 else 0.0
    average_time = all_time / total if total > 0 else 0.0
    print(f"\n评测完成：")
    print(f"总样本数: {total}")
    print(f"正确数: {correct}")
    print(f"准确率: {accuracy:.2%}")
    print(f"平均耗时: {average_time:.2f}秒")
    print(f"最小耗时: {min_time:.2f}秒")
    print(f"最大耗时: {max_time:.2f}秒")

    with open(eval_dataset_result_file, "w", encoding="utf-8") as f:
        json.dump(eval_dataset_result, f, ensure_ascii=False, indent=4)
    print(f"结果已保存: {eval_dataset_result_file}")

if __name__ == "__main__":
    evaluate_accuracy()
