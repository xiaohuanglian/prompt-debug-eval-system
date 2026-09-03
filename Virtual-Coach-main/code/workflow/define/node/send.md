# 发送节点

文件位置：[nodes/check_confirm.py](../../nodes/check_confirm.py)
命名规范：send_xx 或 send_data_xx

### SendAudioDispatchNode

**注册名称**: `send_audio_dispatch`

**功能**: 根据状态分发不同类型的音频响应。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名       | 类型 | 说明                                             |
| ------------ | ---- | ------------------------------------------------ |
| `pkg_step` | step | 步骤名称                                         |
| `adjust`   | step | 调整参数                                         |
| `status`   | step | 状态（good/improved/not_improved/other_problem） |

#### 输出参数

| 参数名       | 类型 | 说明     |
| ------------ | ---- | -------- |
| `response` | step | 响应消息 |

#### 分支选择

根据 `status` 自动选择分支：

- `good`
- `improved`
- `not_improved`
- `other_problem`

#### 配置属性

```python
{
    'attrs': {
        'audio_url': {
            'good': {'type': 'url', 'url': '...', 'text': '...'},
            'improved': {'type': 'tts'},
            # ... 其他状态配置
        }
    }
}
```

### SendAudioDataNode

**注册名称**: `send_audio_data`

**功能**: 发送音频数据到客户端。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名       | 类型 | 说明         |
| ------------ | ---- | ------------ |
| `response` | step | 响应消息模板 |
| `data`     | step | 音频数据     |

#### 输出参数

无（直接发送到客户端）

## 参考：

### Type: send_ack | Name: send_no_data_ack

{"id": 200, "node_type": "send_ack", "node_name": "send_no_data_ack", "input_map": {"last_message_id": "receive_user_info.last_message_id"}, "choice_map": {"default": "send_decision1_no_data"}, "attrs": {"step_name": "before"}}

### Type: send_ack | Name: send_report_ack

{"id": 100, "node_type": "send_ack", "node_name": "send_report_ack", "input_map": {"last_message_id": "receive_user_info.last_message_id"}, "choice_map": {"default": "download_pic"}, "attrs": {"step_name": "before"}}

### Type: send_audio_data | Name: send_data_XX

