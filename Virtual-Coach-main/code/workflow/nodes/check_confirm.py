from re import S

from urllib3 import response
from node import BaseNode, NodeType
from workflow import WorkflowManager
from register_node import register_class
from llm.llm_interface import LLMConfig
from typing import Dict, Type, Any, Optional, Union, List
from util import dict_to_json_short



# 接收信息节点
@register_class('receive_message')
class ReceiveMessageNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数（此处为空）
        self.input_parameters = {
        }
        # 定义输出参数，'pkg'用于存储接收到的消息包
        self.output_parameters = {
            'pkg': 'step',
            'last_message_id': 'step'
        }
        # 定义下一个节点的选择选项
        self.choices = ['default']
    
    async def run(self, input_parameters: dict=[]):
        #print('before waiting receive_message-------', self.name)
        # 等待事件触发（输出事件）
        
        
        await self.wait_for_event()
        #print('start receive_message++++++++++', self.name)
        self.parent_workflow.log('debug', f"after waiting receive_message {self.name}")
        
        # 启动外部信息监听
        #self.start_message()
        
        # 获得外部信息输入
        pkg = await self.get_message()

        # 设置输出参数'pkg'
        await self.set_output('pkg', pkg)
        #print('pkg:', pkg)
        self.parent_workflow.log('debug', f"recv message {dict_to_json_short(pkg)}")

        await self.set_output('last_message_id', pkg['message_id'])

        # 设置下一个节点选择为'default'
        self.set_choice('default')
        self.parent_workflow.log('debug', f"finish receive_message {self.name}")
        # 返回执行成功
        return True

# 判断动作节点
@register_class('judge_motion')
class JudgeMotionNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数
        self.input_parameters = {
            'pkg': 'step'
        }
        # 定义输出参数：pkg_step（步骤名称）、adjust（是否调整）
        self.output_parameters = {
            'pkg_step': 'step',
            'adjust': 'step',
            'status': 'step',
            'prompt_item': 'step'
        }
        # 定义下一个节点的选择选项： good（动作正确）、improved（动作改进）、not_improved（动作未改进）、other_problem（其他问题）
        #self.choices = ['good','improved', 'not_improved', 'other_problem']
        self.choices = ['default']


    async def run(self, input_parameters: dict=[]):
        print('judge_motion ', self.name)
        # 获得输入的pkg内容
        pkg = await self.get_input('pkg')
        print(pkg)
        # 目标检测项
        tar_detect_item = '2'
        tmp_list = []
        other_flag = False
        
        cur_status = None
        
        for item in pkg['data']['extra']['frame_result']:
            print("item:", item)
            if item['detect_item_id'] == tar_detect_item:
                tmp_list.append(item)
                
                if item['error_info'] == 'smaller':
                    other_flag = True
                
                if item['score'] > 0.001:
                    if cur_status == None:
                        cur_status = 'good'
                else:
                    cur_status = item['error_metrics']['trend']
            
        print('cur_status:', cur_status)
        print('filter list:', tmp_list)
        
        
        '''
        tar_item = None
        other_item_flag = False
        for item in pkg['data']['extra']['frame_result']:
            if item['detect_item_id'] == tar_detect_item:
                tar_item = item 
            else:
                if item['score'] < 0.001:
                    other_item_flag = True
        '''
        
        print('judge_motion waiting....', self.name)
        # 等待输出信号
        await self.wait_for_event()
        print('after judge_motion waiting....', self.name)
        
        #await self.set_output('detect_item', tar_detect_item)
            
        # 设置输出参数：pkg_step（步骤名称）
        await self.set_output('pkg_step', pkg['step'])

        #print(other_item_flag)
        #print(tar_item)
        print('check motion?????????', pkg['step'])
        
        self.set_choice('default')
        
        #其他错误
        if other_flag:
            print('judge_motion other_problem', self.name)
            #self.set_choice('default')
            
            if pkg['step'] == 'motion_3':
                await self.set_output('adjust', {
                    "idList": ["2", "3"],
                    "parameters":  [[45.0, 100.0, 150.0, 180.0, 55.0, 75.0, 165.0, 180.0], [40.0, 100.0, 165.0, 180.0, 65.0, 90.0, 170.0, 180.0]]  
                })
            else:
                await self.set_output('adjust', None)
            
            await self.set_output('status', 'other_problem')
            prompt_item = {
                'action': '深蹲',
                'other_problem': True
            }
            await self.set_output('prompt_item', prompt_item)
            print('judge_motion other_problem', self.name)
            return True
        
        # 正确
        if cur_status == 'good':
            print('judge_motion good', self.name)
            await self.set_output('adjust', None)
            #self.set_choice('good')
            await self.set_output('status', 'good')
            print('judge_motion good', self.name)
            return True
        
        # 目标检测项改善
        if cur_status == 'improved' or cur_status == 'unchanged':
            print('judge_motion improved', self.name)
            
            #await self.set_output('adjust', None)
            #self.set_choice('improved')
            await self.set_output('status', 'improved')

            prompt_item = {
                'action': '深蹲',
                'detect_item': '屈髋角度',
                'wrong': '背部有点后仰',
                'trend': '改善'
            }
            await self.set_output('prompt_item', prompt_item)
            print('judge_motion improved', self.name)
           
        
        if cur_status == 'worsened':
            print('judge_motion not_improved', self.name)
            #self.set_choice('default')
            # 目标检测项未改善
            #await self.set_output('adjust', None)
            #self.set_choice('not_improved')
            
            await self.set_output('status', 'not_improved')
            prompt_item = {
                'action': '深蹲',
                'detect_item': '屈髋角度',
                'wrong': '背部有点后仰',
                'trend': '没有改善'
            }
            await self.set_output('prompt_item', prompt_item)
            print('judge_motion not_improved', self.name)
            

        if pkg['step'] == 'motion_3':
            await self.set_output('adjust', {
                "idList": ["2", "3"],
                "parameters":  [[45.0, 100.0, 150.0, 180.0, 55.0, 75.0, 165.0, 180.0], [40.0, 100.0, 165.0, 180.0, 65.0, 90.0, 170.0, 180.0]]  
            })
        else:
            print('set adjust=====================')
            await self.set_output('adjust', None)
        
        
        return True
        
        

