import json


def print_banner():
    """打印欢迎横幅"""
    print("=" * 60)
    print("  Prompt 自动化调试与评测系统")
    print("  Virtual Coach - Prompt Engineering Pipeline")
    print("=" * 60)
    print()


def select_from_list(prompt: str, options: list, key=None) -> int:
    """
    显示编号选项列表，返回用户选择的索引。
    options 可以是字符串列表或字典列表（通过 key 指定显示字段）。
    """
    print(f"\n{prompt}:")
    for i, opt in enumerate(options):
        if key and isinstance(opt, dict):
            label = opt[key]
        elif isinstance(opt, str):
            label = opt
        else:
            label = str(opt)
        print(f"  [{i + 1}] {label}")
    while True:
        try:
            choice = int(input("请输入编号: ").strip()) - 1
            if 0 <= choice < len(options):
                return choice
        except (ValueError, EOFError):
            pass
        print("无效选择，请重试。")


def get_multiline_input(prompt: str) -> str:
    """读取多行输入，直到用户输入 </end> 结束。"""
    print(f"\n{prompt}（输入 </end> 结束）:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "</end>":
            break
        lines.append(line)
    return "\n".join(lines)


def get_single_input(prompt: str) -> str:
    """读取单行输入。"""
    return input(f"\n{prompt}: ").strip()


def confirm_or_edit(title: str, content: str) -> str:
    """
    显示内容，让用户确认、编辑或要求重新生成。
    返回最终内容，如果用户选择重新生成则返回 None。
    """
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    print(content)
    print(f"{'=' * 60}")
    while True:
        choice = input("\n[C] 确认  [E] 编辑  [R] 重新生成: ").strip().upper()
        if choice == 'C':
            return content
        elif choice == 'E':
            print("请输入修改后的内容（输入 </end> 结束）:")
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip() == "</end>":
                    break
                lines.append(line)
            new_content = "\n".join(lines)
            if new_content.strip():
                return new_content
            else:
                print("内容为空，保留原内容。")
                return content
        elif choice == 'R':
            return None
        else:
            print("无效选择，请输入 C/E/R。")


def confirm_or_edit_json(title: str, data: list) -> list:
    """
    显示JSON数据，让用户确认或编辑。
    返回最终的 list 数据，如果用户选择重新生成则返回 None。
    """
    content = json.dumps(data, ensure_ascii=False, indent=2)
    result = confirm_or_edit(title, content)
    if result is None:
        return None
    if result == content:
        return data
    try:
        parsed = json.loads(result)
        if isinstance(parsed, list):
            return parsed
        else:
            print("解析结果不是数组，保留原数据。")
            return data
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}，保留原数据。")
        return data


def display_results(results: dict):
    """显示评测结果摘要。"""
    print(f"\n{'=' * 60}")
    print("  评测结果")
    print(f"{'=' * 60}")
    print(f"  总样本数:  {results['total']}")
    print(f"  正确数:    {results['correct']}")
    print(f"  准确率:    {results['accuracy']:.2%}")
    if results.get("exact_match_accuracy") is not None:
        print(f"  逐字准确率: {results['exact_match_accuracy']:.2%}")
    if results.get("structural_accuracy") is not None:
        print(f"  结构准确率: {results['structural_accuracy']:.2%}")
    if results.get("semantic_eligible"):
        print(
            f"  语义复判:  {results.get('semantic_correct', 0)}/"
            f"{results.get('semantic_eligible', 0)}"
        )
    print(f"  平均耗时:  {results['avg_time']:.2f}秒")
    print(f"  最小耗时:  {results['min_time']:.2f}秒")
    print(f"  最大耗时:  {results['max_time']:.2f}秒")
    print(f"{'=' * 60}")


def display_error_analysis(analysis: dict):
    """显示错误分析结果。"""
    if not analysis["errors"]:
        print("\n所有样本全部正确!")
        return

    print(f"\n{'=' * 60}")
    print("  错误分析")
    print(f"{'=' * 60}")
    print(f"  错误模式统计:")
    for err_type, count in analysis["error_patterns"].items():
        if count > 0:
            print(f"    {err_type}: {count} 个")

    print(f"\n  错误样本详情:")
    for err in analysis["errors"]:
        print(f"\n  --- 样本 {err['sample_index']} ---")
        print(f"  错误类型: {err['error_type']}")
        print(f"  详情: {err['error_detail']}")
        if err.get("expected"):
            print(f"  期望输出: {json.dumps(err['expected'], ensure_ascii=False)}")
        if err.get("predicted"):
            print(f"  实际输出: {json.dumps(err['predicted'], ensure_ascii=False)}")
    print(f"{'=' * 60}")