{"id": 11, "node_type": "send_audio_data", "node_name": "send_data_02", "input_map": {"response": "audio_dispatch_02.response", "data": "tts_02.pcm_data"}, "choice_map": {"default": "receive_03"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow"}}
{"id": 17, "node_type": "send_audio_data", "node_name": "send_data_03", "input_map": {"response": "audio_dispatch_03.response", "data": "tts_03.pcm_data"}, "choice_map": {"default": "finish"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow"}}

### Type: send_audio_dispatch | Name: audio_dispatch_XX

{"id": 2, "node_type": "send_audio_dispatch", "node_name": "audio_dispatch_00", "key_node": true, "input_map": {"pkg_step": "judge_00.pkg_step", "adjust": "judge_00.adjust", "status": "judge_00.status"}, "choice_map": {"good": "finish", "improved": "receive_01", "not_improved": "receive_01", "other_problem": "receive_01"}, "attrs": {"audio_url": {"good": {"type": "url", "url": "https://example.com/media/service_audio/good_0.wav", "text": "厉害，一次就调整到位了，咱们继续。"}, "improved": {"type": "url", "url": "https://example.com/media/service_audio/error_0_qukuan.wav", "text": "这次深蹲屈髋的幅度还不够，要再多点，你再做一个我看看"}, "not_improved": {"type": "url", "url": "https://example.com/media/service_audio/error_0_qukuan.wav", "text": "这次深蹲屈髋的幅度还不够，要再多点，你再做一个我看看"}, "other_problem": {"type": "url", "url": "https://example.com/media/service_audio/other_problem_1.wav", "text": "也不用刻意往后蹲很多，背都弯了，稍微回来点，再来一个"}}}}
{"id": 5, "node_type": "send_audio_dispatch", "node_name": "audio_dispatch_01", "key_node": true, "input_map": {"pkg_step": "judge_01.pkg_step", "adjust": "judge_01.adjust", "status": "judge_01.status"}, "choice_map": {"good": "finish", "improved": "receive_02", "not_improved": "receive_02", "other_problem": "receive_02"}, "attrs": {"audio_url": {"good": {"type": "url", "url": "https://example.com/media/service_audio/good_0.wav", "text": "厉害，一次就调整到位了，咱们继续。"}, "improved": {"type": "url", "url": "https://example.com/media/service_audio/improved_1.wav", "text": "很好，你的屈髋幅度比上一个动作有明显进步，我们再来一个"}, "not_improved": {"type": "url", "url": "https://example.com/media/service_audio/not_improved_1.wav", "text": "加油，屈髋再多一些，我们再来一个"}, "other_problem": {"type": "url", "url": "https://example.com/media/service_audio/other_problem_1.wav", "text": "也不用刻意往后蹲很多，背都弯了，稍微回来点，再来一个"}}}}
{"id": 8, "node_type": "send_audio_dispatch", "node_name": "audio_dispatch_02", "key_node": true, "input_map": {"pkg_step": "judge_02.pkg_step", "adjust": "judge_02.adjust", "status": "judge_02.status"}, "choice_map": {"good": "finish", "improved": "llm_stream_02", "not_improved": "receive_03", "other_problem": "receive_03"}, "attrs": {"audio_url": {"good": {"type": "url", "url": "https://example.com/media/service_audio/good_1.wav", "text": "厉害，一次就调整到位了，咱们继续。"}, "improved": {"type": "tts"}, "not_improved": {"type": "url", "url": "https://example.com/media/service_audio/not_improved_1.wav", "text": "加油，屈髋再多一些，我们再来一个"}, "other_problem": {"type": "url", "url": "https://example.com/media/service_audio/other_problem_1.wav", "text": "也不用刻意往后蹲很多，背都弯了，稍微回来点，再来一个"}}}}
{"id": 14, "node_type": "send_audio_dispatch", "node_name": "audio_dispatch_03", "key_node": true, "input_map": {"pkg_step": "judge_03.pkg_step", "adjust": "judge_03.adjust", "status": "judge_03.status"}, "choice_map": {"good": "finish", "improved": "llm_stream_03", "not_improved": "llm_stream_03", "other_problem": "llm_stream_03"}, "attrs": {"audio_url": {"good": {"type": "url", "url": "https://example.com/media/service_audio/good_2.wav", "text": "厉害，一次就调整到位了，咱们继续。"}, "improved": {"type": "tts"}, "not_improved": {"type": "tts"}, "other_problem": {"type": "tts"}}}}

### Type: send_decisionX | Name: send_decisionX_audio

{"id": 106, "node_type": "send_decision1", "node_name": "send_decision1_audio", "input_map": {"pic_res": null, "summary_content": null, "audio_data": "summary_tts.pcm_data"}, "choice_map": {"default": "receive_step_0_audio_ack"}, "attrs": {"step_name": "step_0", "status": "audio"}}

### Type: send_decisionX | Name: send_decisionX_content

{"id": 110, "node_type": "send_decision2", "node_name": "send_decision2_content", "input_map": {"llm_res": "decision_point_2.content", "audio_data": "question_tts.pcm_data"}, "choice_map": {"default": "receive_step_1_visual_audio_ack"}, "attrs": {"step_name": "step_1", "status": "visual_audio"}}

### Type: send_decisionX | Name: send_decisionX_no_data

{"id": 201, "node_type": "send_decision1", "node_name": "send_decision1_no_data", "input_map": {"pic_res": null, "summary_content": null, "audio_data": null}, "choice_map": {"default": "finish"}, "attrs": {"step_name": "step_0", "status": "visual", "extra_text": "有效动作过少，分析卡壳了"}}

### Type: send_decisionX | Name: send_decisionX_visual

{"id": 104, "node_type": "send_decision1", "node_name": "send_decision1_visual", "input_map": {"pic_res": "download_pic.pic_res", "summary_content": "inter_summary.content", "audio_data": null}, "choice_map": {"default": "receive_step_0_visual_ack"}, "attrs": {"step_name": "step_0", "status": "visual"}}

### Type: send_decisionX_audio | Name: send_decisionX_audio_node

{"id": 115, "node_type": "send_decision3_audio", "node_name": "send_decision3_audio_node", "input_map": {"audio_data": "suggestion_tts.pcm_data"}, "choice_map": {"default": "receive_step_2_audio_ack"}, "attrs": {"step_name": "step_1", "status": "audio"}}
