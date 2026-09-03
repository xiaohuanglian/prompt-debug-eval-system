# -*- coding: utf-8 -*-
from re import S

from urllib3 import response
from node import BaseNode, NodeType
from workflow import WorkflowManager
from register_node import register_class
from llm.llm_interface import LLMConfig
from typing import Dict, Type, Any, Optional, Union, List
from util import dict_to_json_short
import json
import ast
import httpx
import os

# 发送确认信息
@register_class('send_ack')
class SendACKNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数：pkg_step（步骤名称）,data（音频数据，用于type是tts的时候）,adjust（调整参数）
        self.input_parameters = {
            "last_message_id": "step",
        }
        self.output_parameters = {
        }
        self.choices = ['default']
        self.step_name = config['attrs'].get('step_name')
        
    
    async def run(self, input_parameters: dict=[]):
        #print('send_audio_data run--------')
        last_message_id = await self.get_input('last_message_id')
        # 等待输出信号
        await self.wait_for_event()
      
        response = {
            "status": "ack",
            "step": self.step_name,
            "data": {
                "extra": {
                    "last_message_id": last_message_id
                }
            }
        }
        await self.parent_workflow.get_context('handler').send_message(response)
    
        # 设置下一个节点
        self.set_choice('default')

        return True



# 接收信息节点
@register_class('receive_ack')
class ReceiveACKNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数（此处为空）
        self.input_parameters = {
            'last_message_id': 'step',
        }
        # 定义输出参数，'pkg'用于存储接收到的消息包
        self.output_parameters = {
        }
        # 定义下一个节点的选择选项
        self.choices = ['default']
    
    async def run(self, input_parameters: dict=[]):
        last_message_id = await self.get_input('last_message_id')
        # 等待事件触发（输出事件）
        await self.wait_for_event()
        print('start receive_message++++++++++', self.name)
        # 启动外部信息监听
       
        pkg = await self.get_message()

        # 设置输出参数'pkg'
        print("recv ack:", pkg)
        
        # 设置下一个节点选择为'default'
        self.set_choice('default')
        
        #
        return True

# 接收信息节点
@register_class('send_step_resource')
class SendStepResourceNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 最多接入3个资源
        self.input_parameters = {
            "resource_0": "step",
            "resource_1": "step",
            "resource_2": "step",
        }
        # 用于校验ack
        self.output_parameters = {
            "last_message_id": "step",
        }
        # 定义下一个节点的选择选项
        self.choices = ['default']
        
        self.step_name = config['attrs'].get('step_name')
        self.status = config['attrs'].get('status')

        # 静态资源
        self.static_resouce = config['attrs'].get('static_resouce', [])
    
    async def run(self, input_parameters: dict=[]):
        
        resouce_dict = {}
        for item in self.static_resouce:
            if item['type'] in resouce_dict:
                resouce_dict[item['type']].append(item['data'])
            else:
                resouce_dict[item['type']] = [item['data']]
        for i in range(3):
            tmp_resource = await self.get_input(f"resource_{i}")
            if tmp_resource:
                if tmp_resource['type'] in resouce_dict:
                    resouce_dict[tmp_resource['type']].append(tmp_resource['data'])
                else:
                    resouce_dict[tmp_resource['type']] = [tmp_resource['data']]
    
        
        # 等待事件触发（输出事件）
        await self.wait_for_event()
       
        response = {
            "step": self.step_name,
            "status": self.status,
            "data": {
                "resource":resouce_dict
            },
        }
       
        last_message_id = await self.parent_workflow.get_context('handler').send_message(response)

        # 设置输出参数'last_message_id'
        await self.set_output('last_message_id', last_message_id)
        
        # 设置下一个节点选择为'default'
        self.set_choice('default')
        
