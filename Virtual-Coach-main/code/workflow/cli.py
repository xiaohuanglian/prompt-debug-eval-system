import argparse
import uuid

from logger import JsonLogger
from utils import _read_json, _write_json
from planner import LLMPlanner
from default_config import default_user_standardized_output, max_iteration

def cli_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demand", type=str, default=None)
    parser.add_argument("--example", type=str, default=None)
    args = parser.parse_args()

    run_id = str(uuid.uuid4())
    log_path = f"workflow_log_{run_id}.json"  # 推荐 jsonl 后缀
    log_jsonl_path = f"workflow_log_{run_id}.jsonl"
    logger = JsonLogger(log_path, run_id)
    planner = LLMPlanner(logger)

    # 关键：告诉外部系统日志在哪（FastAPI 会读 stdout 抓这个）
    print(f"RUN_ID={run_id}", flush=True)
    print(f"LOG_JSONL={log_jsonl_path}", flush=True)

    # 1) 输入来源：优先命令行参数，否则走原来的交互输入
    user_input = args.demand if args.demand is not None else input("请输入你的需求: ")
    user_standardized_output_path = args.example if args.example is not None else None

    if not user_standardized_output_path:
        user_standardized_output_path = default_user_standardized_output

    user_standardized_output = _read_json(user_standardized_output_path)

    logger.log("开始运行", {
        "用户输入的需求": user_input,
        "用户标准化输出例子路径": user_standardized_output_path,
        "用户标准化输出例子": user_standardized_output
    })

    # 基本工作流生成
    plan = None
    for i in range(max_iteration):
        it_id = "第" + str(i+1) + "轮/共" + str(max_iteration) + "轮"
        retrieved_docs = {"user_standardized_output": user_standardized_output} if i == 0 else plan

        plan = planner.plan(user_input, retrieved_docs, i)
        logger.log(it_id + "工作流生成完成", plan)

        if plan.get("need_more_knowledge") is False:
            break

    if plan and "workflow_draft" in plan.keys():
        _write_json("workflow.json", plan.get("workflow_draft"))
        logger.log(it_id + "工作流保存结果", {
            "save_path": "workflow.json",
            "workflow_draft": plan["workflow_draft"]
        })
    
    # 测试输入工作流生成
    retrieved_docs = plan
    retrieved_docs["with_test_input"] = True
    plan_with_test_input = planner.test_input_plan(user_input, retrieved_docs, plan["workflow_draft"])
    plan_with_test_input["own_test_input"] = True
    logger.log("测试用工作流和测试输入生成完成", plan_with_test_input)
    
        
    if plan_with_test_input and "workflow_draft_for_test" in plan_with_test_input.keys() and "test_input" in plan_with_test_input.keys():
        _write_json("workflow_test_input.json", plan_with_test_input.get("workflow_draft_for_test"))
        _write_json("test_input.json", plan_with_test_input.get("test_input"))
        logger.log("测试用工作流保存结果", {
            "save_path": "workflow_test_input.json",
            "workflow_draft_for_test": plan_with_test_input["workflow_draft_for_test"],
        })
        logger.log("测试输入保存结果", {
            "save_path": "test_input.json",
            "test_input": plan_with_test_input["test_input"]    
        })
    

if __name__ == "__main__":
    cli_main()