# 发送音频节点
@register_class('send_audio_dispatch')
class SendAudioDispatchNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数：pkg_step（步骤名称）,data（音频数据，用于type是tts的时候）,adjust（调整参数）
        self.input_parameters = {
            'pkg_step': 'step',
            'adjust': 'step',
            'status': 'step'
        }
        self.output_parameters = {
            'response': 'step'
        }
        self.choices = ['good', 'improved', 'not_improved', 'other_problem']
        
        # 定义数据类型：url（oss文件播放）、tts（文本转语音）
        #self.data_type = config['attrs'].get('type', 'url')
        #if self.data_type == 'url':
        #    self.data_url = config['attrs'].get('url')
        self.audio_url = config['attrs'].get('audio_url')
    
    async def run(self, input_parameters: dict=[]):
        print('send audio dispatch0', self.name)
        pkg_step = await self.get_input('pkg_step')
        print('send audio dispatch1', self.name)
        adjust_item = await self.get_input('adjust')
        print('send audio dispatch2', self.name)
        status = await self.get_input('status')
        print('send audio dispatch3', self.name)
        if self.audio_url[status]['type'] == 'url':
            # url的音频数据类型
            res_content = {
                "step": pkg_step, 
                "status": "result",
                "data": {
                    "resource":{
                        "audio":[{    
                            "type":"url",
                            "tag": "test",
                            "url": self.audio_url[status]['url'],
                            "flag": "test"
                        }]
                    },
                    "info":{   
                        "complete": True,  
                    }
                }
            }
        if self.audio_url[status]['type'] == 'tts':
            # tts的音频数据类型
            res_content = {
                "step": pkg_step, 
                "status": "result",
                "data": {
                    "resource":{
                        "audio":[{    
                            "type":"stream",
                            "data_id": 0,
                            "data":""
                        }]
                    },
                    "info":{   
                        "complete": True,  
                    }
                }
            }
        # 如果存在调整参数
        if adjust_item:
            res_content['data']['info']['adjust'] = adjust_item
        print('before wait_for_event', self.name)
        # 等待输出信号
        await self.wait_for_event()

        print('after wait_for_event', self.name)
        #print(status)
        #print(self.choices)
        # 设置下一个节点
        self.set_choice(status)
        #await asyncio.sleep(0.1)
        #print('after audio dispatch', self.name)
        if self.audio_url[status]['type'] == 'url':
            self.parent_workflow.set_memory('last_text', self.audio_url[status]['text'])
            #print('send message ', self.name)
            # 返回数据包
            await self.parent_workflow.get_context('handler').send_message(res_content)
            #await asyncio.sleep(0.1)
        #print('after audio dispatch', self.name)
        await self.set_output('response', res_content)

        #print('after audio dispatch', self.name)
        

        return True


