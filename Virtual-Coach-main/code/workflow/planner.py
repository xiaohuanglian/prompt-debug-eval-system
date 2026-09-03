from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from decision_trace import TraceStep
from logger import JsonLogger
from retruever import Retriever
from llm_api import llm_chat
from utils import _parse_llm_json


@dataclass
class PlanResult:
    workflow_draft: Dict[str, Any] # 工作流草案
    confidence: float # 信心度
    need_more_knowledge: bool # 是否需要更多知识
    own_test_input: bool # 是否拥有自己的测试输入
    knowledge_queries: List[Dict[str, Any]] # 知识查询
    reasoning_trace: str # 推理追踪

@dataclass
class TestInputPlanResult:
    workflow_draft_for_test: Dict[str, Any] # 测试输入工作流草案
    test_input: Dict[str, Any] # 测试输入
    confidence: float # 信心度
    own_test_input: bool # 是否拥有自己的测试输入
    reasoning_trace: str # 推理追踪


class BasePlanner:
    def plan(self, requirement: str, retrieved_docs: List[Dict[str, Any]] = None, iteration: int = 0) -> PlanResult:
        raise NotImplementedError

class LLMPlanner(BasePlanner):
    def __init__(self, logger: JsonLogger):
        self.logger = logger
        self.retriever = Retriever()
    
    def _check_plan_result(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        return_flag = True
        return_reason = "[格式化验证]"

        if "workflow_draft" not in result:
            return_flag = False
            return_reason += "workflow_draft 不存在;"
        elif not isinstance(result["workflow_draft"], dict):
            return_flag = False
            return_reason += "workflow_draft 不是 dict;"
        
        if "confidence" not in result:
            return_flag = False
            return_reason += "confidence 不存在;"
        elif not isinstance(result["confidence"], float):
            return_flag = False
            return_reason += "confidence 不是 float;"
        
        if "need_more_knowledge" not in result:
            return_flag = False
            return_reason += "need_more_knowledge 不存在;"
        elif not isinstance(result["need_more_knowledge"], bool):
            return_flag = False
            return_reason += "need_more_knowledge 不是 bool;"
        
        if "knowledge_queries" not in result:
            return_flag = False
            return_reason += "knowledge_queries 不存在;"
        elif not isinstance(result["knowledge_queries"], list):
            return_flag = False
            return_reason += "knowledge_queries 不是 list;"
        
        if "reasoning_trace" not in result:
            return_flag = False
            return_reason += "reasoning_trace 不存在;"
        elif not isinstance(result["reasoning_trace"], str):
            return_flag = False
            return_reason += "reasoning_trace 不是 str;"
        
        return return_flag, return_reason

    def _check_test_input_plan_result(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        return_flag = True
        return_reason = "[格式化验证]"

        if "workflow_draft_for_test" not in result:
            return_flag = False
            return_reason += "workflow_draft_for_test 不存在;"
        elif not isinstance(result["workflow_draft_for_test"], dict):
            return_flag = False
            return_reason += "workflow_draft_for_test 不是 dict;"
        

        if "test_input" not in result:
            return_flag = False
            return_reason += "test_input 不存在;"
        elif not isinstance(result["test_input"], dict):
            return_flag = False
            return_reason += "test_input 不是 dict;"
        
        if "confidence" not in result:
            return_flag = False
            return_reason += "confidence 不存在;"
        elif not isinstance(result["confidence"], float):
            return_flag = False
            return_reason += "confidence 不是 float;"
        
        if "reasoning_trace" not in result:
            return_flag = False
            return_reason += "reasoning_trace 不存在;"
        elif not isinstance(result["reasoning_trace"], str):
            return_flag = False
            return_reason += "reasoning_trace 不是 str;"
        
        return return_flag, return_reason

    def _get_prompt(self, template: str, requirement: str, retrieved_docs: Dict[str, Any], workflow_json: Dict[str, Any] = None) -> str:
        retrieved_docs_text = ""
        for key in retrieved_docs.keys():
            retrieved_docs_text += f"【{key}】\n{retrieved_docs[key]}\n"
        if workflow_json == None:
            return template.format(requirement=requirement, docs=retrieved_docs_text)
        else:
            return template.format(requirement=requirement, docs=retrieved_docs_text, workflow_json=workflow_json)
    
    def _analyze_retrieved_docs(self, retrieved_docs: Dict[str, Any]) -> Dict[str, Any]:
        if "user_standardized_output" in retrieved_docs:
            retrieved_docs["need_more_knowledge"] = True
            retrieved_docs["knowledge_queries"] = [
                {"query": "workflow.base", "reason": "first"}, {"query": "node.base", "reason": "first"}]
        elif "with_test_input" in retrieved_docs:
            retrieved_docs["need_more_knowledge"] = True
            retrieved_docs["knowledge_queries"] = [
                {"query": "workflow.base", "reason": "test_input"}, {"query": "node.base", "reason": "test_input"}]

        new_retrieved_docs = {
            "last_result": retrieved_docs,
            "retrieved_docs": ""
        }

        if "need_more_knowledge" in retrieved_docs:
            if retrieved_docs["need_more_knowledge"]:
                for query_item in retrieved_docs["knowledge_queries"]:
                    query = query_item["query"]
                    split_query = query.split(".")
                    if len(split_query) < 2:
                        knowledge_content = f"无法解析的知识查询格式: {query}"
                        first_level_key = split_query[0] if len(split_query) > 0 else "未知"
                        second_level_key = "未知"
                    else:
                        first_level_key = split_query[0]
                        second_level_key = split_query[1]
                        knowledge_content = self.retriever.get_knowledge_content(first_level_key, second_level_key)
                    new_retrieved_docs["retrieved_docs"] += f"\n【{first_level_key}.{second_level_key}】\n{knowledge_content}"

        return new_retrieved_docs


    def plan(self, requirement: str, retrieved_docs: Dict[str, Any] = None, iteration: int = 0) -> PlanResult:
        print("plan_iteration: ", iteration)

        it_id = "第" + str(iteration+1) + "轮"

        template = self.retriever.get_base_knowledge_content()
        new_retrieved_docs = self._analyze_retrieved_docs(retrieved_docs)
        prompt = self._get_prompt(template, requirement, new_retrieved_docs)


        retry_count = 5
        i = 0
        while i < retry_count:
            try:
                raw = llm_chat(prompt)
                self.logger.log(it_id + "LLMPlanner请求LLM成功", 
                {
                    "请求内容": prompt, 
                    "请求次数": i,
                    "总请求次数": retry_count,
                    "响应内容": raw
                
                })
            except Exception as e:
                self.logger.error(it_id + "LLMPlanner请求失败", 
                {
                    "请求内容": prompt, 
                    "请求次数": i,
                    "总请求次数": retry_count,
                    "错误原因": e
                })
                continue
            
            try:
                result = _parse_llm_json(raw)
                self.logger.log(it_id + "LLMPlanner解析LLM响应成功", 
                {
                    "解析结果": result
                })
            except Exception as e:
                self.logger.error(it_id + "LLMPlanner解析LLM响应失败",
                {
                    "响应内容": raw,
                    "错误原因": str(e)
                })
                continue
            
            try:
                return_flag, return_reason = self._check_plan_result(result)
                if not return_flag:
                    self.logger.error(it_id + "LLMPlanner检查格式存在错误",
                    {
                        "格式具体错误": return_reason
                    })
                    last_prompt = prompt
                    prompt =  f"\n【上一次生成结果】\n {last_prompt} \n 【格式问题】\n {return_reason}"
                else:
                    return result
            except Exception as e:
                self.logger.error(it_id + "LLMPlanner检查格式存在错误",
                {
                    "错误原因": str(e)
                })
                
            i += 1
    
        return PlanResult(
            workflow_draft={},
            confidence=0,
            need_more_knowledge=True,
            own_test_input=False,
            knowledge_queries=[],
            reasoning_trace=""
        )


    def test_input_plan(self, requirement: str, retrieved_docs: Dict[str, Any] = None, workflow_json: Dict[str, Any] = None, iteration: int = 0) -> PlanResult:
        print("test_input_plan_iteration: ", iteration)
        
        template = self.retriever.get_test_input_knowledge_content()
        new_retrieved_docs = self._analyze_retrieved_docs(retrieved_docs)
        prompt = self._get_prompt(template, requirement, new_retrieved_docs, workflow_json)

        retry_count = 5
        i = 0
        while i < retry_count:
            try:
                raw = llm_chat(prompt)
                self.logger.log("TestInputPlanner请求LLM成功", 
                {
                    "请求内容": prompt, 
                    "请求次数": i,
                    "总请求次数": retry_count,
                    "响应内容": raw
                
                })
            except Exception as e:
                self.logger.error("TestInputPlanner请求失败", 
                {
                    "请求内容": prompt, 
                    "请求次数": i,
                    "总请求次数": retry_count,
                    "错误原因": e
                })
                continue
            
            try:
                result = _parse_llm_json(raw)
                self.logger.log("TestInputPlanner解析LLM响应成功", 
                {
                    "解析结果": result
                })
            except Exception as e:
                self.logger.error("TestInputPlanner解析LLM响应失败",
                {
                    "响应内容": raw,
                    "错误原因": str(e)
                })
                continue

            try:
                return_flag, return_reason = self._check_test_input_plan_result(result)
                if not return_flag:
                    self.logger.error("TestInputPlanner检查格式存在错误",
                    {
                        "格式具体错误": return_reason
                    })
                    last_prompt = prompt
                    prompt =  f"\n【上一次生成结果】\n {last_prompt} \n 【格式问题】\n {return_reason}"
                else:
                    return result
            except Exception as e:
                self.logger.error("TestInputPlanner检查格式存在错误",
                {
                    "错误原因": str(e)
                })
                
            i += 1
    
        return TestInputPlanResult(
            workflow_draft_for_test={},
            test_input={},
            confidence=0,
            reasoning_trace=""
        )
