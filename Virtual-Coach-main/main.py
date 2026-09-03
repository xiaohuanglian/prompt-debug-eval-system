import os
import sys
import json

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from code.pipeline.cli_utils import (
    print_banner, select_from_list, get_multiline_input, get_single_input,
    confirm_or_edit, confirm_or_edit_json, display_results, display_error_analysis,
)
from code.pipeline.model_resolver import list_available_models, load_model
from code.pipeline.prompt_generator import generate_prompt_template, extract_placeholders
from code.pipeline.eval_data_generator import generate_eval_data_auto, generate_eval_data_from_seeds
from code.pipeline.eval_code_generator import generate_eval_script
from code.pipeline.eval_runner import run_evaluation
from code.pipeline.optimizer import analyze_errors, suggest_improvements, apply_improvements
from code.pipeline.version_manager import (
    VersionManager,
    build_scratch_scenario_name,
    is_generic_scratch_scenario_name,
    normalize_scenario_name,
)


def step_select_models(available_models: list) -> tuple:
    """Step 1: 选择 helper 和 target 模型。"""
    print("\n--- Step 1: 模型选择 ---")

    if len(available_models) == 0:
        print("错误: 没有找到可用模型。请先在 code/models/api_keys.py 中配置模型。")
        sys.exit(1)

    print(f"\n找到 {len(available_models)} 个可用模型。")

    helper_idx = select_from_list(
        "请选择 Helper 模型（用于生成 prompt、评测数据和优化建议）",
        available_models, key="model_name"
    )
    target_idx = select_from_list(
        "请选择 Target 模型（被评测的模型）",
        available_models, key="model_name"
    )

    helper_info = available_models[helper_idx]
    target_info = available_models[target_idx]

    print(f"\nHelper 模型: {helper_info['model_name']}")
    print(f"Target 模型: {target_info['model_name']}")

    helper_llm = load_model(helper_info)
    target_llm = load_model(target_info)

    # 并发数设置
    max_workers_input = input("\n请设置评测并发数 (直接回车默认为 8): ").strip()
    if max_workers_input:
        try:
            max_workers = max(1, int(max_workers_input))
        except ValueError:
            print("无效输入，使用默认值 8。")
            max_workers = 8
    else:
        max_workers = 8
    print(f"评测并发数: {max_workers}")

    return helper_llm, target_llm, helper_info, target_info, max_workers


def step_input_requirements() -> tuple:
    """Step 2: 输入场景名称和需求。"""
    print("\n--- Step 2: 需求输入 ---")

    scenario_name = normalize_scenario_name(
        get_single_input("请输入场景名称（例如 DecisionScenario6；临时测试请用 测试_具体用途）")
    )
    if not scenario_name:
        print("场景名称不能为空。")
        sys.exit(1)
    if is_generic_scratch_scenario_name(scenario_name):
        note = get_single_input("“测试”会复用同一个目录。请输入这次临时测试的具体用途")
        try:
            scenario_name = build_scratch_scenario_name(note)
        except ValueError as e:
            print(f"场景名称无效: {e}")
            sys.exit(1)
        print(f"临时测试场景名已设为: {scenario_name}")

    print("\n请描述你的 prompt 需求：")
    print("  - 这个 prompt 要完成什么任务？")
    print("  - 输入有哪些字段？各是什么类型？")
    print("  - 输出是什么格式（JSON字段）？")
    print("  - 有哪些规则或约束？")
    requirements = get_multiline_input("需求描述")

    if not requirements.strip():
        print("需求描述不能为空。")
        sys.exit(1)

    return scenario_name, requirements


def step_generate_prompt(helper_llm: callable, requirements: str) -> str:
    """Step 3 & 4: 生成 prompt 并让用户审查。"""
    print("\n--- Step 3: 自动生成 Prompt ---")

    while True:
        print("正在生成 prompt 模板...")
        try:
            prompt_template = generate_prompt_template(helper_llm, requirements)
        except RuntimeError as e:
            print(f"生成失败: {e}")
            choice = select_from_list("如何处理？", ["重试", "手动输入 prompt"])
            if choice == 0:
                continue
            else:
                prompt_template = get_multiline_input("请输入 prompt 模板")
                break

        print("\n--- Step 4: 审查 Prompt ---")
        result = confirm_or_edit("生成的 Prompt 模板", prompt_template)
        if result is None:
            print("重新生成...")
            continue
        else:
            prompt_template = result
            break

    # 显示检测到的占位符
    placeholders = extract_placeholders(prompt_template)
    if placeholders:
        print(f"\n检测到的输入占位符: {', '.join(placeholders)}")
    else:
        print("\n警告: 未检测到输入占位符 ({variable_name})，请确认模板是否正确。")

    return prompt_template