# 接收信息节点
@register_class('send_motion_change')
class SendMotionChangeNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数（此处为空）
        self.input_parameters = {
            'content': 'step',
            'adjust': 'step'
        }
        # 定义输出参数，'pkg'用于存储接收到的消息包
        self.output_parameters = {
            "last_message_id": "step"
        }
        # 定义下一个节点的选择选项
        self.choices = ['default']

        self.step_name = config['attrs'].get('step_name')
        self.status = config['attrs'].get('status')
    
    async def run(self, input_parameters: dict=[]):
        content = await self.get_input('content')
        adjust = await self.get_input('adjust')
        # 等待事件触发（输出事件）
        await self.wait_for_event()
        
        response = {
            "step": self.step_name,
            "status": self.status,
            "data": {
                "extra":{
                    "content": content,
                    "adjust": adjust,
                }
            }

        }
        
        last_message_id = await self.parent_workflow.get_context('handler').send_message(response)
        
        await self.set_output('last_message_id', last_message_id)
        
        # 设置下一个节点选择为'default'
        self.set_choice('default')

        return True


        
# 接收信息节点
@register_class('receive_motion_change_result')
class ReceiveMotionChangeResultNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 

        # 定义输入参数（此处为空）
        self.input_parameters = {
        }
        # 定义输出参数，'pkg'用于存储接收到的消息包
        self.output_parameters = {
        }
        # 定义下一个节点的选择选项
        self.choices = ['default']
    
    async def run(self, input_parameters: dict=[]):
        # 等待事件触发（输出事件）
        await self.wait_for_event()
       
       
        pkg = await self.get_message()

        # 设置输出参数'pkg'
        print("recv ack:", pkg)
        
        # 设置下一个节点选择为'default'
        self.set_choice('default')
        
        #
        return True

#============================================

@register_class('clac_trace')
class ClacTrace(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "pkg": "step",
        }
        self.output_parameters = {
            'params': 'step',
            'parsed_pkg': 'step',
            'token': 'step'
        }
        self.choices = ['default', 'no_data']
    
    async def run(self, input_parameters: dict=[]):
        try:
            pkg = await self.get_input('pkg')
            '''
            data_str = pkg['data']
            try:
                # 方法1: 使用ast.literal_eval解析单引号字典
                data_dict = ast.literal_eval(data_str)
            except:
                # 方法2: 如果ast解析失败，尝试将单引号替换为双引号后用json.loads
                data_str_fixed = data_str.replace("'", '"')
                data_dict = json.loads(data_str_fixed)
            
            # 3. 解析last_group_trace中的traceInfo字段（嵌套的字符串化JSON）
            if 'extra' in data_dict and 'last_group_trace' in data_dict['extra']:
                last_group_trace = data_dict['extra']['last_group_trace']
                if 'traceInfo' in last_group_trace:
                    trace_info_str = last_group_trace['traceInfo']
                    # traceInfo字段已经是双引号格式，可以直接用json.loads解析
                    trace_info_dict = json.loads(trace_info_str)
                    # 替换原始字符串为解析后的字典
                    last_group_trace['traceInfo'] = trace_info_dict
    
            # 4. 将解析后的data字典放回外层JSON
            pkg['data'] = data_dict
            '''

            await self.wait_for_event()
            token = pkg['data']['extra']['token']
            await self.set_output('token', token)
            await self.set_output('parsed_pkg', pkg)
            
            # TODO: 对应动作名称，最常出现错误
            exercise_id = pkg['data']['extra'].get('motion_id', '4')
            quality_checkpoint = []
            quality_title = []
            reqs = []

            if exercise_id not in self.parent_workflow.get_context('action_list'):
                exercise_id = "4"
            
            exercise_name = self.parent_workflow.get_context('action_list')[exercise_id]['name']
            quality_checkpoint = self.parent_workflow.get_context('action_list')[exercise_id]['check_point']
            quality_title = self.parent_workflow.get_context('action_list')[exercise_id]['quality_title']
            reqs = self.parent_workflow.get_context('action_list')[exercise_id]['req']
            
            levels = pkg['data']['extra'].get('levels', 1)
            
            standard_list = ['low','medium','high'] 


            quality_list = {}
            for i in range(len(quality_checkpoint)):
                quality_list[quality_checkpoint[i]] = {
                    'is_enabled': True,
                    'standard': standard_list[levels-1],
                    'title': quality_title[i],
                    'req': reqs[i],
                }

            
            params = {
                "high_quality_reps" : pkg['data']['extra']['last_group_trace'].get('highQualityActionCount', 0),
                "error_reps" : pkg['data']['extra']['last_group_trace'].get('errorCount', 0),
                "most_frequent_error_type" : pkg['data']['extra']['last_group_trace'].get('errorName', ''),
                "set_reps": pkg['data']['extra'].get('rep_num', 10),
                "levels": pkg['data']['extra'].get('levels', 1),
                "exercise_name": exercise_name,
                "exercise_id": exercise_id,
                "quality_checkpoints": quality_list
            }            
            await self.set_output('params', params)
            if pkg['data']['extra']['last_group_trace']:
                print('Enter pic=======================')
                self.set_choice('default')
            else:
                print('Enter no_data=======================')
                self.set_choice('no_data')
        except Exception as e:
            print("judge error:", e)
        return True

