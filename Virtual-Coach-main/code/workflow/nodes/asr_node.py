from scipy.sparse import data
from node import BaseNode, NodeType
from workflow import WorkflowManager
from register_node import register_class
from llm.llm_interface import LLMConfig
from typing import Dict, Type, Any, Optional, Union, List
import asyncio
import base64
import wave
from util import print_dict_short

@register_class('asr_vad')
class ASRWithVADNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.StepNode)
        self.input_parameters = {}
        self.output_parameters = {
            'asr_text': 'step'
            }
        
        self.choices = ['default']
        
        self.status = 'INIT'

        self.step_name = config['attrs'].get('step_name', 'step')
        self.if_result_audio = config['attrs'].get('if_result_audio', False)

        self.result_audio_empty = config['attrs'].get('result_audio_empty', '')
        self.result_audio_receive = config['attrs'].get('result_audio_receive', '')



    async def on_sentence_end(self, response_text):
        print('sentence end============', response_text)
        self.status = 'STOP'
        await self.set_output('asr_text', response_text)   
        
        response = {
            'step': self.step_name,
            'status': 'asr_stop'
        }
        if self.if_result_audio:
            audio_data = ''
            resource_dict = {}
            if len(response_text.strip()) == 0:
                with open(self.result_audio_empty, 'r') as f:
                    audio_data = f.read()
                    resource_dict["audio"] = [{
                        "type": "stream",
                        "data_id": 0,
                        "data": audio_data,
                        "pos": 0
                    }]
            else:
                with open(self.result_audio_receive, 'r') as f:
                    audio_data = f.read()
                    resource_dict["audio"] = [{
                        "type": "stream",
                        "data_id": 0,
                        "data": audio_data,
                        "pos": 0
                    }]
            response['data'] = {
                "resource": resource_dict
            }
            
        print('send  asr response')
        print_dict_short(response)
        await self.parent_workflow.get_context('handler').send_message(response)
    


    async def run(self, input_parameters: dict=[]):
        asr_client = self.parent_workflow.get_context('asr_tencent')
        asr_client.set_recall(self.on_sentence_end)
        await self.wait_for_event()
        running_flag = True
        while True:
            print('waiting audio pkg')
            pkg = await self.get_message()
            print('recv audio pkg')
            if pkg['status'] == 'asr':
                if pkg['data']['resource']['audio']:
                    for item in pkg['data']['resource']['audio']:
                        if item['pos'] == 0 and self.status == 'INIT':
                            await asr_client.start()
                            self.status = 'START'
                            try:
                                # 解码base64字符串为bytes
                                audio_bytes = base64.b64decode(item['data'])
                                # 可以将解码后的音频数据发送给ASR客户端
                                res = await asr_client.process(audio_bytes)
                                if not res:
                                    break
                            except Exception as e:
                                print(f"Base64解码错误: {str(e)}")
                        if item['pos'] == 1 and self.status == 'START':
                            try:
                                # 解码base64字符串为bytes
                                audio_bytes = base64.b64decode(item['data'])
                                # 可以将解码后的音频数据发送给ASR客户端
                                res = await asr_client.process(audio_bytes)
                                if not res:
                                    break
                            except Exception as e:
                                print(f"Base64解码错误: {str(e)}")
                        if item['pos'] == 2:
                            running_flag = False
                            # await asr_client.stop()
                            break
            if not running_flag:
                break
        
        self.set_choice('default')
        
        return True

