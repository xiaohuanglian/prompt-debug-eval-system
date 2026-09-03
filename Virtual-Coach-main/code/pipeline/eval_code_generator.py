import json
import re

from .json_utils import extract_last_complete_json  # re-exported for convenience
from .prompt_generator import extract_placeholders


# 与 eval_runner 保持一致的「跳过比对」字段名 token 集合（按 token 精确匹配）。
LONG_TEXT_KEY_KEYWORDS = frozenset({
    "reason", "reasons",
    "rationale", "rationales",
    "summary", "summaries",
    "narrative", "narratives",
    "explanation", "explanations", "explain",
    "description", "descriptions",
    "comment", "comments",
    "feedback",
    "review", "reviews",
    "analysis", "analyses",
    "insight", "insights",
    "message", "messages",
    "content", "contents",
    "text", "texts",
    "note", "notes",
    "remark", "remarks",
    "理由", "原因", "说明", "描述", "总结", "评价", "建议",
})


_EXTRACT_JSON_FUNCTION = '''
def extract_last_complete_json(text):
    """提取文本中的最后一个完整的JSON对象。"""
    import re as _re
    _CODE_BLOCK_RE = _re.compile(r"```json\\s*(.*?)\\s*```", _re.S)

    def _try_load(blob):
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
            elif ch == '\\\\':
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

    matches = list(_re.finditer(r'\\{[\\s\\S]*?\\}', text))
    for m in reversed(matches):
        obj = _try_load(m.group())
        if obj is not None:
            return obj

    return None


def coerce_single_text_response(response, ground_truth):
    """单文本输出场景：把纯文本响应包装为 ground_truth 的唯一字符串字段。"""
    if not isinstance(response, str) or not response.strip():
        return None
    if not isinstance(ground_truth, dict) or len(ground_truth) != 1:
        return None
    key, expected = next(iter(ground_truth.items()))
    if not isinstance(expected, str):
        return None
    text = response.strip()
    if text.startswith("{") or text.startswith("["):
        return None
    return {key: text}
'''


# 嵌入到生成脚本里的结构比对块。
# 注意：本块用 .format() 注入 long_text_keywords；其余字面 {{ }} 都是双写转义后的真实大括号。
_STRUCTURAL_COMPARE_BLOCK = '''
from code.pipeline.eval_runner import structural_compare, compare_output, diff_output
'''


# 嵌入到生成脚本里的 LLM judge 块。
# 用 {judge_meta_prompt_repr} 注入 JUDGE_META_PROMPT 的 repr 形式，
# 这样生成脚本里 JUDGE_META_PROMPT 是一个普通 Python 字面量字符串，
# 内部的 {prompt_for_target} 占位符在运行期 .format() 时才会被替换。
_JUDGE_BLOCK = '''
from code.pipeline.llm_judge import DEFAULT_RUBRIC
from code.pipeline.llm_judge import judge_sample as _pipeline_judge_sample

def judge_sample(prompt_for_target, predicted, ground_truth, rubric=None, threshold=4):
    return _pipeline_judge_sample(
        _helper_llm, prompt_for_target, predicted, ground_truth,
        rubric=rubric, threshold=threshold,
    )
'''

_JUDGE_BLOCK_DISABLED = '''
DEFAULT_RUBRIC = []
def judge_sample(*args, **kwargs):
    return None
'''