@register_class('get_pic')
class GetInterPic(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "pkg": "step",
            "token": "step"
        }
        self.output_parameters = {
            'pic_res': 'step',
            
        }
        self.choices = ['default']
    
    async def run(self, input_parameters: dict=[]):
        try:
            pkg = await self.get_input('pkg')
            token = await self.get_input('token')
    

            # 从 pkg 中解析出 actionSessionId 与 group
            
            action_session_id = pkg['data']['extra']['last_group_trace']['actionSessionId']
            group = pkg['data']['extra']['last_group_trace']['group']

            
            # 构造 GET 请求
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url=os.getenv(
                        "GROUP_SUMMARY_API_URL",
                        "http://127.0.0.1:48080/api/example/group-summary",
                    ),
                    params={
                        "actionSessionId": action_session_id,
                        "group": group
                    },
                    headers={
                        "Authorization": f"Bearer {token}"
                    },
                    timeout=120
                )
                resp.raise_for_status()
                result = resp.json()

            if result.get("code") != 0:
                raise RuntimeError(f"接口返回异常: {result.get('msg')}")
            
            await self.wait_for_event()
            
            
            data = result.get("data", {})
            print('result_data', data)
            await self.set_output('pic_res', {
                "viewSummaryText": data.get("viewSummaryText", ""),
                "ttsSummaryText": data.get("ttsSummaryText", ""),
                "errorSnapshot": data.get("errorSnapshot", {}).get("imageUrl", ""),
                "errorMessage": data.get("errorSnapshot", {}).get("errorMessage", "")
            })
            '''
            await self.set_output('pic_res', {
                "viewSummaryText": "",
                "ttsSummaryText": "",
                "errorSnapshot": "",
            })
            '''
            self.set_choice('default')

        except Exception as e:
            print("get pic error:", e)
        return True   

