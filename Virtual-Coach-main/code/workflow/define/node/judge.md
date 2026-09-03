# 判断节点

文件位置：[nodes/check_confirm.py](../../nodes/check_confirm.py)
命名规范：judge_xx 或 judge_report

### JudgeMotionNode

**注册名称**: `judge_motion`

**功能**: 判断运动动作质量，检测错误并提供改进建议。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名  | 类型 | 说明                     |
| ------- | ---- | ------------------------ |
| `pkg` | step | 包含动作检测数据的消息包 |

#### 输出参数

| 参数名          | 类型 | 说明                                                 |
| --------------- | ---- | ---------------------------------------------------- |
| `pkg_step`    | step | 步骤名称                                             |
| `adjust`      | step | 调整参数（可选）                                     |
| `status`      | step | 动作状态（good/improved/not_improved/other_problem） |
| `prompt_item` | step | 提示词项，用于生成反馈                               |

#### 状态判断逻辑

- `good`: 动作得分 > 0.001，动作标准
- `improved`: 趋势为改善
- `worsened`: 趋势为恶化
- `other_problem`: 存在其他错误（如角度过小）

## 参考：

### Type: judge_decisionX | Name: judge_point_X

{"id": 108, "node_type": "judge_decision2", "node_name": "judge_point_2", "input_map": {"llm_res": "decision_point_2.content"}, "choice_map": {"asr": "question_tts", "skip": "before_decision3_node"}, "attrs": {}}

### Type: judge_motion | Name: judge_XX

{"id": 1, "node_type": "judge_motion", "node_name": "judge_00", "key_node": true, "input_map": {"pkg": "receive_00.pkg"}, "choice_map": {"default": "audio_dispatch_00"}, "attrs": {}}
{"id": 4, "node_type": "judge_motion", "node_name": "judge_01", "key_node": true, "input_map": {"pkg": "receive_01.pkg"}, "choice_map": {"default": "audio_dispatch_01"}, "attrs": {}}
{"id": 7, "node_type": "judge_motion", "node_name": "judge_02", "key_node": true, "input_map": {"pkg": "receive_02.pkg"}, "choice_map": {"default": "audio_dispatch_02"}, "attrs": {}}
{"id": 13, "node_type": "judge_motion", "node_name": "judge_03", "key_node": true, "input_map": {"pkg": "receive_03.pkg"}, "choice_map": {"default": "audio_dispatch_03"}, "attrs": {}}

### Type: clac_trace | Name: judge_report

{"id": 1, "node_type": "clac_trace", "node_name": "judge_report", "input_map": {"pkg": "receive_user_info.pkg"}, "choice_map": {"default": "send_report_ack", "no_data": "send_no_data_ack"}, "attrs": {}}
