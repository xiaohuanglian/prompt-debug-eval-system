
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

@register_class('tts_step2step')
class TTSStep2Step(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        #print('setup child')
        self.input_parameters = {
            'content': 'step'
            }
        self.output_parameters = {
            'pcm_data': 'step'
            }
        self.choices = ['default']
        self.encode_flag = config['attrs'].get('encode', False)

        self.speaker_id = config['attrs'].get('speaker_id', 'default')
        self.key = config['attrs'].get('key', None)

        
        
    async def run(self, input_parameters: dict=[]):
        try:
            print('running tts===============')

            tts_client = self.parent_workflow.get_context('tts_xunfei')

            content = await self.get_input('content')
            
            if self.key:
                content = content[self.key]

            print("after get input:======================", content)

            data = await tts_client.process_step(content, self.speaker_id, encode=self.encode_flag)
            
            #print("step:",data)

            await self.wait_for_event()

            print('after wait_event')

            await self.set_output('pcm_data', data)
            

            print('after output pcm_data')

            self.set_choice('default')
            
            print('after after output pcm_data')
        except Exception as e:
            print('!!!!!!!!!!!!!tts_step2step error:', e)
        return True
     
@register_class('tts_step2stream')
class TTSStep2Stream(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        #print('setup child')
        self.input_parameters = {
            'content': 'step'
            }
        self.output_parameters = {
            'pcm_stream': 'stream'
            }
        self.choices = ['default']
        self.encode_flag = config['attrs'].get('encode', False)
    
    async def internal_callback(self, data, status):
        
        await self.set_output('pcm_stream', {
            'data': data,
            'status': status
        })


    async def run(self, input_parameters: dict=[]):

        tts_client = self.parent_workflow.get_context('tts_xunfei')

        content = await self.get_input('content')
        
        await self.wait_for_event()
        self.set_choice('default')
        
        data = await tts_client.process_step(content, self.attrs['speaker_id'], encode=self.encode_flag, on_message_recall=self.internal_callback)

        
        
        return True
        
     
@register_class('tts_stream2step')
class TTSStream2Step(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        #print('setup child')
        self.input_parameters = {
            'content': 'stream'
            }
        self.output_parameters = {
            'pcm_data': 'step'
            }
        self.choices = ['default']
        self.encode_flag = config['attrs'].get('encode', False)
    


    async def run(self, input_parameters: dict=[]):
        #print('tts_stream2step1------------')
        tts_client = self.parent_workflow.get_context('tts_xunfei')
        #print('tts_stream2step2----------')
        msg_queue = asyncio.Queue()
        #print('tts_stream2step3---------')
        
        task = None
        
        #print('tts_stream2step4--------')
        choice_flag = True
        
        while True:
            #print('tts_stream2step5-----------')
            content = await self.get_input('content')
            if task is None:
                task = asyncio.create_task(tts_client.process_stream(self.attrs['speaker_id'], msg_queue, self.encode_flag))
            
            #print('tts content', content)
            await msg_queue.put(content)

            if content['status'] == 2:
                break
        
        data_byte = await task
        await self.wait_for_event()
        #print('tts_stream2step6-----------data_byte')
        #print(len(data_byte))
        await self.set_output('pcm_data', data_byte)
        self.set_choice('default')
        return True
        
@register_class('tts_stream2stream')
class TTSStream2Stream(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 

        #print('setup child')
        self.input_parameters = {
            'content': 'stream'
            }
        self.output_parameters = {
            'pcm_stream': 'stream'
            }
        self.choices = ['default']
        self.encode_flag = config['attrs'].get('encode', False)
    
    async def internal_callback(self, data, status):
        
        await self.set_output('pcm_stream', {
            'data': data,
            'status': status
        })


    async def run(self, input_parameters: dict=[]):
        
        tts_client = self.parent_workflow.get_context('tts_xunfei')

        msg_queue = asyncio.Queue()

        task = asyncio.create_task(tts_client.process_stream(self.attrs['speaker_id'], msg_queue. self.encode_flag, on_message_recall=self.internal_callback))

        choice_flag = True
        
        while True:
        
            content = await self.get_input('content')
            
            if choice_flag:
                await self.wait_for_event()
                self.set_choice('default')
                choice_flag = False

            await msg_queue.put(content)

            if content['status'] == 2:
                break
        
        await task

        return True
    

@register_class('tts_step2file')
class TTSStep2File(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 
        
        self.input_parameters = {
            'data': 'step'
        }
        self.output_parameters = {}
        self.choices = ['default']

        self.encode_flag = config['attrs'].get('encode', False)
        self.file_attr = config['attrs']['file']
    
    async def run(self, input_parameters: dict=[]):

        data = await self.get_input('data')
        
        if self.encode_flag:
            decode_data = base64.b64decode(data)
        else:
            decode_data = data
        
        await self.wait_for_event()

        channels = self.file_attr.get('channels', 1)
        sample_rate = self.file_attr.get('sample_rate', 16000)
        sample_width = self.file_attr.get('sample_width', 2)
        
        with wave.open(self.file_attr['path'], 'wb') as wav_file:
            # 设置音频参数
            wav_file.setnchannels(channels)  # 声道数
            wav_file.setsampwidth(sample_width)  # 采样宽度（字节）
            wav_file.setframerate(sample_rate)  # 采样率
            
            # 计算帧数：总字节数 / (每个采样的字节数 × 声道数)
            # 每个采样的字节数 = sample_width，每个帧包含所有声道的一个采样
            n_frames = len(decode_data) // (sample_width * channels)
            wav_file.setnframes(n_frames)
            
            # 设置压缩类型（WAV默认无压缩）
            wav_file.setcomptype('NONE', 'not compressed')
            
            # 写入PCM数据
            wav_file.writeframes(decode_data)
        
        self.set_choice('default')
        return True


@register_class('tts_stream2file')
class TTSStream2File(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode) 
        
        self.input_parameters = {
            'content': 'stream'
        }
        self.output_parameters = {}
        self.choices = ['default']

        self.encode_flag = config['attrs'].get('encode', False)
        self.file_attr = config['attrs']['file']
    
    async def run(self, input_parameters: dict=[]):

        
        tot_data = bytes()

        while True:
        
            content = await self.get_input('content')
            if self.encode_flag:
                data = base64.b64decode(content['data'])
            else:
                data = content['data']
            tot_data += data
            
            if content['status'] == 2:
                break
    
        await self.wait_for_event()

        channels = self.file_attr.get('channels', 1)
        sample_rate = self.file_attr.get('sample_rate', 16000)
        sample_width = self.file_attr.get('sample_width', 2)
        
        with wave.open(self.file_attr['path'], 'wb') as wav_file:
            # 设置音频参数
            wav_file.setnchannels(channels)  # 声道数
            wav_file.setsampwidth(sample_width)  # 采样宽度（字节）
            wav_file.setframerate(sample_rate)  # 采样率
            
            # 计算帧数：总字节数 / (每个采样的字节数 × 声道数)
            # 每个采样的字节数 = sample_width，每个帧包含所有声道的一个采样
            n_frames = len(tot_data) // (sample_width * channels)
            wav_file.setnframes(n_frames)
            
            # 设置压缩类型（WAV默认无压缩）
            wav_file.setcomptype('NONE', 'not compressed')
            
            # 写入PCM数据
            wav_file.writeframes(tot_data)
        
        self.set_choice('default')
        return True



    
