# 组间节点

文件位置：[nodes/between_set.py](../../nodes/between_set.py)

### SendACKNode / ReceiveACKNode

**注册名称**: `send_ack` / `receive_ack`

**功能**: 发送/接收确认消息，用于消息同步。

#### 配置属性

| 属性名        | 类型 | 说明     |
| ------------- | ---- | -------- |
| `step_name` | str  | 步骤名称 |

### SendStepResourceNode

**注册名称**: `send_step_resource`

**功能**: 发送步骤资源（音频、文本、图片等）。

#### 输入参数

| 参数名         | 类型 | 说明  |
| -------------- | ---- | ----- |
| `resource_0` | step | 资源0 |
| `resource_1` | step | 资源1 |
| `resource_2` | step | 资源2 |

#### 输出参数

| 参数名              | 类型 | 说明   |
| ------------------- | ---- | ------ |
| `last_message_id` | step | 消息ID |

#### 配置属性

```python
{
    'attrs': {
        'step_name': str,      # 步骤名称
        'status': str,         # 状态
        'static_resouce': [    # 静态资源
            {'type': 'audio', 'data': '...'},
            {'type': 'text', 'data': '...'}
        ]
    }
}
```

### ClacTrace

**注册名称**: `clac_trace`

**功能**: 计算和分析运动轨迹数据，提取质量检查点和统计数据。

#### 输入参数

| 参数名  | 类型 | 说明                 |
| ------- | ---- | -------------------- |
| `pkg` | step | 包含运动数据的消息包 |

#### 输出参数

| 参数名         | 类型 | 说明           |
| -------------- | ---- | -------------- |
| `params`     | step | 计算后的参数   |
| `parsed_pkg` | step | 解析后的消息包 |
| `token`      | step | 认证令牌       |

#### 输出参数格式

```python
{
    "high_quality_reps": 8,        # 高质量次数
    "error_reps": 2,                # 错误次数
    "most_frequent_error_type": "", # 最常见错误类型
    "set_reps": 10,                 # 组次数
    "levels": 1,                    # 难度等级
    "exercise_name": "深蹲",        # 动作名称
    "exercise_id": "4",             # 动作ID
    "quality_checkpoints": {        # 质量检查点
        "checkpoint_name": {
            'is_enabled': True,
            'standard': 'low',
            'title': '检查点标题',
            'req': '要求描述'
        }
    }
}
```

#### 分支选择

- `default`: 有运动数据
- `no_data`: 无运动数据

### GetInterPic

**注册名称**: `get_pic`

**功能**: 获取运动间歇图片和相关总结文本。

#### 输入参数

| 参数名    | 类型 | 说明     |
| --------- | ---- | -------- |
| `pkg`   | step | 消息包   |
| `token` | step | 认证令牌 |

#### 输出参数

| 参数名      | 类型 | 说明         |
| ----------- | ---- | ------------ |
| `pic_res` | step | 图片资源结果 |

#### 输出格式

```python
{
    "viewSummaryText": "",     # 视图总结文本
    "ttsSummaryText": "",      # TTS总结文本
    "errorSnapshot": "",       # 错误快照图片URL
    "errorMessage": ""         # 错误消息
}
```

### SendDecision1

**注册名称**: `send_decision1`

**功能**: 发送第一阶段决策信息（包含图片、总结文本和音频）。

#### 输入参数

| 参数名              | 类型 | 说明     |
| ------------------- | ---- | -------- |
| `pic_res`         | step | 图片资源 |
| `summary_content` | step | 总结内容 |
| `audio_data`      | step | 音频数据 |

#### 输出参数

| 参数名              | 类型 | 说明   |
| ------------------- | ---- | ------ |
| `last_message_id` | step | 消息ID |

### JudgeDecision2

**注册名称**: `judge_decision2`

**功能**: 判断是否需要与用户进行二次沟通。

#### 输入参数

| 参数名      | 类型 | 说明        |
| ----------- | ---- | ----------- |
| `llm_res` | step | LLM返回结果 |

#### 输出参数

| 参数名     | 类型 | 说明                 |
| ---------- | ---- | -------------------- |
| `choice` | step | 选择结果（asr/skip） |

#### 分支选择

- `asr`: 需要用户沟通
- `skip`: 跳过沟通

### TextAppend

**注册名称**: `text_append`

**功能**: 将多个文本内容拼接在一起。

#### 输入参数

| 参数名        | 类型 | 说明  |
| ------------- | ---- | ----- |
| `content_0` | step | 内容0 |
| `content_1` | step | 内容1 |
| `content_2` | step | 内容2 |

#### 输出参数

| 参数名      | 类型 | 说明         |
| ----------- | ---- | ------------ |
| `content` | step | 拼接后的文本 |

#### 配置属性

```python
{
    'attrs': {
        'key_0': '',  # 从content_0中提取的键名（可选）
        'key_1': '',  # 从content_1中提取的键名（可选）
        'key_2': ''   # 从content_2中提取的键名（可选）
    }
}
```

### AfterDecision3

**注册名称**: `after_decision3`

**功能**: 处理第三阶段决策后的调整建议。

#### 输入参数

| 参数名      | 类型 | 说明        |
| ----------- | ---- | ----------- |
| `llm_res` | step | LLM返回结果 |
| `params`  | step | 参数        |

#### 输出参数

| 参数名              | 类型 | 说明     |
| ------------------- | ---- | -------- |
| `text_content`    | step | 文本内容 |
| `last_message_id` | step | 消息ID   |
| `adjust_result`   | step | 调整结果 |

#### 调整类型

1. **CHANGE_REP_COUNT**: 修改次数

   ```python
   {
       "type": "rep",
       "original_rep": 10,
       "new_rep": 8,
       "rep_title": "调整训练次数",
       "detect_title": "...",
       "req": ""
   }
   ```
2. **CHANGE_QUALITY_STANDARD**: 修改质量标准

   ```python
   {
       "type": "detect",
       "old_level": 2,
       "new_level": 1,
       "direction": "down",  # 或 "up"
       "rep_title": "调整训练次数",
       "detect_title": "...",
       "req": "..."
   }
   ```
