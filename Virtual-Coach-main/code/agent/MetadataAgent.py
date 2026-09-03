import os
import json
import re
import ast
import importlib
import shutil
from tqdm import tqdm
from typing import Any, Dict, List, Tuple, Union, Mapping, Callable, Literal

from ..prompts.metadata_agent import ch_to_en_en, en_to_ch_en, generate_constant_based_on_induction_en, generate_cases_by_deduction_en, get_answer_en, check_answer_en, generate_variables_by_analogy_en, validate_variables_en

# define the JSON-style data types that are accepted
JSONType = Union[
    Dict[str, Any],
    List[Any],
    Tuple[Any, ...],
    str, int, float, bool, None
]

class MetadataAgent:
    def __init__(self, metadata_name: str, model_name: str = "glm-4-air"):
        """初始化元数据智能体。"""

        self.model_name = model_name

        # 当前文件（MetadataAgent.py）所在目录
        self.CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

        self.metadata_name = metadata_name # 元数据的名称
        temp_metadata_name = re.sub(r'[^a-zA-Z0-9]', '_', metadata_name).lower()

        self.metadata_file = f"{self.CURRENT_DIR}/metadata/{temp_metadata_name}.json"     # 保存路径
        if not os.path.exists(self.metadata_file):
            os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)

        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Failed to load {self.metadata_file}: {e}")
                self.metadata = {}
        else:
            self.metadata = {} # 元数据字典

        if self.metadata:
            self.constant = self.metadata.get("constant", "")
            self.variable = self.metadata.get("variable", [])
            self.cases = self.metadata.get("cases", [])
        else:
            self.metadata = {
                "metadata_name": metadata_name,
                "constant": "",
                "variable": [],
                "cases": []
            }
            self.constant = "" # 基本常量描述
            self.variable = [] # 泛化性变量列表，每个元素为字典
            self.cases = [] # 特定问题样例列表，每个元素为字典
    
    def get_llm_response(self, prompt, model_name):
        """
        直接处理LLM响应的函数
        """
        model_name_str = re.sub(r'[^a-zA-Z0-9]', '_', model_name).lower()
        try:
            model_module = importlib.import_module(f"..models.{model_name_str}", package=__name__)
            return model_module.llm_response(prompt)
        except Exception as e:
            print(f"Error in get_llm_response: {e}")
            return None
    
    def extract_last_complete_json(self, text: str):
        """
        提取文本中的最后一个完整的JSON对象
        """
        _CODE_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.S)

        def _try_load(blob: str):
            try:
                return json.loads(blob)
            except json.JSONDecodeError:
                return None

        # ---------- 1) 先看 ```json``` 代码块 ----------
        for block in reversed(_CODE_BLOCK_RE.findall(text)):
            obj = _try_load(block)
            if obj is not None:
                return obj                    # 嵌套无限制

        # ---------- 2) 从后往前定位 {...} ----------
        dec = json.JSONDecoder()
        i = len(text)                         # 右端游标
        depth = 0
        in_string = False
        escape = False

        # 反向扫描，找到最外层 '{' 对应的索引 start
        for i in range(len(text) - 1, -1, -1):
            ch = text[i]

            # 维护 in_string / escape 状态，忽略字符串内部的大括号
            if in_string:
                escape = (ch == '\\') and not escape
                if ch == '"' and not escape:
                    in_string = False
                continue
            else:
                if ch == '"':
                    in_string = True
                    continue

            if ch == '}':
                depth += 1
            elif ch == '{':
                depth -= 1
                if depth == 0:                # 找到闭合
                    candidate = text[i:]
                    obj = _try_load(candidate)
                    if obj is not None:
                        return obj            # 支持任意嵌套
                    # 否则继续向左找上一层可能的 '{'

        return None

    def ch_to_en(self, text: str):
        """
        将中文翻译为英文
        """
        prompt = ch_to_en_en.format(text=text)
        for _ in range(5):  # 最多尝试5次，避免死循环
            response = self.get_llm_response(prompt, self.model_name)
            if not response:
                continue
            extracted_json = self.extract_last_complete_json(response)
            if not extracted_json:
                continue
            en_text = extracted_json.get("en")
            if en_text:
                return en_text
        raise RuntimeError("翻译失败：无法从LLM响应中提取英文内容。")
    
    def en_to_ch(self, text: str):
        """
        将英文转换为中文
        """
        prompt = en_to_ch_en.format(text=text)
        for _ in range(5):  # 最多尝试5次，避免死循环
            response = self.get_llm_response(prompt, self.model_name)
            if not response:
                continue
            extracted_json = self.extract_last_complete_json(response)
            if not extracted_json:
                continue
            ch_text = extracted_json.get("ch")
            if ch_text:
                return ch_text
        raise RuntimeError("翻译失败：无法从LLM响应中提取中文内容。")

    def set_metadata_name(self, metadata_name: str):
        """设置元数据的名称。"""
        self.metadata_name = metadata_name
        self.metadata["metadata_name"] = metadata_name
        temp_metadata_name = re.sub(r'[^a-zA-Z0-9]', '_', metadata_name).lower()
        # 将旧的文件重命名
        if os.path.exists(self.metadata_file):
            os.rename(self.metadata_file, f"{self.CURRENT_DIR}/metadata/{temp_metadata_name}.json")
        self.metadata_file = f"{self.CURRENT_DIR}/metadata/{temp_metadata_name}.json"     # 保存路径

        self.save_metadata()
    
    def get_metadata_name(self):
        """获取元数据的名称。"""
        return self.metadata_name

    def set_constant(self, constant: str):
        """设置元数据的基本常量描述。"""
        if constant != self.constant:
            self.constant = constant
            self.metadata["constant"] = constant
            self.save_metadata()
    
    def get_constant(self):
        """获取元数据的基本常量描述。"""
        return self.constant
    
    def add_variable(self, name: str, description: str, min_value, max_value, step, variant=None):
        """添加一个泛化性变量。"""
        if min_value is None or max_value is None or step is None:
            print(f"Warning: min_value, max_value, step should be numbers, but got {min_value}, {max_value}, {step}")
            return

        param_info = {
            "name": name,
            "description": description,
            "min": min_value,
            "max": max_value,
            "step": step
        }
        if variant:
            param_info["variant"] = variant  # 如果提供了变体信息，则添加该字段
        
        # 如果变量列表中已经存在该变量，则更新该变量
        for param in self.variable:
            if param["name"] == name:
                param.update(param_info)  # 使用update方法一次性更新所有字段
                break
        else:
            self.variable.append(param_info)
        
        self.metadata["variable"] = self.variable
        self.save_metadata()
    
    def add_variable_by_dict(self, param_info: dict):
        """添加一个泛化性变量。"""
        self.add_variable(param_info["name"], param_info["description"], param_info["min"], param_info["max"], param_info["step"], param_info.get("variant", None))
    
    def add_variable_by_list(self, param_info_list: list):
        """添加多个泛化性变量。"""
        for param_info in param_info_list:
            self.add_variable_by_dict(param_info)
    
    def set_variable(self, variable: list):
        """设置元数据的泛化性变量列表。"""
        self.variable = variable
        self.metadata["variable"] = self.variable
        self.save_metadata()
    
    def get_variable(self):
        """获取元数据的泛化性变量列表。"""
        return self.variable
    
    def add_case(self, metadata, question, answer):
        """添加一个具体的元数据样例。"""
        case = {"metadata": metadata, "question": question, "answer": answer}
        
        # 如果样例列表中已经存在该样例，则更新该样例
        for ex in self.cases:
            if ex["metadata"] == metadata and ex["question"] == question:
                if ex["answer"] == answer:
                    return
                else:
                    ex.update(case)
                    break
    
        self.cases.append(case)    
        self.metadata["cases"] = self.cases
        self.save_metadata()
    
    def add_case_by_dict(self, case_info: dict):
        """添加一个具体的元数据样例。"""
        self.add_case(case_info["metadata"], case_info["question"], case_info["answer"])
    
    def add_case_by_list(self, case_info_list: list):
        """添加多个具体的元数据样例。"""
        for case_info in case_info_list:
            self.add_case_by_dict(case_info)
            
    def get_cases(self):
        """获取元数据的样例列表。"""
        return self.cases
    
    def set_cases(self, cases: list):
        """设置元数据的样例列表。"""
        self.cases = cases
        self.metadata["cases"] = self.cases
        self.save_metadata()
    
    def save_metadata(self):
        """保存元数据到 JSON 文件。"""
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=4)

    def get_metadata(self):
        """获取元数据。"""
        return self.metadata
    
    def add_key_value(self, key: str, value):
        """添加一个键值对。"""
        self.metadata[key] = value
        self.save_metadata()

    def collect_metadata(self, url: str):
        """从指定网页收集元数据，模拟网页解析。更新基础常量、变量列表和样例列表。"""
        html_content = ""
        if "case.com/metadata-metadata" in url:
            # 使用预定义的示例网页内容（模拟从指定 URL 获取的数据）
            html_content = """
            <html>
            <body>
            <h1>Logic metadata Metadata</h1>
            <div id="base-constant">
            Base constant: 玩家轮流翻开自己牌堆顶的一张牌，按顺序摆成牌堆；如果新牌与已有牌堆中某张牌重复，则将两张牌之间的所有牌收为己有。
            </div>
            <div id="params">
                <ul>
                <li>Name: num_players, Description: 玩家数, Min: 2, Max: 3, Step: 1, Variant: 无特殊常量</li>
                <li>Name: deck_size, Description: 每人初始牌数, Min: 5, Max: 15, Step: 1, Variant: 初始牌数越多，游戏越复杂</li>
                </ul>
            </div>
            <div id="cases">
                <p>metadata: 两位玩家，A 和 B，初始牌为平均分的整副牌。A 先出牌，依次出 Spade 5, Heart 7, Diamond 5。 Question: 哪些牌被 A 收走? Answer: Spade 5, Heart 7, Diamond 5。</p>
                <p>metadata: 三位玩家，轮流出牌。当前 B 出的牌与桌面已有牌重复。 Question: B 收走哪些牌? Answer: B 收走从重复牌之间的所有牌。</p>
            </div>
            </body>
            </html>
            """
        else:
            try:
                import requests
                response = requests.get(url)
                html_content = response.text
            except Exception as e:
                print(f"请求 {url} 失败: {e}")
                return

        # 提取基本常量
        constant_text = ""
        start_index = html_content.find("Base constant:")
        if start_index != -1:
            start_index += len("Base constant:")
            end_index = html_content.find("</div>", start_index)
            if end_index != -1:
                constant_text = html_content[start_index:end_index].strip()
            else:
                end_line_index = html_content.find("\n", start_index)
                constant_text = html_content[start_index:end_line_index].strip() if end_line_index != -1 else html_content[start_index:].strip()
        if constant_text:
            self.constant = constant_text

        # 提取变量
        import re
        param_pattern = re.compile(
            r"Name:\s*([^,]+),\s*Description:\s*([^,]+),\s*Min:\s*([^,]+),"
            r"\s*Max:\s*([^,]+),\s*Step:\s*([^,]+)(?:,\s*Variant:\s*(.*))?"
        )
        for match in param_pattern.finditer(html_content):
            name = match.group(1).strip()
            desc = match.group(2).strip()
            min_val_str = match.group(3).strip()
            max_val_str = match.group(4).strip()
            step_val_str = match.group(5).strip()
            if min_val_str.replace('.', '', 1).isdigit():
                min_val = int(min_val_str) if min_val_str.isdigit() else float(min_val_str)
            else:
                min_val = min_val_str
            if max_val_str.replace('.', '', 1).isdigit():
                max_val = int(max_val_str) if max_val_str.isdigit() else float(max_val_str)
            else:
                max_val = max_val_str
            if step_val_str.replace('.', '', 1).isdigit():
                step_val = int(step_val_str) if step_val_str.isdigit() else float(step_val_str)
            else:
                step_val = step_val_str
            variant_info = match.group(6).strip() if match.group(6) else None
            self.add_variable(name, desc, min_val, max_val, step_val, variant_info)

        # 提取样例
        case_pattern = re.compile(r"<p>(.*?)</p>", re.DOTALL)
        for ex_match in case_pattern.finditer(html_content):
            ex_text = re.sub(r"<.*?>", "", ex_match.group(1)).strip()
            if not ex_text:
                continue
            metadata_idx = ex_text.find("metadata:")
            question_idx = ex_text.find("Question:")
            answer_idx = ex_text.find("Answer:")
            if metadata_idx != -1 and question_idx != -1 and answer_idx != -1:
                metadata_part = ex_text[metadata_idx + len("metadata:"): question_idx].strip()
                question_part = ex_text[question_idx + len("Question:"): answer_idx].strip()
                answer_part = ex_text[answer_idx + len("Answer:"):].strip()
                self.add_case(metadata_part, question_part, answer_part)

    def generate_constant_based_on_induction(self, extra_constant: str = None, extra_case: list = None, extra_other_info: dict = None):
        """
        根据归纳法生成新常量。
        :param extra_constant: 额外常量。
        :param extra_case: 额外样例。
        :param extra_other_info: 额外其他信息。
        :return: 新常量。
        """
        new_constant_prompt = generate_constant_based_on_induction_en.format(metadata_name=self.metadata_name, his_constant=self.constant, his_case=self.cases, reference_constant=extra_constant, reference_case=extra_case, reference_other_info=extra_other_info)

        new_constant = None
        for i in tqdm(range(10), desc="Generate new constant"):
            response = self.get_llm_response(new_constant_prompt, self.model_name)
            new_constant = self.extract_last_complete_json(response)
            if new_constant is not None and new_constant.get("metadata_constant", None) is not None:
                new_constant = new_constant["metadata_constant"]
                break
            else:
                print(f"生成新常量失败，尝试第{i+1}次")
                continue
        
        if new_constant is None:
            print("生成新常量失败")
        else:
            self.set_constant(new_constant)

        return new_constant
    
    def generate_cases_by_deduction(self, case_nums:int = 3,
    extra_constant: str = None, extra_case: list = None, extra_other_info: dict = None):
        """
        根据推理生成新的样例。
        :param case_nums: 生成样例的数量, 默认3个。
        :param extra_constant: 额外常量。
        :param extra_case: 额外样例。
        :param extra_other_info: 额外其他信息。
        :return: 新的样例。
        """
        
        if extra_case is not None:
            self.add_case_by_list(extra_case)
        if len(self.cases) >= case_nums:
            return self.cases[:case_nums]

        while len(self.cases) < case_nums:
            new_case = self._generate_cases_by_deduction(extra_constant=extra_constant, extra_other_info=extra_other_info)
            if new_case is not None:
                self.add_case_by_dict(new_case)
        return self.cases

    def _generate_cases_by_deduction(self, extra_constant: str = None, extra_other_info: dict = None):
        """
        根据推理生成新的样例。
        :param extra_constant: 额外常量。
        :param extra_other_info: 额外其他信息。
        :return: 新的样例。
        """

        new_case_prompt = generate_cases_by_deduction_en.format(metadata_name=self.metadata_name, metadata_constant=self.constant, metadata_case=self.cases, extra_constant=extra_constant, extra_other_info=extra_other_info)

        new_case = None
        for i in tqdm(range(10), desc="Generate new case"):
            response = self.get_llm_response(new_case_prompt, self.model_name)
            new_case = self.extract_last_complete_json(response)
            # 确保生成了新的元数据
            if new_case is not None and new_case.get("metadata", None) is not None and new_case.get("question", None):
                # 如果没有答案则生成答案
                if new_case.get("answer", None) is None or new_case.get("answer", "") == "":
                    new_case["answer"] = self._get_answer(new_case.get("metadata", ""), new_case.get("question", ""))
                # 检查答案是否正确
                flag = self._check_answer(new_case.get("metadata", ""), new_case.get("question", ""), new_case.get("answer", ""))
                if flag:
                    new_case = new_case
                    # 校正问题格式
                    new_case["question"] = self._correct_question_format(new_case.get("question", ""), new_case.get("answer", ""))
                    break
                else:
                    print(f"生成新样例失败，尝试第{i+1}次")
                    continue
            else:
                print(f"生成新样例失败，尝试第{i+1}次")
                continue
        return new_case
    
    def _get_answer(self, metadata: str, question: str):
        """
        根据元数据和问题生成答案。
        :param metadata: 元数据。
        :param question: 问题。
        :return: 答案。
        """
        get_answer_prompt = get_answer_en.format(metadata_name=self.metadata_name, metadata_constant=self.constant, metadata=metadata, question=question)
        for i in tqdm(range(10), desc="Get answer"):
            answer = self.get_llm_response(get_answer_prompt, self.model_name)
            answer = self.extract_last_complete_json(answer)
            if answer is not None and answer.get("answer", None) is not None:
                return answer.get("answer", "")
            else:
                print(f"生成答案失败，尝试第{i+1}次")
                continue
        return None

    def _check_answer(self, metadata: str, question: str, answer: str):
        """
        检查答案是否正确。
        :param metadata: 元数据。
        :param question: 问题。
        :param answer: 答案。
        :return: 是否正确。
        """
        check_answer_prompt = check_answer_en.format(metadata_name=self.metadata_name, metadata_constant=self.constant, metadata=metadata, question=question, candidate_answer=answer)
        for i in tqdm(range(10), desc="Check answer"):
            response = self.get_llm_response(check_answer_prompt, self.model_name)
            response = self.extract_last_complete_json(response)
            if response is not None and response.get("is_correct", None) is not None:
                return response.get("is_correct", False)
            else:
                print(f"检查答案失败，尝试第{i+1}次")
                continue
        return False

    def _correct_question_format(self, question: str, answer: str):
        """
        校正问题格式。
        :param question: 问题。
        :param answer: 答案。
        :return: 校正后的问题。
        """        
        return self.update_question_with_answer(question, answer)

    def _make_placeholder(self, obj: JSONType) -> JSONType:
        if isinstance(obj, list):
            return [self._make_placeholder(item) for item in obj]
        if isinstance(obj, tuple):
            return tuple(self._make_placeholder(item) for item in obj)
        if isinstance(obj, Mapping):
            return {k: self._make_placeholder(v) for k, v in obj.items()}
        return "_"  # primitive type
    
    def update_question_with_answer(self, question: JSONType, answer: JSONType) -> JSONType:
        # 1) completely identical
        if question == answer:
            return question

        # NEW constant: if question is "empty" (empty list, empty dict, or None), treat as needing full skeleton of answer
        if (isinstance(question, list) and len(question) == 0) or (isinstance(question, dict) and len(question) == 0) or question is None:
            return self._make_placeholder(answer)

        # 2) both are sequence (list/tuple)
        if isinstance(question, (list, tuple)) and isinstance(answer, (list, tuple)):
            updated: List[JSONType] = []
            for i, ans_item in enumerate(answer):
                if i < len(question):
                    updated.append(self.update_question_with_answer(question[i], ans_item))
                else:  # answer has new element
                    updated.append(self._make_placeholder(ans_item))
            return updated

        # 3) both are mapping (dict)
        if isinstance(question, Mapping) and isinstance(answer, Mapping):
            updated: Dict[str, JSONType] = {}
            for key, ans_val in answer.items():
                if key in question:
                    updated[key] = self.update_question_with_answer(question[key], ans_val)
                else:  # answer has new key
                    updated[key] = self._make_placeholder(ans_val)
            return updated

        # 4) primitive type or type mismatch
        return "_"
    
    def generate_variable_by_analogy(self, extra_constant: str = None, extra_case: list = None, extra_variable: list = None, extra_other_info: dict = None):
        """
        根据类比推理生成新的变量。
        :param extra_constant: 额外常量。
        :param extra_case: 额外示例。
        :param extra_variable: 额外变量。
        :param extra_other_info: 额外其他信息。
        :return: 新的变量。
        """
        if extra_variable is not None:
            self.add_variable_by_list(extra_variable)
        if extra_case is not None:
            self.add_case_by_list(extra_case)
    
        generate_variable_by_analogy_prompt = generate_variables_by_analogy_en.format(metadata_name=self.metadata_name, metadata_constant=self.constant, cases=self.cases, extra_constant=extra_constant, extra_other_info=extra_other_info)
        for i in tqdm(range(10), desc="Generate variable by analogy"):
            response = self.get_llm_response(generate_variable_by_analogy_prompt, self.model_name)
            response = self.extract_last_complete_json(response)
            if response is not None and response.get("variable", None) is not None:
                self.add_variable_by_list(response.get("variable", []))
                break
            else:
                print(f"生成变量失败，尝试第{i+1}次")
                continue
        return self.variable
    
    def judge_variable(self, extra_info: dict = None):
        """
        判断变量是否合理,如果有不合理的地方,则进行修改。
        :return: 是否合理。
        """
        judge_variable_prompt = validate_variables_en.format(metadata_constant=self.constant, cases=self.cases, variables=self.variable, extra_info=extra_info)
        for i in tqdm(range(10), desc="Judge variable"):
            response = self.get_llm_response(judge_variable_prompt, self.model_name)
            response = self.extract_last_complete_json(response)
            if response is not None and response.get("variable", None) is not None:
                self.set_variable(response.get("variable", []))
                break
            else:
                print(f"判断变量失败，尝试第{i+1}次")
                continue
        
        # 删除min、max和step不为数字的变量
        self.variable = [param for param in self.variable if param.get("min", None) is not None and param.get("max", None) is not None and param.get("step", None) is not None]
        self.save_metadata()
        
        return self.variable
    
    def make_metadata_by_cmd(self):
        """
        使用命令行交互的方式，新增或者更新元数据。
        """
        temp_deepth_id = 0
        temp_input_data = None
        temp_old_data = None
        while True:
            success, result, old_data, new_deepth_id, is_continue_input = self._make_metadata(deepth_id=temp_deepth_id, input_data=temp_input_data, old_data=temp_old_data)
            print(result)
            if success:
                break
            if is_continue_input:
                temp_input_data = input()
            temp_old_data = old_data
            temp_deepth_id = new_deepth_id
    
    def _make_metadata(self, deepth_id: int = 0, input_data: any = None, old_data: any = None) -> tuple[bool, any, any, int, bool]:
        """
        新增或者更新元数据。
        :param deepth_id: 深度id，用于标识当前是第几层，0表示最外层，1表示第一层，以此类推。
        :param input_str: 传入信息。
        :param old_data: 旧数据。
        :return: 
            是否成功，返回值，旧数据，新的深度id，是否需要继续输入。
        """
        if deepth_id == 0:
            return False, "【新增或者更新元数据】请输入新的元数据或者更新已有元数据。。。", None, 1, False
        elif deepth_id == 1:
            temp_constant = self.get_constant()
            if temp_constant == "":
                return False, "【新增或者更新元数据】请输入新的基本常量：", None, 2, True
            else:
                print_str = f"【新增或者更新元数据】当前基本常量为：{temp_constant} \n\n 【新增或者更新元数据】请输入新的基本常量（留空则不更新）："
                return False, print_str, None, 2, True
        elif deepth_id == 2:
            if input_data is not None and str(input_data).strip() != "":
                self.set_constant(input_data)
            temp_variable = self.get_variable()
            temp_variable_num = len(temp_variable)
            return False, f"【新增或者更新元数据】请输入新的或者更新已有泛化性变量。。。 \n\n【新增或者更新元数据】当前泛化性变量数量为：{temp_variable_num}，请输入新的泛化性变量数量（留空则不更新）：", None, 3, True
        elif deepth_id == 3:
            temp_variable = self.get_variable()
            temp_variable_num = len(temp_variable)
            if input_data is not None and str(input_data).strip() != "":
                old_data = temp_variable
                temp_new_variable_info = []
                for i in range(int(input_data)):
                    temp_new_variable = {
                        "name": "wait",
                        "description": "wait",
                        "min": 0,
                        "max": 0,
                        "step": 0,
                        "variant": ""
                    }
                    temp_new_variable_info.append(temp_new_variable)
                self.set_variable(temp_new_variable_info)
                return False, "【新增或者更新元数据】请依此输入新的或者更新已有泛化性变量。。。", old_data, 4, False
            else:
                return False, "【新增或者更新元数据】请输入新的或者更新已有元数据样例。。。", None, 1000000, False
        elif deepth_id > 3 and deepth_id < 1000000:
            temp_variable_info = self.get_variable()
            max_deepth_id = len(temp_variable_info) * 12
            deepth_idV2 = deepth_id - 4
            if deepth_idV2 >= max_deepth_id:
                return False, "【新增或者更新元数据】请输入新的或者更新已有元数据样例。。。", None, 1000000, False
            else:
                variable_index = deepth_idV2 // 12 # 向下取整
                variable_sub_index = deepth_idV2 % 12 # 取余
                if variable_sub_index == 0:
                    if variable_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量名称：{old_data[variable_index]['name']} \n\n 【新增或者更新元数据】请输入新的或者更新已有泛化性变量名称（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量的名称不存在。。。\n\n 【新增或者更新元数据】请输入新的泛化性变量名称：", old_data, deepth_id + 1, True
                elif variable_sub_index == 1:
                    if str(input_data).strip() != "":
                        temp_variable_info[variable_index]["name"] = input_data
                    else:
                        if variable_index < len(old_data):
                            if old_data[variable_index].get("name", "") != "":
                                temp_variable_info[variable_index]["name"] = old_data[variable_index].get("name", "")

                    self.set_variable(temp_variable_info)
                    return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量名称：{temp_variable_info[variable_index]['name']} \n\n", old_data, deepth_id + 1, False
                elif variable_sub_index == 2:
                    if variable_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量描述：{old_data[variable_index]['description']} \n\n 【新增或者更新元数据】请输入新的或者更新已有泛化性变量描述（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量的描述不存在。。。\n\n 【新增或者更新元数据】请输入新的泛化性变量描述：", old_data, deepth_id + 1, True
                elif variable_sub_index == 3:
                    if str(input_data).strip() != "":
                        temp_variable_info[variable_index]["description"] = input_data
                    else:
                        if variable_index < len(old_data):
                            if old_data[variable_index].get("description", "") != "":
                                temp_variable_info[variable_index]["description"] = old_data[variable_index].get("description", "")

                    self.set_variable(temp_variable_info)
                    return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量描述：{temp_variable_info[variable_index]['description']} \n\n", old_data, deepth_id + 1, False
                elif variable_sub_index == 4:
                    if variable_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量最小值：{old_data[variable_index]['min']} \n\n 【新增或者更新元数据】请输入新的或者更新已有泛化性变量最小值（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量的最小值不存在。。。\n\n 【新增或者更新元数据】请输入新的泛化性变量最小值：", old_data, deepth_id + 1, True
                elif variable_sub_index == 5:
                    if str(input_data).strip() != "":
                        temp_variable_info[variable_index]["min"] = int(input_data)
                    else:
                        if variable_index < len(old_data):
                            if old_data[variable_index].get("min", "") != "":
                                temp_variable_info[variable_index]["min"] = old_data[variable_index].get("min", "")

                    self.set_variable(temp_variable_info)
                    return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量最小值：{temp_variable_info[variable_index]['min']} \n\n", old_data, deepth_id + 1, False
                elif variable_sub_index == 6:
                    if variable_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量最大值：{old_data[variable_index]['max']} \n\n 【新增或者更新元数据】请输入新的或者更新已有泛化性变量最大值（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量的最大值不存在。。。\n\n 【新增或者更新元数据】请输入新的泛化性变量最大值：", old_data, deepth_id + 1, True
                elif variable_sub_index == 7:
                    if str(input_data).strip() != "":
                        temp_variable_info[variable_index]["max"] = int(input_data)
                    else:
                        if variable_index < len(old_data):
                            if old_data[variable_index].get("max", "") != "":
                                temp_variable_info[variable_index]["max"] = old_data[variable_index].get("max", "")

                    self.set_variable(temp_variable_info)
                    return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量最大值：{temp_variable_info[variable_index]['max']} \n\n", old_data, deepth_id + 1, False
                elif variable_sub_index == 8:
                    if variable_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量步长：{old_data[variable_index]['step']} \n\n 【新增或者更新元数据】请输入新的或者更新已有泛化性变量步长（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量的步长不存在。。。\n\n 【新增或者更新元数据】请输入新的泛化性变量步长：", old_data, deepth_id + 1, True
                elif variable_sub_index == 9:
                    if str(input_data).strip() != "":
                        temp_variable_info[variable_index]["step"] = int(input_data)
                    else:
                        if variable_index < len(old_data):
                            if old_data[variable_index].get("step", "") != "":
                                temp_variable_info[variable_index]["step"] = old_data[variable_index].get("step", "")

                    self.set_variable(temp_variable_info)
                    return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量步长：{temp_variable_info[variable_index]['step']} \n\n", old_data, deepth_id + 1, False
                elif variable_sub_index == 10:
                    if variable_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量变体描述：{old_data[variable_index].get('variant', '')} \n\n 【新增或者更新元数据】请输入新的或者更新已有泛化性变量变体描述（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量的变体描述不存在。。。\n\n 【新增或者更新元数据】请输入新的泛化性变量变体描述：", old_data, deepth_id + 1, True
                elif variable_sub_index == 11:
                    if str(input_data).strip() != "":
                        temp_variable_info[variable_index]["variant"] = input_data
                    else:
                        if variable_index < len(old_data):
                            if old_data[variable_index].get("variant", "") != "":
                                temp_variable_info[variable_index]["variant"] = old_data[variable_index].get("variant", "")

                    self.set_variable(temp_variable_info)
                    return False, f"【新增或者更新元数据】第{variable_index+1}个泛化性变量变体描述：{temp_variable_info[variable_index]['variant']} \n\n", old_data, deepth_id + 1, False
        elif deepth_id == 1000000:
            temp_cases = self.get_cases()
            temp_case_num = len(temp_cases)
            return False, f"【新增或者更新元数据】请输入新的或者更新已有元数据样例。。。\n\n 【新增或者更新元数据】当前元数据样例数量为：{temp_case_num}，请输入新的元数据样例数量（留空则不更新）：", None, 1000001, True
        elif deepth_id == 1000001:
            temp_cases = self.get_cases()
            temp_case_num = len(temp_cases)
            if input_data is not None and str(input_data).strip() != "":
                old_data = temp_cases
                temp_new_case_info = []
                for i in range(int(input_data)):
                    temp_new_case = {
                        "metadata": "wait",
                        "question": "wait",
                        "answer": "wait"
                    }
                    temp_new_case_info.append(temp_new_case)
                self.set_cases(temp_new_case_info)
                return False, "【新增或者更新元数据】请依此输入新的或者更新已有元数据样例。。。", old_data, 1000002, False
            else:
                return False, "【新增或者更新元数据】请输入新的或者更新已有元数据样例。。。", None, 2000000, False
        elif deepth_id > 1000001 and deepth_id < 2000000:
            temp_case_info = self.get_cases()
            max_deepth_id = len(temp_case_info) * 6
            deepth_idV2 = deepth_id - 1000002
            if deepth_idV2 >= max_deepth_id:
                return False, "【新增或者更新元数据】已完成所有元数据样例的输入。。。", None, 2000000, False
            else:
                case_index = deepth_idV2 // 6 # 向下取整
                case_sub_index = deepth_idV2 % 6 # 取余
                if case_sub_index == 0:
                    if case_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的元数据：{old_data[case_index]['metadata']} \n\n 【新增或者更新元数据】请输入新的或者更新已有元数据样例的元数据（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的元数据不存在。。。\n\n 【新增或者更新元数据】请输入新的元数据样例的元数据：", old_data, deepth_id + 1, True
                elif case_sub_index == 1:
                    if str(input_data).strip() != "":
                        temp_case_info[case_index]["metadata"] = input_data
                    else:
                        if case_index < len(old_data):
                            if old_data[case_index].get("metadata", "") != "":
                                temp_case_info[case_index]["metadata"] = old_data[case_index].get("metadata", "")

                    self.set_cases(temp_case_info)
                    return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的元数据：{temp_case_info[case_index]['metadata']} \n\n", old_data, deepth_id + 1, False
                elif case_sub_index == 2:
                    if case_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的问题：{old_data[case_index]['question']} \n\n 【新增或者更新元数据】请输入新的或者更新已有元数据样例的问题（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的问题不存在。。。\n\n 【新增或者更新元数据】请输入新的元数据样例的问题：", old_data, deepth_id + 1, True
                elif case_sub_index == 3:
                    if str(input_data).strip() != "":
                        temp_case_info[case_index]["question"] = self.parse_structure(input_data)
                    else:
                        if case_index < len(old_data):
                            if old_data[case_index].get("question", "") != "":
                                temp_case_info[case_index]["question"] = old_data[case_index].get("question", "")

                    self.set_cases(temp_case_info)
                    return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的问题：{temp_case_info[case_index]['question']} \n\n", old_data, deepth_id + 1, False
                elif case_sub_index == 4:
                    if case_index < len(old_data):
                        return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的答案：{old_data[case_index]['answer']} \n\n 【新增或者更新元数据】请输入新的或者更新已有元数据样例的答案（留空则不更新）：", old_data, deepth_id + 1, True
                    else:
                        return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的答案不存在。。。\n\n 【新增或者更新元数据】请输入新的元数据样例的答案：", old_data, deepth_id + 1, True
                elif case_sub_index == 5:
                    if str(input_data).strip() != "":
                        temp_case_info[case_index]["answer"] = input_data
                    else:
                        if case_index < len(old_data):
                            if old_data[case_index].get("answer", "") != "":
                                temp_case_info[case_index]["answer"] = old_data[case_index].get("answer", "")

                    self.set_cases(temp_case_info)
                    return False, f"【新增或者更新元数据】第{case_index+1}个元数据样例的答案：{temp_case_info[case_index]['answer']} \n\n", old_data, deepth_id + 1, False
        elif deepth_id == 2000000:
            temp_metadata = self.get_metadata()
            metadata_name = temp_metadata["metadata_name"]
            constant = temp_metadata["constant"]
            variable = temp_metadata["variable"]
            cases = temp_metadata["cases"]
            return True, f"【新增或者更新元数据】新增或者更新元数据完成。\n\n 【完整元数据的元数据名称】{metadata_name}\n\n 【完整元数据的基本常量】{constant}\n\n 【完整元数据的泛化性变量】{variable}\n\n 【完整元数据的元数据样例】{cases}", None, 2000000, False
    
    def parse_structure(self, text: str) -> Any:
        """
        将字符串解析成对应的 Python 数据结构（list / dict / str / int / …）。

        解析顺序：
        1. json.loads（标准 JSON）
        2. ast.literal_eval（Python 字面量）
        3. 单引号→双引号替换后再次尝试 json.loads
        """
        # 已经是 Python 对象，直接返回
        if not isinstance(text, str):
            return text

        # 尝试严格 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试 Python 字面量
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            pass

        # 把单引号替换为双引号再试一次 JSON
        text_fixed = re.sub(r"'", r'"', text)
        try:
            return json.loads(text_fixed)
        except json.JSONDecodeError:
            pass

        # 全部失败，说明格式无法识别
        raise ValueError("无法将输入解析为有效的数据结构")

    def read_multiline_until_sentinel(self, sentinel="##END##", systemp_prompt= "", prompt="> "):
        if systemp_prompt != "":
            print(systemp_prompt)
        print(f"输入多行，最后单独输入 {sentinel} 结束：")
        lines = []
        while True:
            line = input(prompt)
            if line == sentinel:
                break
            lines.append(line)
        return "\n".join(lines)

    def constant_based_judge(
        self,
        basic_info: Union[str, dict],                  # 基本信息，可直接放入提示，或在生成提示时展开
        judge_constants: Union[str, dict],                 # 判断常量，同上
        expected_output_format: Union[
            Literal["json", "markdown", "text"],       # 内置格式
            Callable[[Any], Any]                       # 或者一个自定义后处理函数
        ] = "json",
        *,
        model_preamble: str = (
            "You are an impartial judge. "
            "Evaluate the case strictly according to the given constants "
            "and return your conclusion in the required format.\n"
        ),
        temperature: float = 0.0                       # 若你的 llm_response 支持模型变量，可在此处透传
    ) -> Any:
        """
        根据 basic_info 和 judge_constants 生成提示并调用 llm_response，
        然后将 LLM 回复整理为期望的输出格式。

        Returns
        -------
        Any
            整理后的结果；类型取决于 expected_output_format。
        """

        # 1) 构造提示（最简单的串联，也可以在此做更多模板化）
        prompt_parts = [
            model_preamble,
            "## basic_info\n",
            json.dumps(basic_info, ensure_ascii=False, indent=2) if isinstance(basic_info, dict) else str(basic_info),
            "\n\n## judge_constants\n",
            json.dumps(judge_constants, ensure_ascii=False, indent=2) if isinstance(judge_constants, dict) else str(judge_constants),
            "\n\n## expected_output_format\n",
            (
                "Please strictly return a **valid JSON** object containing only the key: result. \n The format is like this: \n"
                "```json\n"
                "{\n"
                "    \"result\": \"The result of the judge\"\n"
                "}\n"
                "```\n"
                if expected_output_format == "json" else
                "Please output the result in a **Markdown** code block." if expected_output_format == "markdown" else
                "Please return the result as plain text." if expected_output_format == "text"
                else "Please return the result in the custom format."
            )
        ]
        prompt = "\n".join(prompt_parts)

        # 2) 调用 LLM
        for i in range(10):
            raw_response = self.get_llm_response(prompt, model_name=self.model_name)  # 你的 llm_response 可能只接 prompt
            if raw_response is not None:
                break

        # 3) 整理 / 校验输出
        return raw_response
        
def main():
    metadata_name = "8_metadata"
    agent = MetadataAgent(metadata_name)
    # agent.generate_constant_based_on_induction(extra_constant="给定一个表示8拼图状态的3×3网格，输出到达目标配置[[1, 2, 3], [4, 5, 6], [7, 8, 0]]的最短移动序列（上、下、左、右），或指示如果不存在解决方案。")
    agent.generate_cases_by_deduction()
    agent.generate_variable_by_analogy()
    agent.judge_variable()

    # # 创建 MetadataAgent 实例
    # while True:
    #     metadata_name = input("请输入元数据名称：")
    #     if str(metadata_name).strip() == "":
    #         break
    #     agent = MetadataAgent(metadata_name)
    #     # agent.updete_leaderboard_website()
    #     agent.make_metadata_by_cmd()

# 执行示例演示
if __name__ == "__main__":
    main()