@register_class('send_decision1')
class SendDecision1(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "pic_res": "step",
            "summary_content": "step",
            "audio_data": "step"
        }
        self.output_parameters = {
            "last_message_id": "step",
        }
        self.choices = ['default']

        self.step_name = config['attrs'].get('step_name')
        self.status = config['attrs'].get('status')
        self.extra_text = config['attrs'].get('extra_text', '')
    async def run(self, input_parameters: dict=[]):
        try:
            pic_res = await self.get_input('pic_res')
            summary_content = await self.get_input('summary_content')
            audio_data = await self.get_input('audio_data')
            #等待事件触发（输出事件）
            await self.wait_for_event()
            print('after wait_for_event send_decision1')
            resource_dict = {}
            if pic_res and pic_res["errorSnapshot"]:
                resource_dict["image"] = [{
                    "type": "url",
                    "url": pic_res["errorSnapshot"]
                }]
            if summary_content:
                resource_dict["text"] = [{
                    "type": "text",
                    "content": summary_content.get("point_1","") + summary_content.get("point_2","")
                }]
            else:
                resource_dict["text"] = [{
                    "type": "text",
                    "content": self.extra_text
                }]
            
            
            if audio_data:
                resource_dict["audio"] = [{
                    "type": "stream",
                    "data_id": 0,
                    "data": audio_data,
                    "pos": 0
                }]

            response = {
                "step": self.step_name,
                "status": self.status,
                "data": {
                    "resource": resource_dict
                },
            }
            last_message_id = await self.parent_workflow.get_context('handler').send_message(response)

            # 设置输出参数'last_message_id'
            await self.set_output('last_message_id', last_message_id)
            
            # 设置下一个节点选择为'default'
            self.set_choice('default')
        except Exception as e:
            print("send decision1 error:", e)
        return True


@register_class('text_append')
class TextAppend(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "content_0": "step",
            "content_1": "step",
            "content_2": "step"
        }
        self.output_parameters = {
            "content": "step",
        }
        self.choices = ['default']

        key_0 =  config['attrs'].get('key_0', "")
        key_1 = config['attrs'].get('key_1', "")
        key_2 = config['attrs'].get('key_2', "")
        self.keys = [key_0, key_1, key_2]

    async def run(self, input_parameters: dict=[]):
        try:
            
            res_text = ""
            for i in range(3):
                tmp_content = await self.get_input(f'content_{i}')
                if tmp_content:
                    if self.keys[i]:
                        res_text += tmp_content[self.keys[i]]
                    else:
                        res_text += tmp_content
            
            await self.wait_for_event()


            await self.set_output('content', res_text)
            
            
            # 设置下一个节点选择为'default'
            self.set_choice('default')
        except Exception as e:
            print("text append error:", e)
        return True


@register_class('judge_decision2')
class JudgeDecision2(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "llm_res": "step"
        }
        self.output_parameters = {
            "choice": "step"
        }
        self.choices = ['asr','skip']
    async def run(self, input_parameters: dict=[]):
        llm_res = await self.get_input('llm_res')
        # 设置输出参数'last_message_id'
        await self.wait_for_event()
        
        if llm_res.get('need_to_communicate',False):
            
            await self.set_output('choice', 'asr')
            print('choose asr==============')
            self.set_choice('asr')
        else:
            await self.set_output('choice', 'skip')
            print('choose skip==============')
            self.set_choice('skip')
        '''
        
        await self.set_output('choice', 'skip')
        self.set_choice('skip')
        '''

        return True

@register_class('send_decision2')
class SendDecision2(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "llm_res": "step",
            "audio_data": "step"
        }
        self.output_parameters = {
            "last_message_id": "step",
        }
        self.choices = ['default']

        self.step_name = config['attrs'].get('step_name')
        self.status = config['attrs'].get('status')
    async def run(self, input_parameters: dict=[]):
        
        llm_res = await self.get_input('llm_res')
        text_content = llm_res.get('message','')
        audio_data = await self.get_input('audio_data')
        #等待事件触发（输出事件）
        await self.wait_for_event()
        resource_dict = {}
        if text_content:
            resource_dict["text"] = [{
                "type": "text",
                "content": text_content
            }]
        
        if audio_data:
            resource_dict["audio"] = [{
                "type": "stream",
                "data_id": 0,
                "data": audio_data,
                "pos": 0
            }]

        response = {
            "step": self.step_name,
            "status": self.status,
            "data": {
                "resource": resource_dict
            },
        }
        last_message_id = await self.parent_workflow.get_context('handler').send_message(response)

        # 设置输出参数'last_message_id'
        await self.set_output('last_message_id', last_message_id)
        
        # 设置下一个节点选择为'default'
        self.set_choice('default')     
            
