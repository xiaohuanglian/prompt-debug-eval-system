# **组间休息分析和决策工作流**


between_set是一个用于组间休息分析和决策工作流，具体功能包括：
1.分析组内训练数据
2.生成总结报告
3.决策是否需要调整训练计划
4.与用户进行二次沟通

## between_set 工作流详解

**功能**: 在组间休息时，分析组内训练数据，生成总结报告，决策是否需要调整训练计划，与用户进行二次沟通。

### 工作流概览

```
开始→ receive_user_info → judge_report ┬─→ 有数据 → send_report_ack → download_pic → decision_point_1 → inter_summary → pic_summary → send_decision1_visual → receive_step_0_visual_ack → tts_append → summary_tts → send_decision1_audio → receive_step_0_audio_ack → decision_point_2 → judge_point_2 ┬─→ asr → question_tts → send_decision2_content → receive_step_1_visual_audio_ack → step_1_asr → before_decision3_node → decision_point_3 → after_decision3_node → adjust_reason_text → suggestion_tts → send_decision3_audio_node → receive_step_2_audio_ack → receive_step_2_motion_change_result → finish
                                     │                                                                                                                                                                                                                                                                          └─→ skip → before_decision3_node → ...
                                     └─→ 无数据 → send_no_data_ack → send_decision1_no_data → finish
```

### 节点详细说明

#### 1. receive_user_info

**节点类型**: `receive_message`

**功能**: 接收用户完成的组内训练数据

**输入参数**: 无

**输出参数**:

- `pkg`: 训练数据包
- `last_message_id`: 消息ID

**下一跳**: `judge_report`

---

#### 2. judge_report

**节点类型**: `clac_trace`

**功能**: 计算和分析训练数据，提取统计信息

**输入参数**:

```json
{
    "pkg": "receive_user_info.pkg"
}
```

**输出参数**:

- `params`: 计算后的参数（高质量次数、错误次数、检查点等）
- `parsed_pkg`: 解析后的消息包
- `token`: 认证令牌

**分支映射**:

```json
{
    "default": "send_report_ack",        // 有数据
    "no_data": "send_no_data_ack"        // 无数据
}
```

---

#### 3a. send_report_ack（有数据路径）

**节点类型**: `send_ack`

**功能**: 发送确认消息

**输入参数**:

```json
{
    "last_message_id": "receive_user_info.last_message_id"
}
```

**配置**:

```json
{
    "step_name": "before"
}
```

**下一跳**: `download_pic`

---

#### 3b. send_no_data_ack（无数据路径）

**节点类型**: `send_ack`

**功能**: 发送确认消息（无数据）

**下一跳**: `send_decision1_no_data`

---

#### 4. download_pic

**节点类型**: `get_pic`

**功能**: 从服务器获取错误快照图片和总结文本

**输入参数**:

```json
{
    "pkg": "judge_report.parsed_pkg",
    "token": "judge_report.token"
}
```

**输出参数**:

- `pic_res`: 图片资源结果
  - `viewSummaryText`: 视图总结
  - `ttsSummaryText`: TTS 总结
  - `errorSnapshot`: 错误快照 URL
  - `errorMessage`: 错误消息

**下一跳**: `decision_point_1`

---

#### 5. decision_point_1

**节点类型**: `llm_step`

**功能**: 第一个决策点，判断用户等级和表现分类

**输入参数**:

```json
{
    "params_0": "judge_report.params"
}
```

**配置**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "intergroup_decision1.md",
    "json": true
}
```

**输出**: JSON 格式的决策结果

**下一跳**: `inter_summary`

---

#### 6. inter_summary

**节点类型**: `llm_step`

**功能**: 生成组间总结（两点总结 + 口语化总结）

**输入参数**:

```json
{
    "params_0": "decision_point_1.content",
    "params_1": "judge_report.params"
}
```

**配置**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "intergroup_summary.md",
    "system": "你是一名健身教练...",
    "json": true
}
```

**输出格式**:

```json
{
    "point_1": "第一点总结（≤40字）",
    "point_2": "第二点总结（≤40字）",
    "sumrization": "口语化总结（≤80字）"
}
```

**下一跳**: `pic_summary`

---

#### 7. pic_summary

**节点类型**: `llm_step`

**功能**: 基于错误快照生成图片总结