def generate_eval_script(scenario_name: str, prompt_template: str,
                         eval_data: list, target_model_info: dict,
                         version: int = 1, max_workers: int = 8,
                         helper_info: dict = None,
                         use_llm_judge: bool = False,
                         judge_threshold: int = 4,
                         template_mode: str = "structural") -> str:
    """
    模板化生成评测脚本（结构 + 可选 LLM judge 双层）。

    参数:
        scenario_name: 场景名称
        prompt_template: prompt 模板
        eval_data: 评测数据集
        target_model_info: 目标模型信息（含 module_name）
        version: prompt 版本号
        max_workers: 并发数
        helper_info: helper 模型信息；非空时脚本内嵌 LLM judge
        use_llm_judge: 是否对每个样本都跑 judge；False 时仅在 all_skipped 时兜底跑
        judge_threshold: 综合分通过阈值
        template_mode: "structural" / "strict"，仅作为元信息保存
    """
    placeholders = extract_placeholders(prompt_template)
    module_name = target_model_info["module_name"]

    compare_block = _STRUCTURAL_COMPARE_BLOCK

    judge_enabled = bool(helper_info)
    if judge_enabled:
        helper_import = f"from code.models.{helper_info['module_name']} import llm_response as _helper_llm"
        judge_block = _JUDGE_BLOCK
    else:
        helper_import = "_helper_llm = None  # judge disabled"
        judge_block = _JUDGE_BLOCK_DISABLED

    script = f'''import os
import json
import re
import sys
import time
import concurrent.futures
from datetime import datetime
from tqdm import tqdm

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

from code.models.{module_name} import llm_response
from code.pipeline.prompt_generator import render_prompt_template
{helper_import}

TEMPLATE_MODE = {template_mode!r}
USE_LLM_JUDGE = {use_llm_judge!r}
JUDGE_THRESHOLD = {judge_threshold!r}
JUDGE_ENABLED = {judge_enabled!r}

ROOT_DIR = project_root
eval_dataset_file = os.path.join(ROOT_DIR, 'data', 'eval', '{scenario_name}.json')
with open(eval_dataset_file, "r", encoding="utf-8") as f:
    eval_dataset = json.load(f)

prompt_dir = os.path.join(ROOT_DIR, 'data', 'prompt', {scenario_name!r})

def resolve_prompt_file(prompt_dir, version):
    exact = os.path.join(prompt_dir, 'v' + str(version) + '.py')
    if os.path.exists(exact):
        return exact
    pattern = re.compile(r'^v' + re.escape(str(version)) + r'(?:\\.py|[^0-9].*\\.py)$')
    candidates = [
        os.path.join(prompt_dir, name)
        for name in os.listdir(prompt_dir)
        if pattern.match(name)
    ] if os.path.isdir(prompt_dir) else []
    if candidates:
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]
    raise FileNotFoundError('找不到 prompt 版本文件: ' + exact)

prompt_file = resolve_prompt_file(prompt_dir, {version!r})

def load_prompt_template(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'PROMPT_TEMPLATE\\s*=\\s*"""(.*?)"""', content, re.S)
    if not match:
        match = re.search(r'=\\s*"""(.*?)"""', content, re.S)
    if match:
        return match.group(1).replace('\\\\"\\\\"\\\\"', '"""')
    match = re.search(r"PROMPT_TEMPLATE\\s*=\\s*[']{{3}}(.*?)[']{{3}}", content, re.S)
    if not match:
        match = re.search(r"=\\s*[']{{3}}(.*?)[']{{3}}", content, re.S)
    if match:
        return match.group(1)
    raise ValueError("无法从 prompt 版本文件解析模板: " + path)

PROMPT_TEMPLATE = load_prompt_template(prompt_file)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
eval_dataset_result_file = os.path.join(
    ROOT_DIR, 'data', 'eval_result',
    '{scenario_name}_v{version}_result_' + timestamp + '.json'
)
os.makedirs(os.path.dirname(eval_dataset_result_file), exist_ok=True)

{_EXTRACT_JSON_FUNCTION}

{compare_block}

{judge_block}

def evaluate_accuracy():
    total = len(eval_dataset)

    def process_sample(i):
        result = {{"input": eval_dataset[i]["input"]}}
        temp_data = result["input"]
        try:
            formatted = render_prompt_template(PROMPT_TEMPLATE, temp_data)
        except KeyError as e:
            result["is_correct"] = False
            result["final_pass"] = False
            result["structural_pass"] = False
            result["error_reason"] = "格式化失败: " + str(e)
            result["time_cost"] = 0
            return result
        result["prompt"] = formatted

        response_json = None
        start_time = time.time()
        for times in range(3):
            try:
                response = llm_response(formatted)
                result["response_" + str(times)] = response
                if response is None:
                    result["response_json_" + str(times)] = None
                    continue
                response_json = extract_last_complete_json(response)
                if response_json is None:
                    response_json = coerce_single_text_response(response, eval_dataset[i]["output"])
                    if response_json is not None:
                        result["response_json_" + str(times) + "_coerced"] = True
                result["response_json_" + str(times)] = response_json
                if response_json is not None:
                    break
            except Exception as e:
                result["response_" + str(times)] = "Error: " + str(e)
                result["response_json_" + str(times)] = None
        result["time_cost"] = time.time() - start_time

        if response_json is None:
            result["is_correct"] = False
            result["final_pass"] = False
            result["structural_pass"] = False
            result["error_reason"] = "无法获取有效响应"
            return result

        ground_truth = eval_dataset[i]["output"]
        result["ground_truth"] = ground_truth

        sc = structural_compare(response_json, ground_truth)
        result["structural_pass"] = sc["hard_pass"]
        result["exact_match_pass"] = sc["pass"]
        result["hard_diffs"] = sc["hard_diffs"]
        result["semantic_needed"] = sc["semantic_needed"]
        result["semantic_diffs"] = sc["semantic_diffs"]
        result["semantic_compared_count"] = sc["semantic_compared_count"]
        result["all_skipped"] = sc["all_skipped"]
        result["structural_diffs"] = sc["diffs"]

        run_judge = JUDGE_ENABLED and (USE_LLM_JUDGE or sc["semantic_needed"] or sc["all_skipped"])
        if run_judge:
            jr = judge_sample(formatted, response_json, ground_truth, threshold=JUDGE_THRESHOLD)
            if jr is not None:
                result["judge_score"] = jr["overall"]
                result["judge_pass"] = jr["pass"]
                result["judge_reason"] = jr["reason"]
                result["judge_dimensions"] = jr["dimensions"]
            else:
                result["judge_pass"] = None
        else:
            result["judge_score"] = None
            result["judge_pass"] = None
            result["judge_reason"] = None

        if not sc["hard_pass"]:
            final_pass = False
        elif run_judge:
            final_pass = bool(result.get("judge_pass"))
        else:
            final_pass = sc["pass"]

        result["final_pass"] = final_pass
        result["is_correct"] = final_pass

        if not final_pass:
            parts = []
            if not sc["hard_pass"]:
                parts.append("结构: " + ("; ".join(sc["hard_diffs"]) or "硬结构字段不一致"))
            if sc["semantic_needed"]:
                if run_judge:
                    parts.append("语义文本: " + ("; ".join(sc["semantic_diffs"]) or "自然语言字段不一致"))
                else:
                    parts.append(
                        "语义待判: " + ("; ".join(sc["semantic_diffs"]) or "自然语言字段不一致")
                        + "（未配置 Helper Judge）"
                    )
            if sc["all_skipped"] and not run_judge and not sc["pass"]:
                parts.append("结构: 只有自然语言文本字段，未启用 LLM judge，无法判定")
            if run_judge and not result.get("judge_pass"):
                parts.append("语义: score=" + str(result.get("judge_score")) + ", reason=" + str(result.get("judge_reason") or ""))
            if parts:
                result["error_reason"] = "; ".join(parts)
        return result

    results = []
    correct = 0
    structural_eligible = 0
    structural_correct = 0
    semantic_eligible = 0
    semantic_correct = 0
    exact_match_correct = 0
    semantic_needed_count = 0
    semantic_override_correct = 0
    all_time = 0
    min_time = float('inf')
    max_time = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers={max_workers}) as executor:
        future_to_idx = {{executor.submit(process_sample, i): i for i in range(total)}}
        for future in tqdm(concurrent.futures.as_completed(future_to_idx), total=total):
            r = future.result()
            results.append(r)
            if r.get("final_pass") or r.get("is_correct"):
                correct += 1
            if r.get("exact_match_pass"):
                exact_match_correct += 1
            if r.get("semantic_needed"):
                semantic_needed_count += 1
                if r.get("judge_pass"):
                    semantic_override_correct += 1
            err_reason = r.get("error_reason") or ""
            if "structural_pass" in r and not r.get("all_skipped") and not err_reason.startswith(("格式化失败", "无法获取")):
                structural_eligible += 1
                if r["structural_pass"]:
                    structural_correct += 1
            if r.get("judge_pass") is not None:
                semantic_eligible += 1
                if r["judge_pass"]:
                    semantic_correct += 1
            tc = r.get("time_cost", 0)
            all_time += tc
            if tc > 0:
                min_time = min(min_time, tc)
            max_time = max(max_time, tc)

    if min_time == float('inf'):
        min_time = 0
    overall = correct / total if total > 0 else 0.0
    structural_acc = (structural_correct / structural_eligible) if structural_eligible else None
    semantic_acc = (semantic_correct / semantic_eligible) if semantic_eligible else None
    summary = {{
        "scenario_name": {scenario_name!r},
        "version": {version!r},
        "target_model": {target_model_info.get("model_name", module_name)!r},
        "helper_model": {helper_info.get("model_name") if helper_info else None!r},
        "template_mode": TEMPLATE_MODE,
        "judge_enabled": JUDGE_ENABLED,
        "use_llm_judge": USE_LLM_JUDGE,
        "judge_threshold": JUDGE_THRESHOLD,
        "total": total,
        "correct": correct,
        "overall_accuracy": overall,
        "structural_accuracy": structural_acc,
        "structural_eligible": structural_eligible,
        "semantic_accuracy": semantic_acc,
        "semantic_eligible": semantic_eligible,
        "semantic_correct": semantic_correct,
        "exact_match_accuracy": (exact_match_correct / total) if total else 0.0,
        "semantic_needed": semantic_needed_count,
        "semantic_overridden_correct": semantic_override_correct,
        "avg_time": all_time / total if total else 0,
        "min_time": min_time,
        "max_time": max_time,
        "created_at": timestamp,
    }}

    print()
    print("评测完成：")
    print("  总样本: " + str(total))
    print("  通过: " + str(correct))
    print("  综合准确率: " + "{{:.2%}}".format(overall))
    print("  逐字准确率: " + "{{:.2%}}".format(summary["exact_match_accuracy"]))
    print("  结构准确率: " + ("{{:.2%}}".format(structural_acc) if structural_acc is not None else "N/A"))
    if semantic_acc is not None:
        print("  语义准确率: " + "{{:.2%}}".format(semantic_acc))
    else:
        print("  语义准确率: N/A" + (" (judge 未启用)" if not JUDGE_ENABLED else ""))
    print("  模板模式: " + TEMPLATE_MODE)
    print("  平均耗时: " + "{{:.2f}}".format(all_time / total if total else 0) + "秒")
    print("  最小/最大耗时: " + "{{:.2f}}".format(min_time) + "秒 / " + "{{:.2f}}".format(max_time) + "秒")

    with open(eval_dataset_result_file, "w", encoding="utf-8") as f:
        json.dump({{"summary": summary, "samples": results}}, f, ensure_ascii=False, indent=4)
    print("结果已保存: " + eval_dataset_result_file)

if __name__ == "__main__":
    evaluate_accuracy()
'''
    return script