@register_class('before_decision3')
class BeforeDecision3(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "choice": "step",
            "llm_res": "step",
            'asr_text': 'step',
            'trace': 'step'
        }
        self.output_parameters = {
            'params': 'step',
        }
        self.choices = ['default']
    async def run(self, input_parameters: dict=[]):
        choice = await self.get_input('choice')
        if choice == 'asr':
            user_response = await self.get_input('asr_text')
            llm_res = await self.get_input('llm_res')
            coach_question = llm_res.get('message','')
            communication_result = "教练提问：" + coach_question + "，用户回复：" + user_response
        else:
            communication_result = ''

        trace = await self.get_input('trace')
        quality_checkpoints = json.dumps(trace.get('quality_checkpoints',{}))

        await self.wait_for_event()
                
        
        params = {
            'communication_result': communication_result,
            'user_goal': '保持健康',
            'quality_checkpoints': quality_checkpoints,
        }
        await self.set_output('params', params)
        self.set_choice('default')
        return True

@register_class('after_decision3')
class AfterDecision3(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "llm_res": "step",
            "params": "step",
        }
        self.output_parameters = {
            'text_content': 'step',
            "last_message_id": "step",
            "adjust_result": "step"
        }
        self.choices = ['default']

        self.step_name = config['attrs'].get('step_name')
        self.status = config['attrs'].get('status')

    async def run(self, input_parameters: dict=[]):
        try:
            params = await self.get_input('params')
            llm_res = await self.get_input('llm_res')
            should_adjust = llm_res.get('should_adjust',False)
            text_content = llm_res.get('reason')

            quality_checkpoints = params.get('quality_checkpoints',{})
            quality_list = list(quality_checkpoints.items())


            adjust_item = {}
            if should_adjust:
                #text_content += '，这是下一组动作的调整建议'
                ori_adjust_type = llm_res['adjustment'].get('type','')
                if ori_adjust_type == 'CHANGE_REP_COUNT':
                    detect_title = quality_list[0][1].get('title','')
                    
                    adjust_item = [{
                        "type": 'rep',
                        "original_rep": llm_res['adjustment'].get('old_reps',10),
                        "new_rep": llm_res['adjustment'].get('new_reps', 8),
                        "rep_title": "调整训练次数",
                        "detect_title": detect_title,
                        "req": ""
                    }]
                elif ori_adjust_type == 'CHANGE_QUALITY_STANDARD':
                    old_standard = llm_res['adjustment'].get('old_standard','')
                    new_standard = llm_res['adjustment'].get('new_standard','')
                    standard_list = ['low','medium','high']
                    # 判断old和new在standard_list中的顺序
                    old_index = standard_list.index(old_standard)
                    new_index = standard_list.index(new_standard)
                    if old_index > new_index:
                        direction = 'down'
                    else:
                        direction = 'up'

                    tmp_title = quality_list[0][1].get('title','')
                    tmp_req = quality_list[0][1].get('req','')
                    if llm_res['adjustment'].get('checkpoint_id','') in quality_checkpoints:
                        tmp_title = quality_checkpoints[llm_res['adjustment'].get('checkpoint_id','')].get('title','')
                        tmp_req = quality_checkpoints[llm_res['adjustment'].get('checkpoint_id','')].get('req','')

                    adjust_item = [{
                        "type": 'detect',
                        "old_level": old_index+1,
                        "new_level": new_index+1,
                        "direction": direction,
                        "rep_title": "调整训练次数",
                        "detect_title": tmp_title,
                        "req": tmp_req
                    }]
            else:
                text_content += "，我们不需要调整动作，休息后准备下一组动作"
            
            await self.wait_for_event()
            
            await self.set_output('text_content', text_content)
            await self.set_output('adjust_result', {
                "should_adjust": should_adjust,
                "reason": text_content,
                "adjust": json.dumps(adjust_item[0]),
                "req": adjust_item[0].get('req','')
            })
            if should_adjust:
                response = {
                    "step": self.step_name,
                    "status": self.status,
                    "data": {
                        "extra":{
                            "content": text_content,
                            "should_adjust": should_adjust,
                            "adjust": adjust_item,
                        }
                    }
                }
            else:
                response = {
                    "step": self.step_name,
                    "status": self.status,
                    "data": {
                        "extra":{
                            "content": text_content,
                            "should_adjust": should_adjust
                        }
                    }
                }
            print('send decision')
            print(response)
            last_message_id = await self.parent_workflow.get_context('handler').send_message(response)
            await self.set_output('last_message_id', last_message_id)

            # 设置下一个节点选择为'default'
            self.set_choice('default')
        except Exception as e:
            print('send suggest error', e)
            
        return True

