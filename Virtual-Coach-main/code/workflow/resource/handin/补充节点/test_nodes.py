from pydantic_core.core_schema import nullable_schema
from scipy.sparse import data
from node import BaseNode, NodeType
from workflow import WorkflowManager
from register_node import register_class
from llm.llm_interface import LLMConfig
from typing import Dict, Type, Any, Optional, Union, List
import asyncio
import base64
import wave
import re

# 根据大模型的返回选项，选择后续节点
@register_class('choose_node')
class ChooseNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数（此处为空）
        self.input_parameters = {
            'content': 'step',
        }
        # 定义输出参数，'pkg'用于存储接收到的消息包
        self.output_parameters = {
        }
        # 定义下一个节点的选择选项
        self.choices = ['choice_a','choice_b']
    
    async def run(self, input_parameters: dict=[]):
        content = await self.get_input('content')
        # 从content中提取第一个大写字母
        first_uppercase = None
        if content:
            for char in content:
                if char.isupper():
                    first_uppercase = char
                    break
        # 等待事件触发（输出事件）
        await self.wait_for_event()

         # 根据第一个大写字母选择下一个节点
        if first_uppercase == 'A':
            self.set_choice('choice_a')
        else:
            self.set_choice('choice_b')

        return True

