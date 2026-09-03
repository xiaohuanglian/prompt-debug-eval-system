# TTS节点

文件位置：[nodes/tts_node.py](../../nodes/tts_node.py)
命名规范：tts_xx

TTS 节点提供文本转语音功能，支持多种输入输出组合。

### TTSStep2Step

**注册名称**: `tts_step2step`

**功能**: 将文本转换为 PCM 音频数据（步骤输入 → 步骤输出）。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名      | 类型 | 说明             |
| ----------- | ---- | ---------------- |
| `content` | step | 待转换的文本内容 |

#### 输出参数

| 参数名       | 类型 | 说明                  |
| ------------ | ---- | --------------------- |
| `pcm_data` | step | PCM 音频数据（bytes） |

#### 配置属性

| 属性名         | 类型 | 默认值    | 说明                   |
| -------------- | ---- | --------- | ---------------------- |
| `encode`     | bool | False     | 是否使用 base64 编码   |
| `speaker_id` | str  | 'default' | 发音人ID               |
| `key`        | str  | None      | 从字典中提取特定键的值 |

### TTSStep2Stream

**注册名称**: `tts_step2stream`

**功能**: 将文本转换为 PCM 音频流（步骤输入 → 流式输出）。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名      | 类型 | 说明             |
| ----------- | ---- | ---------------- |
| `content` | step | 待转换的文本内容 |

#### 输出参数

| 参数名         | 类型   | 说明       |
| -------------- | ------ | ---------- |
| `pcm_stream` | stream | PCM 音频流 |

#### 输出格式

```python
{
    'data': bytes_data,
    'status': 0/1/2  # 0: 开始, 1: 进行中, 2: 结束
}
```

### TTSStream2Step

**注册名称**: `tts_stream2step`

**功能**: 将文本流转换为完整的 PCM 音频数据（流式输入 → 步骤输出）。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名      | 类型   | 说明   |
| ----------- | ------ | ------ |
| `content` | stream | 文本流 |

#### 输出参数

| 参数名       | 类型 | 说明                |
| ------------ | ---- | ------------------- |
| `pcm_data` | step | 完整的 PCM 音频数据 |

### TTSStream2Stream

**注册名称**: `tts_stream2stream`

**功能**: 将文本流转换为 PCM 音频流（流式输入 → 流式输出）。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名      | 类型   | 说明   |
| ----------- | ------ | ------ |
| `content` | stream | 文本流 |

#### 输出参数

| 参数名         | 类型   | 说明       |
| -------------- | ------ | ---------- |
| `pcm_stream` | stream | PCM 音频流 |

### TTSStep2File

**注册名称**: `tts_step2file`

**功能**: 将 PCM 音频数据保存为 WAV 文件（步骤输入 → 文件输出）。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名   | 类型 | 说明         |
| -------- | ---- | ------------ |
| `data` | step | PCM 音频数据 |

#### 输出参数

无（直接写入文件）

#### 配置属性

```python
{
    'attrs': {
        'encode': False,  # 是否 base64 编码
        'file': {
            'path': 'output.wav',  # 文件路径
            'channels': 1,         # 声道数
            'sample_rate': 16000,  # 采样率
            'sample_width': 2      # 采样宽度（字节）
        }
    }
}
```

### TTSStream2File

**注册名称**: `tts_stream2file`

**功能**: 将 PCM 音频流保存为 WAV 文件（流式输入 → 文件输出）。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名      | 类型   | 说明       |
| ----------- | ------ | ---------- |
| `content` | stream | PCM 音频流 |

#### 输出参数

无（直接写入文件）

#### 配置属性

同 `TTSStep2File`

## 参考：

### Type: tts_stepXstep | Name: question_tts

{"id": 109, "node_type": "tts_step2step", "node_name": "question_tts", "input_map": {"content": "decision_point_2.content"}, "choice_map": {"default": "send_decision2_content"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow", "key": "message"}}

### Type: tts_stepXstep | Name: suggestion_tts

{"id": 114, "node_type": "tts_step2step", "node_name": "suggestion_tts", "input_map": {"content": "adjust_reason_text.content"}, "choice_map": {"default": "send_decision3_audio_node"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow"}}

### Type: tts_stepXstep | Name: summary_tts

{"id": 105, "node_type": "tts_step2step", "node_name": "summary_tts", "input_map": {"content": "tts_append.content"}, "choice_map": {"default": "send_decision1_audio"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow"}}

### Type: tts_streamXstep | Name: tts_XX

{"id": 10, "node_type": "tts_stream2step", "node_name": "tts_02", "input_map": {"content": "llm_stream_02.content"}, "choice_map": {"default": "send_data_02"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow"}}
{"id": 16, "node_type": "tts_stream2step", "node_name": "tts_03", "input_map": {"content": "llm_stream_03.content"}, "choice_map": {"default": "send_data_03"}, "attrs": {"encode": true, "speaker_id": "x5_lingfeiyi_flow"}}

### Type: text_append | Name: tts_append

{"id": 302, "node_type": "text_append", "node_name": "tts_append", "input_map": {"content_0": "inter_summary.content", "content_1": "pic_summary.content", "content_2": null}, "choice_map": {"default": "summary_tts"}, "attrs": {"key_0": "sumrization"}}