@register_class('send_decision3_audio')
class SendDecision3Audio(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "audio_data": "step"
        }
        self.output_parameters = {
            "last_message_id": "step",
        }
        self.choices = ['default']

        self.step_name = config['attrs'].get('step_name')
        self.status = config['attrs'].get('status')
    async def run(self, input_parameters: dict=[]):
        
        audio_data = await self.get_input('audio_data')
        #等待事件触发（输出事件）
        await self.wait_for_event()
        resource_dict = {}
    
        if audio_data:
            resource_dict["audio"] = [{
                "type": "stream",
                "data_id": 0,
                "data": audio_data,
                "pos": 0
            }]

        response = {
            "step": self.step_name,
            "status": self.status,
            "data": {
                "resource": resource_dict
            },
        }
        last_message_id = await self.parent_workflow.get_context('handler').send_message(response)

        # 设置输出参数'last_message_id'
        await self.set_output('last_message_id', last_message_id)
        
        # 设置下一个节点选择为'default'
        self.set_choice('default')  

    




@register_class('get_report')
class GetReportNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "pkg": "step",
        }
        self.output_parameters = {
            'content': 'step',
            'pic': 'step'
        }
        self.choices = ['default']

    async def run(self, input_parameters: dict=[]):
        print("waiting for pkg", self.name)
        try:
            pkg = await self.get_input('pkg')
            print("recv pkg:", self.name)
            await self.wait_for_event()
            print("after waiting,", self.name)
        

            await self.set_output('content', {
                'type': "text",
                'data': {
                    'type': 'step',
                    'content': "本组完成10次，其中2次为高质量动作"
                }
            })
            await self.set_output('pic', {
                'type': "image",
                'data': {
                    'type': 'url',
                    'url': 'https://example.com/images/example.png'
                }
            })

            self.set_choice('default')
        except Exception as e:
            print("judge error:", e)
        print('judge_ok,', self.name)
        return True



@register_class('get_motion_change')
class GetMotionChangeNode(BaseNode):
    def __init__(self, config, workflow):
        # 调用父类初始化方法
        super().__init__(config, workflow, NodeType.BaseNode) 
        self.input_parameters = {
            "asr_text": "step",
        }
        self.output_parameters = {
            'content': 'step',
            'adjust': 'step'
        }
        self.choices = ['default']

    async def run(self, input_parameters: dict=[]):
        asr_text = await self.get_input('asr_text')
        await self.wait_for_event()

        await self.set_output('content', "需要调整")
        await self.set_output('adjust', [{ 
                "type": "rep", 
                "original_rep" : 10, 
                "new_rep": 12, 
                "title": "调整数量" 
            },{
                "type": "detect", 
                "idList": ["2", "3"], 
                "parameters":  [[45.0, 100.0, 150.0, 180.0, 55.0, 75.0, 165.0, 180.0], [40.0, 100.0, 165.0, 180.0, 65.0, 90.0, 170.0, 180.0]], 
                "content": [{ 
                    "title": "核心稳定要求", 
                    "choices": ["偏低","标准","偏高"], 
                    "original_choice": 0, 
                    "new_choice": 1
                }]
            }])

        self.set_choice('default')

        return True

