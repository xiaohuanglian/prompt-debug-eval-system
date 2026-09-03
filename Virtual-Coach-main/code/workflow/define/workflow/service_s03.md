# **组内动作调整指导工作流**

service_s03是一个用于组内动作调整指导的工作流，具体功能包括：
1.实时接收用户动作数据
2.判断动作质量
3.提供个性化反馈和指导

## service_s03 工作流详解

**功能**: 在用户进行一组深蹲动作时，实时接收动作数据，判断动作质量，提供个性化的反馈和指导。

### 工作流概览

```
开始→ receive_00 → judge_00 → audio_dispatch_00 ┬─→ good → finish
                                              ├─→ improved/not_improved/other_problem → receive_01 → judge_01 → audio_dispatch_01 ┬─→ good → finish
                                              │                                                                                                              ├─→ improved/not_improved/other_problem → receive_02 → judge_02 → audio_dispatch_02 ┬─→ good → finish
                                              │                                                                                                              │                                                                                                              ├─→ not_improved/other_problem → receive_03 → judge_03 → audio_dispatch_03 ─┐
                                              │                                                                                                              │                                                                                                              └─→ improved → llm_stream_02 → tts_02 → send_data_02 ────────────────────────────────────────────────┘
                                              │                                                                                                                                                                                                                                                ┌─→ good → finish
                                              │                                                                                                                                                                                                                                                ├─→ improved/not_improved/other_problem → llm_stream_03 → tts_03 → send_data_03 → finish
```

### 节点详细说明

#### 1. receive_00 / receive_01 / receive_02 / receive_03

**节点类型**: `receive_message`

**功能**: 接收客户端发送的动作数据包

**输入参数**: 无（从消息队列接收）

**输出参数**:

- `pkg`: 接收到的消息包
- `last_message_id`: 消息ID

**配置**:

```json
{
    "key_node": true,
    "msg_queue": true
}
```

**下一跳**: `judge_00` / `judge_01` / `judge_02` / `judge_03`

---

#### 2. judge_00 / judge_01 / judge_02 / judge_03

**节点类型**: `judge_motion`

**功能**: 分析用户动作数据，判断动作质量（good/improved/not_improved/other_problem）

**输入参数**:

```json
{
    "pkg": "receive_xx.pkg"  // 从对应的 receive 节点获取
}
```

**输出参数**:

- `pkg_step`: 步骤名称
- `adjust`: 调整参数（如果需要）
- `status`: 动作状态
- `prompt_item`: 提示词项（用于 LLM 生成反馈）

**判断逻辑**:

- **good**: 动作得分 > 0.001，动作标准
- **improved**: 趋势为改善
- **not_improved**: 趋势为恶化
- **other_problem**: 存在其他错误（如角度过小）

**下一跳**: `audio_dispatch_xx`

---

#### 3. audio_dispatch_00 / audio_dispatch_01 / audio_dispatch_02 / audio_dispatch_03

**节点类型**: `send_audio_dispatch`

**功能**: 根据动作状态分发不同类型的反馈（预录音频或 TTS）

**输入参数**:

```json
{
    "pkg_step": "judge_xx.pkg_step",
    "adjust": "judge_xx.adjust",
    "status": "judge_xx.status"
}
```

**配置属性**:

```json
{
    "audio_url": {
        "good": {
            "type": "url",  // 预录音频
            "url": "https://...",
            "text": "厉害，一次就调整到位了，咱们继续。"
        },
        "improved": {
            "type": "url",  // 或 "tts"（实时生成）
            "url": "https://...",
            "text": "这次深蹲屈髋的幅度还不够，要再多点，你再做一个我看看"
        },
        "not_improved": { ... },
        "other_problem": { ... }
    }
}
```

**分支映射**:

```json
{
    "good": "finish",                    // 动作标准 → 结束
    "improved": "receive_01",            // 有改善 → 继续接收
    "not_improved": "receive_01",        // 未改善 → 继续接收
    "other_problem": "receive_01"        // 其他问题 → 继续接收
}
```

**特殊说明**:

- audio_dispatch_02 的 improved 分支使用 TTS（`"type": "tts"`），跳转到 `llm_stream_02`
- audio_dispatch_03 的 improved/not_improved/other_problem 分支都使用 TTS，跳转到 `llm_stream_03`

---

#### 4. llm_stream_02 / llm_stream_03

**节点类型**: `llm_stream`

**功能**: 使用 LLM 生成个性化的动作指导反馈

**输入参数**:

```json
{
    "prompt_item": "judge_xx.prompt_item"
}
```

**配置属性**:

**llm_stream_02**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "user_question.md",
    "system": "你是一个健身教练，正在给学员动作指导..."
}
```

**llm_stream_03**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "user_adjust.md",
    "system": "你是一个健身教练，当前学员的表现暂时达不到原本的标准..."
}
```

**输出参数**:

- `content`: 流式生成的文本内容

**下一跳**: `tts_xx`

---

#### 5. tts_02 / tts_03

**节点类型**: `tts_stream2step`

**功能**: 将 LLM 生成的文本转换为语音

**输入参数**:

```json
{
    "content": "llm_stream_xx.content"
}
```

**配置属性**:

```json
{
    "encode": true,                      // 使用 base64 编码
    "speaker_id": "x5_lingfeiyi_flow"    // 发音人
}
```

**输出参数**:

- `pcm_data`: PCM 音频数据

**下一跳**: `send_data_xx`

---

#### 6. send_data_02 / send_data_03

**节点类型**: `send_audio_data`

**功能**: 将音频数据发送给客户端

**输入参数**:

```json
{
    "response": "audio_dispatch_xx.response",
    "data": "tts_xx.pcm_data"
}
```

**下一跳**: `receive_03` / `finish`

---

### 工作流程说明

#### 阶段0 (receive_00 → judge_00 → audio_dispatch_00)

1. 接收用户的第一个动作数据
2. 判断动作质量
3. 根据状态分发反馈：
   - good → 结束
   - 有问题 → 进入阶段1

#### 阶段1 (receive_01 → judge_01 → audio_dispatch_01)

1. 接收用户的第二个动作数据
2. 判断动作质量
3. 根据状态分发反馈：
   - good → 结束
   - 有问题 → 进入阶段2

#### 阶段2 (receive_02 → judge_02 → audio_dispatch_02)

1. 接收用户的第三个动作数据
2. 判断动作质量
3. 根据状态分发反馈：
   - good → 结束
   - improved → 使用 LLM + TTS 生成个性化反馈 → 结束
   - not_improved/other_problem → 进入阶段3

#### 阶段3 (receive_03 → judge_03 → audio_dispatch_03)

1. 接收用户的第四个动作数据
2. 判断动作质量
3. 根据状态分发反馈：
   - good → 结束
   - 任何问题 → 使用 LLM + TTS 生成最终反馈 → 结束