@register_class('llm_stream')
class LLMStreamNode(BaseNode):
    
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        #print('setup child')
        self.input_parameters = {
            #'status': 'step',
            'prompt_item': 'step'
            }
        self.output_parameters = {
            'content': 'stream'
            }
        self.choices = ['default']
        #print(self.choices)
        #print('init')

        self.stream_flag = 'init'

        self.prompt = self.parent_workflow.prompt_factory.build_prompt('chat_stream',config['attrs']['prompt'])
        self.system = config['attrs']['system']
        self.model = config['attrs']['model']
        self.seq = 0

    async def content_recall(self, data):
        #print('content_recall')
        #print(data)
        status = 1
        if self.stream_flag == 'init':
            self.stream_flag = 'start'
            status = 0
        if data['status'] == 'finish':
            status = 2
        #print('content_recall', data)
        await self.set_output('content', {
            'status': status,
            'text': data['content'],
            'seq': self.seq
        })
        self.seq += 1
        return True
        
    async def run(self, input_parameters: dict=[]):
        
        #print('wait content', self.name)
        #status = await self.get_input('status')
        #print('after wait content', self.name)
        print('llm_stream run--------')
        prompt_item = await self.get_input('prompt_item')
        last_prompt = self.parent_workflow.get_memory('last_text')
        prompt_item['last_prompt'] = last_prompt
        
        #print('wait ', self.name)
        await self.wait_for_event()
        #print('after wait ', self.name)

        self.set_choice('default')

        config:LLMConfig = LLMConfig(self.system,self.model)
        res = await self.prompt.send_prompt(config=config, params=prompt_item,
            recall=self.content_recall
        )
        #print('llm_stream run--------3')
        #print(res)
        self.stream_flag = 'finish'
        
        return True



# 发送音频节点
@register_class('send_audio_data')
class SendAudioDataNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数：pkg_step（步骤名称）,data（音频数据，用于type是tts的时候）,adjust（调整参数）
        self.input_parameters = {
            'response': 'step',
            'data': 'step'
        }
        self.output_parameters = {
        }
        self.choices = ['default']
        
        # 定义数据类型：url（oss文件播放）、tts（文本转语音）
        #self.data_type = config['attrs'].get('type', 'url')
        #if self.data_type == 'url':
        #    self.data_url = config['attrs'].get('url')
        #self.audio_url = config['attrs'].get('audio_url')
    
    async def run(self, input_parameters: dict=[]):
        print('send_audio_data run--------')
        response = await self.get_input('response')
        data = await self.get_input('data')
        
        # 等待输出信号
        await self.wait_for_event()
        #print('send_audio_data run--------2')
        response['data']['resource']['audio'][0]['data'] = data
        #print(data)
        #print(response)
        # 返回数据包
        await self.parent_workflow.get_context('handler').send_message(response)
    
        # 设置下一个节点
        self.set_choice('default')

        return True