def step_generate_eval_data(helper_llm: callable, prompt_template: str,
                            requirements: str) -> list:
    """Step 5: 生成评测数据集。"""
    print("\n--- Step 5: 生成评测数据集 ---")

    mode = select_from_list(
        "评测数据生成方式",
        ["全自动生成（LLM 根据 prompt 理解生成）", "从种子样本扩充（你提供几个示例，LLM 扩展更多）"]
    )

    while True:
        try:
            if mode == 0:
                print("正在自动生成评测数据...")
                eval_data = generate_eval_data_auto(helper_llm, prompt_template, requirements)
            else:
                print("\n请输入种子样本（JSON数组格式）:")
                print('例如: [{"input": {...}, "output": {...}}, ...]')
                seeds_json = get_multiline_input("种子数据")
                print("正在扩充评测数据...")
                eval_data = generate_eval_data_from_seeds(
                    helper_llm, prompt_template, requirements, seeds_json
                )
        except (RuntimeError, ValueError) as e:
            print(f"生成失败: {e}")
            choice = select_from_list("如何处理？", ["重试", "手动输入评测数据"])
            if choice == 0:
                continue
            else:
                raw = get_multiline_input("请输入评测数据（JSON数组）")
                eval_data = json.loads(raw)
                break

        print(f"\n生成了 {len(eval_data)} 个评测样本。")
        result = confirm_or_edit_json("评测数据集", eval_data)
        if result is None:
            print("重新生成...")
            continue
        else:
            eval_data = result
            break

    return eval_data


def step_generate_eval_code(scenario_name: str, prompt_template: str,
                            eval_data: list, target_info: dict,
                            version: int, vm: VersionManager,
                            max_workers: int = 8,
                            helper_info: dict = None) -> str:
    """Step 6: 生成评测脚本。"""
    print("\n--- Step 6: 生成评测脚本 ---")

    eval_script = generate_eval_script(
        scenario_name, prompt_template, eval_data, target_info, version,
        max_workers, helper_info=helper_info
    )

    result = confirm_or_edit("评测脚本", eval_script)
    if result is not None:
        eval_script = result

    vm.save_eval_script(eval_script)
    return eval_script



def _regenerate_prompt_from_suggestions(helper_llm, prompt_template, suggestions,
                                         vm, scenario_name, target_info,
                                         version, max_workers):
    """根据修改意见重新生成 prompt，返回 (new_prompt_template, new_version)。
    注意：不在此函数内生成评测脚本，由调用方在评测数据最终确定后再生成。"""
    while True:
        print("\n正在根据修改意见重新生成 prompt...")
        try:
            new_prompt = apply_improvements(helper_llm, prompt_template, suggestions)
        except RuntimeError as e:
            print(f"自动生成失败: {e}，保留原 prompt。")
            return prompt_template, version

        result = confirm_or_edit("根据修改意见重新生成的 Prompt（请审查）", new_prompt)
        if result is None:
            # 用户选了"重新生成" → 重试
            print("重新生成...")
            continue

        new_prompt = result
        new_version = vm.save_version(new_prompt)
        print(f"已保存为 v{new_version}")
        return new_prompt, new_version


def _regenerate_eval_script(scenario_name, prompt_template, eval_data,
                             target_info, version, vm, max_workers, helper_info=None):
    """在评测数据最终确定后，生成匹配的评测脚本。"""
    eval_script = generate_eval_script(
        scenario_name, prompt_template, eval_data, target_info, version, max_workers,
        helper_info=helper_info
    )
    vm.save_eval_script(eval_script)
    return eval_script


def _maybe_regenerate_eval_data(helper_llm, prompt_template, requirements, vm):
    """询问用户是否重新生成评测数据，返回新的 eval_data 或 None（表示不重新生成）。"""
    print("\nPrompt 已更新。评测数据是基于旧 prompt 生成的，建议同步更新。")
    choice = select_from_list("是否重新生成评测数据？", [
        "是，根据新 prompt 重新生成评测数据",
        "否，继续使用现有评测数据",
    ])
    if choice == 0:
        new_data = step_generate_eval_data(helper_llm, prompt_template, requirements)
        vm.save_eval_data(new_data)
        return new_data
    return None