**输入参数**:

```json
{
    "params_0": "judge_report.params",
    "params_1": "download_pic.pic_res"
}
```

**配置**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "pic_summary.md",
    "system": "你是一名健身教练..."
}
```

**输出**: 图片总结文本（≤40字）

**下一跳**: `send_decision1_visual`

---

#### 8. send_decision1_visual

**节点类型**: `send_decision1`

**功能**: 发送第一阶段决策（视觉部分：图片 + 文本）

**输入参数**:

```json
{
    "pic_res": "download_pic.pic_res",
    "summary_content": "inter_summary.content",
    "audio_data": null
}
```

**配置**:

```json
{
    "step_name": "step_0",
    "status": "visual"
}
```

**发送内容**:

- 图片（错误快照）
- 文本总结

**下一跳**: `receive_step_0_visual_ack`

---

#### 9. receive_step_0_visual_ack

**节点类型**: `receive_ack`

**功能**: 接收客户端的确认消息

**下一跳**: `tts_append`

---

#### 10. tts_append

**节点类型**: `text_append`

**功能**: 拼接文本内容

**输入参数**:

```json
{
    "content_0": "inter_summary.content",
    "content_1": "pic_summary.content",
    "content_2": null
}
```

**配置**:

```json
{
    "key_0": "sumrization"  // 从 content_0 中提取 sumrization 字段
}
```

**输出**: 拼接后的文本

**下一跳**: `summary_tts`

---

#### 11. summary_tts

**节点类型**: `tts_step2step`

**功能**: 将总结文本转换为语音

**输入参数**:

```json
{
    "content": "tts_append.content"
}
```

**配置**:

```json
{
    "encode": true,
    "speaker_id": "x5_lingfeiyi_flow"
}
```

**输出**: PCM 音频数据

**下一跳**: `send_decision1_audio`

---

#### 12. send_decision1_audio

**节点类型**: `send_decision1`

**功能**: 发送第一阶段决策（音频部分）

**输入参数**:

```json
{
    "pic_res": null,
    "summary_content": null,
    "audio_data": "summary_tts.pcm_data"
}
```

**配置**:

```json
{
    "step_name": "step_0",
    "status": "audio"
}
```

**下一跳**: `receive_step_0_audio_ack`

---

#### 13. receive_step_0_audio_ack → decision_point_2

**节点类型**: `receive_ack` → `llm_step`

**功能**: 接收确认后，进行第二个决策点判断

**decision_point_2**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "intergroup_decision2.md",
    "json": true
}
```

**输出**:

```json
{
    "need_to_communicate": true/false,  // 是否需要与用户沟通
    "message": "问题内容"
}
```

**下一跳**: `judge_point_2`

---

#### 14. judge_point_2

**节点类型**: `judge_decision2`

**功能**: 判断是否需要 ASR 语音交互

**输入参数**:

```json
{
    "llm_res": "decision_point_2.content"
}
```

**分支映射**:

```json
{
    "asr": "question_tts",           // 需要沟通 → 生成问题
    "skip": "before_decision3_node"  // 跳过沟通 → 直接进入第三决策
}
```

---

#### 15a. question_tts（需要沟通路径）

**节点类型**: `tts_step2step`

**功能**: 将问题转换为语音

**输入参数**:

```json
{
    "content": "decision_point_2.content"
}
```

**配置**:

```json
{
    "encode": true,
    "speaker_id": "x5_lingfeiyi_flow",
    "key": "message"  // 从 content 中提取 message 字段
}
```

**下一跳**: `send_decision2_content`

---

#### 16a. send_decision2_content（需要沟通路径）

**节点类型**: `send_decision2`

**功能**: 发送第二阶段决策（问题文本 + 音频）

**输入参数**:

```json
{
    "llm_res": "decision_point_2.content",
    "audio_data": "question_tts.pcm_data"
}
```

**配置**:

```json
{
    "step_name": "step_1",
    "status": "visual_audio"
}
```

**下一跳**: `receive_step_1_visual_audio_ack`

---

#### 17a. step_1_asr（需要沟通路径）

**节点类型**: `asr_vad`

**功能**: 接收用户的语音回复

**配置**:

