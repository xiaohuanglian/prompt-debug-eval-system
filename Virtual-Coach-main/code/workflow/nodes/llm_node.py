import re

from urllib3 import response
from node import BaseNode, NodeType
from workflow import WorkflowManager
from register_node import register_class
from llm.llm_interface import LLMConfig
from typing import Dict, Type, Any, Optional, Union, List
from util import dict_to_json_short
import json

answer_template = re.compile(r"\{[\s\S]*\}")


@register_class('llm_step')
class LLMStepNode(BaseNode):
    
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        #print('setup child')
        self.input_parameters = {
            'params_0': 'step',
            'params_1': 'step',
            'params_2': 'step',
        }
        self.output_parameters = {
            'content': 'step'
        }
        self.choices = ['default']
        #print(self.choices)
        #print('init')

        
        self.prompt = self.parent_workflow.prompt_factory.build_prompt('chat',config['attrs']['prompt'])
        self.system = config['attrs']['system']
        self.model = config['attrs']['model']
        self.json = config['attrs']['json']

        self.static_params = config['attrs']['static_params']


    async def run(self, input_parameters: dict=[]):
        
        try:
            print('llm_step run--------')

            params = {}
            for i in range(3):
                tmp_params = await self.get_input(f'params_{i}')
                
                if tmp_params:
                    params.update(tmp_params)
            params.update(self.static_params)
            print('llm_step params')
            print(params)

        #prompt_item = await self.get_input('params')
            #last_prompt = self.parent_workflow.get_memory('last_text')
            #prompt_item['last_prompt'] = last_prompt
            config:LLMConfig = LLMConfig(self.system,self.model)
            res = await self.prompt.send_prompt(config=config, params=params)
            #print('wait ', self.name)
            await self.wait_for_event()
            #print('after wait ', self.name)
            if self.json:
                match = answer_template.search(res)
                if not match:
                    raise Exception("No Json found")
                else:
                    res = json.loads(match.group())
            
            print('llm_step res')
            print(res)
            await self.set_output('content', res)
            
            
            self.set_choice('default')
            
            print('after after output content')
        except Exception as e:
            print('llm_step error:', e)
        return True