def step_run_eval_and_optimize(helper_llm: callable, target_llm: callable,
                               prompt_template: str, eval_data: list,
                               scenario_name: str, version: int,
                               vm: VersionManager, target_info: dict,
                               requirements: str,
                               max_workers: int = 8,
                               helper_info: dict = None) -> None:
    """评测 → 分析 → 优化 → 循环。"""
    while True:
        # ── 运行评测 ──
        print(f"\n{'=' * 60}")
        print(f"  运行评测 (v{version})")
        print(f"{'=' * 60}")
        result_path = vm.get_result_path(version)
        results = run_evaluation(
            target_llm, prompt_template, eval_data,
            scenario_name, version, result_path, max_workers,
            helper_llm=helper_llm
        )
        display_results(results)

        # ── 错误分析 ──
        print(f"\n{'=' * 60}")
        print(f"  错误分析")
        print(f"{'=' * 60}")
        error_analysis = analyze_errors(results, eval_data)
        display_error_analysis(error_analysis)

        # ── 有错误：LLM 建议 → 合并用户意见 → 自动生成新 prompt ──
        if error_analysis["errors"]:
            print("\n正在生成 LLM 优化建议...")
            suggestions = suggest_improvements(helper_llm, prompt_template, error_analysis)
            print(f"\n{'─' * 60}")
            print("  LLM 优化建议")
            print(f"{'─' * 60}")
            print(suggestions)
            print(f"{'─' * 60}")

            print("\n你可以在 LLM 建议基础上补充修改意见（直接回车跳过）。")
            extra = get_multiline_input("补充修改意见")
            if extra.strip():
                suggestions = suggestions + "\n\n--- 用户补充意见 ---\n" + extra.strip()

            prompt_template, version = _regenerate_prompt_from_suggestions(
                helper_llm, prompt_template, suggestions,
                vm, scenario_name, target_info, version, max_workers
            )

            new_data = _maybe_regenerate_eval_data(helper_llm, prompt_template, requirements, vm)
            if new_data is not None:
                eval_data = new_data
            _regenerate_eval_script(scenario_name, prompt_template, eval_data,
                                    target_info, version, vm, max_workers, helper_info=helper_info)

        # ── 全对：弹窗输入修改意见 → 自动生成新 prompt ──
        else:
            prev = vm.load_manual_suggestions()
            if prev:
                print(f"\n之前保存的修改意见:\n{'─' * 40}\n{prev}\n{'─' * 40}")

            print("\n✓ 所有样本通过！")
            print("如有优化想法，请输入修改意见，系统将据此自动生成新版 prompt。")
            manual_input = get_multiline_input("修改意见")
            if not manual_input.strip():
                print("\n未输入修改意见。")
                action = select_from_list("请选择", [
                    "重新评测（使用当前 prompt 再跑一次）",
                    "手动编辑当前 prompt",
                    "结束优化，保留当前结果",
                ])
                if action == 0:
                    continue
                elif action == 1:
                    result = confirm_or_edit("当前 Prompt (请修改)", prompt_template)
                    if result is not None and result != prompt_template:
                        prompt_template = result
                        version = vm.save_version(prompt_template)
                        print(f"已保存为 v{version}")
                    continue
                else:
                    break

            vm.save_manual_suggestions(manual_input.strip())

            enriched = suggest_improvements(
                helper_llm, prompt_template, error_analysis,
                manual_suggestions=manual_input.strip(),
            )

            prompt_template, version = _regenerate_prompt_from_suggestions(
                helper_llm, prompt_template, enriched,
                vm, scenario_name, target_info, version, max_workers
            )

            new_data = _maybe_regenerate_eval_data(helper_llm, prompt_template, requirements, vm)
            if new_data is not None:
                eval_data = new_data
            _regenerate_eval_script(scenario_name, prompt_template, eval_data,
                                    target_info, version, vm, max_workers, helper_info=helper_info)

        # ── 下一轮评测 ──
        print(f"\n→ 准备用 v{version} 重新评测...")