```json
{
    "step_name": "step_1",
    "if_result_audio": true,
    "result_audio_empty": "tmp_pcm/empty.txt",
    "result_audio_receive": "tmp_pcm/receive.txt"
}
```

**输出**: `asr_text` - 识别出的文本

**下一跳**: `before_decision3_node`

---

#### 15b. before_decision3_node（汇合点）

**节点类型**: `before_decision3`

**功能**: 准备第三决策的参数

**输入参数**:

```json
{
    "choice": "judge_point_2.choice",
    "llm_res": "decision_point_2.content",
    "asr_text": "step_1_asr.asr_text",
    "trace": "judge_report.params"
}
```

**输出**: 汇总后的参数

**下一跳**: `decision_point_3`

---

#### 16. decision_point_3

**节点类型**: `llm_step`

**功能**: 第三个决策点，决定是否调整训练计划

**输入参数**:

```json
{
    "params_0": "judge_report.params",
    "params_1": "before_decision3_node.params"
}
```

**配置**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "intergroup_decision3.md",
    "json": true
}
```

**输出**:

```json
{
    "should_adjust": true/false,
    "adjustment": {
        "type": "CHANGE_REP_COUNT" | "CHANGE_QUALITY_STANDARD",
        "checkpoint_id": "...",
        "old_reps": 10,
        "new_reps": 8,
        // ... 其他调整参数
    },
    "reason": "调整原因"
}
```

**下一跳**: `after_decision3_node`

---

#### 17. after_decision3_node

**节点类型**: `after_decision3`

**功能**: 处理第三决策后的调整建议

**输入参数**:

```json
{
    "llm_res": "decision_point_3.content",
    "params": "judge_report.params"
}
```

**输出参数**:

- `text_content`: 文本内容
- `last_message_id`: 消息ID
- `adjust_result`: 调整结果

**配置**:

```json
{
    "step_name": "step_2",
    "status": "visual"
}
```

**下一跳**: `adjust_reason_text`

---

#### 18. adjust_reason_text

**节点类型**: `llm_step`

**功能**: 生成调整建议的原因说明

**输入参数**:

```json
{
    "params_0": "after_decision3_node.adjust_result"
}
```

**配置**:

```json
{
    "model": "GLM-4-FlashX-250414",
    "prompt": "adjust_reason_text.md",
    "system": "你是一个专业和蔼的健身教练..."
}
```

**输出**: 人性化的调整建议文本

**下一跳**: `suggestion_tts`

---

#### 19. suggestion_tts

**节点类型**: `tts_step2step`

**功能**: 将建议文本转换为语音

**输入参数**:

```json
{
    "content": "adjust_reason_text.content"
}
```

**配置**:

```json
{
    "encode": true,
    "speaker_id": "x5_lingfeiyi_flow"
}
```

**下一跳**: `send_decision3_audio_node`

---

#### 20. send_decision3_audio_node

**节点类型**: `send_decision3_audio`

**功能**: 发送第三阶段决策（音频）

**输入参数**:

```json
{
    "audio_data": "suggestion_tts.pcm_data"
}
```

**配置**:

```json
{
    "step_name": "step_1",
    "status": "audio"
}
```

**下一跳**: `receive_step_2_audio_ack`

---

#### 21. receive_step_2_audio_ack → receive_step_2_motion_change_result → finish

**节点类型**: `receive_ack` → `receive_motion_change_result`

**功能**: 接收确认和动作变更结果，结束工作流

---

### 工作流程说明

#### 阶段1：数据分析与总结（step_0）

1. 接收组内训练数据
2. 计算统计信息
3. 下载错误快照图片
4. 判断用户等级和表现分类（A/B/C）
5. 生成总结（两点 + 口语化）
6. 生成图片总结
7. 发送视觉反馈（图片 + 文本）
8. 发送音频反馈（TTS 总结）

#### 阶段2：二次沟通决策（step_1）

1. 判断是否需要与用户沟通
2. 如果需要：
   - 生成问题
   - TTS 转换
   - 发送问题（文本 + 音频）
   - 接收用户语音回复
3. 汇合沟通结果

#### 阶段3：训练计划调整（step_2）

1. 基于沟通结果决定是否调整训练计划
2. 生成调整建议（次数/质量标准）
3. 生成人性化说明
4. TTS 转换
5. 发送音频反馈
6. 接收确认和变更结果
7. 结束
