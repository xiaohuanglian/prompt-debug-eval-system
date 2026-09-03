import json
import uuid

from logger import JsonLogger
from utils import _read_json, _write_json
from planner import LLMPlanner
from default_config import default_user_standardized_output, default_knewledge, max_iteration

def cli_main():
    # 初始化
    run_id = str(uuid.uuid4())
    logger = JsonLogger(f"workflow_log_{run_id}.json", run_id)
    planner = LLMPlanner(logger)

    # 1. 获得用户输入的需求和标准化输出例子
    user_input = input("请输入你的需求: ")
    user_standardized_output = input("请输入你的标准化输出例子所在路径（回车则使用默认路径）: ")
    if not user_standardized_output:
        user_standardized_output = default_user_standardized_output
    user_standardized_output = _read_json(user_standardized_output)
    logger.log(
        "开始运行", 
        {
            "用户输入的需求": user_input, 
            "用户标准化输出例子": user_standardized_output
        }
    )

    for i in range(max_iteration):
        # 2. 生成工作流
        if i == 0:
            retrieved_docs = {"user_standardized_output": user_standardized_output}
        else:
            retrieved_docs = plan
        
        plan = planner.plan(user_input, retrieved_docs, i)
        logger.log(
            "工作流生成完成", 
            plan
        )
        if "need_more_knowledge" in plan:
            if plan["need_more_knowledge"] == False:
                break

        # 3. 验证工作流
        #issues = validate_workflow_file(plan.workflow_draft)
        #logger.log("工作流验证结果", {"工作流": plan.workflow_draft, "验证结果": issues})

    # 4. 保存工作流
    if "workflow_draft" in plan:    
        _write_json(plan["workflow_draft"], "workflow.json")
        logger.log("工作流保存结果", 
        {"工作流": plan["workflow_draft"]})

if __name__ == "__main__":
    cli_main()