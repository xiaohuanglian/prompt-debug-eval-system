# ASR节点

文件位置：[nodes/asr_node.py](../../nodes/asr_node.py)

### ASRWithVADNode

**注册名称**: `asr_vad`

**功能**: 带语音活动检测（VAD）的语音识别节点，实时接收音频流并进行语音识别。

**节点类型**: `StepNode`

#### 输入参数

| 参数名 | 类型 | 说明                     |
| ------ | ---- | ------------------------ |
| 无     | -    | 通过消息队列接收音频数据 |

#### 输出参数

| 参数名       | 类型 | 说明             |
| ------------ | ---- | ---------------- |
| `asr_text` | step | 识别出的文本内容 |

#### 配置属性

| 属性名                   | 类型 | 默认值 | 说明                       |
| ------------------------ | ---- | ------ | -------------------------- |
| `step_name`            | str  | -      | 步骤名称                   |
| `if_result_audio`      | bool | False  | 是否返回结果音频           |
| `result_audio_empty`   | str  | -      | 空识别结果时的音频文件路径 |
| `result_audio_receive` | str  | -      | 有识别结果时的音频文件路径 |

#### 工作流程

1. 等待接收音频数据包
2. 检测音频包位置（pos=0: 开始，pos=1: 中间，pos=2: 结束）
3. 解码 base64 音频数据
4. 调用 ASR 客户端进行识别
5. 句子结束时触发 `on_sentence_end` 回调
6. 输出识别文本并发送响应

#### 状态机

- `INIT`: 初始状态，等待首帧音频
- `START`: 已启动ASR，处理音频流
- `STOP`: 识别完成，停止处理

## 参考

### Type: asr_vad | Name: step_X_asr

{"id": 8, "node_type": "asr_vad", "node_name": "step_1_asr", "input_map": {}, "choice_map": {"default": "before_decision3_node"}, "attrs": {"step_name": "step_1", "if_result_audio": true, "result_audio_empty": "tmp_pcm/empty.txt", "result_audio_receive": "tmp_pcm/receive.txt"}}