def main():
    print_banner()

    # Step 1: 模型选择
    available_models = list_available_models()
    helper_llm, target_llm, helper_info, target_info, max_workers = step_select_models(available_models)

    # Step 2: 需求输入
    scenario_name, requirements = step_input_requirements()
    vm = VersionManager(scenario_name)

    # 检查是否有已有版本，支持续接
    existing_versions = vm.list_versions()
    if existing_versions:
        print(f"\n发现场景 '{scenario_name}' 已有版本: {', '.join(f'v{v}' for v in existing_versions)}")
        choice = select_from_list("如何处理？", [
            "从头开始（新建 prompt）",
            f"从最新版本 v{existing_versions[-1]} 继续优化",
            f"选择特定版本继续优化",
        ])
        if choice in (1, 2):
            # 选择版本
            if choice == 1:
                resume_v = existing_versions[-1]
            else:
                version_options = [f"v{v}" for v in existing_versions]
                idx = select_from_list("选择要继续优化的版本", version_options)
                resume_v = existing_versions[idx]

            prompt_template = vm.load_version(resume_v)
            version = resume_v
            print(f"\n已加载 v{version} 的 prompt。")

            # 加载已有评测数据
            try:
                eval_data = vm.load_eval_data()
                print(f"已加载评测数据 ({len(eval_data)} 个样本)。")
            except FileNotFoundError:
                print("未找到已有评测数据，需要重新生成。")
                eval_data = step_generate_eval_data(helper_llm, prompt_template, requirements)
                vm.save_eval_data(eval_data)

            # ─── 续接：弹窗输入修改意见 → 自动优化 prompt → 走完整流程 ───
            # 检查是否已有完整的评测资产（数据+脚本+结果），决定提示文案
            has_results = False
            result_dir = os.path.join(vm.root_dir, "data", "eval_result")
            if os.path.isdir(result_dir):
                scenario_results = [f for f in os.listdir(result_dir)
                                    if f.startswith(scenario_name)]
                has_results = len(scenario_results) > 0

            print(f"\n{'─' * 50}")
            print(f"  续接场景: {scenario_name} (v{version})")
            print(f"  评测数据: {len(eval_data)} 样本")
            print(f"  评测结果: {'有' if has_results else '无'}")
            print(f"{'─' * 50}")

            # 直接弹窗让用户输入修改意见
            if has_results:
                print("\n该场景已有完整评测结果。请输入修改意见，系统将据此自动优化 prompt。")
            else:
                print("\n请输入修改意见，系统将据此自动优化 prompt（直接回车则使用当前 prompt 进入评测）。")

            manual_input = get_multiline_input("修改意见")
            if manual_input.strip():
                vm.save_manual_suggestions(manual_input.strip())

                # 用修改意见生成优化建议，再自动改写 prompt
                print("\n正在分析修改意见并优化 prompt...")
                dummy_analysis = {"total": 0, "correct": 0, "accuracy": 0.0, "errors": []}
                enriched = suggest_improvements(
                    helper_llm, prompt_template, dummy_analysis,
                    manual_suggestions=manual_input.strip(),
                )

                prompt_template, version = _regenerate_prompt_from_suggestions(
                    helper_llm, prompt_template, enriched,
                    vm, scenario_name, target_info, version, max_workers
                )

                # 询问是否重新生成评测数据
                new_data = _maybe_regenerate_eval_data(helper_llm, prompt_template, requirements, vm)
                if new_data is not None:
                    eval_data = new_data
                _regenerate_eval_script(scenario_name, prompt_template, eval_data,
                                        target_info, version, vm, max_workers, helper_info=helper_info)
            else:
                print("\n未输入修改意见，将使用当前 prompt 直接进入评测。")

            # 进入评测循环
            step_run_eval_and_optimize(
                helper_llm, target_llm, prompt_template, eval_data,
                scenario_name, version, vm, target_info, requirements,
                max_workers, helper_info=helper_info
            )
            return

    # Step 3 & 4: 生成 prompt 并审查
    prompt_template = step_generate_prompt(helper_llm, requirements)
    version = vm.save_version(prompt_template)
    print(f"Prompt 已保存为 v{version}")

    # Step 5: 生成评测数据
    eval_data = step_generate_eval_data(helper_llm, prompt_template, requirements)
    vm.save_eval_data(eval_data)

    # Step 6: 生成评测脚本
    step_generate_eval_code(
        scenario_name, prompt_template, eval_data, target_info, version, vm,
        max_workers, helper_info=helper_info
    )

    # 评测 → 优化循环
    step_run_eval_and_optimize(
        helper_llm, target_llm, prompt_template, eval_data,
        scenario_name, version, vm, target_info, requirements,
        max_workers, helper_info=helper_info
    )


if __name__ == "__main__":
    main()
