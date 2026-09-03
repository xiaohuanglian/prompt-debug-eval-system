# 接收节点

文件位置：[nodes/check_confirm.py](../../nodes/check_confirm.py)
命名规范：receive_xx 或 receive_user_info

### ReceiveMessageNode

**注册名称**: `receive_message`

**功能**: 接收外部消息的通用节点。

**节点类型**: `BaseNode`

#### 输入参数

无

#### 输出参数

| 参数名              | 类型 | 说明           |
| ------------------- | ---- | -------------- |
| `pkg`             | step | 接收到的消息包 |
| `last_message_id` | step | 上一条消息的ID |

#### 工作流程

1. 等待事件触发
2. 调用 `get_message()` 获取消息
3. 输出消息包和消息ID

参考：
------

### Type: receive_message | Name: receive_XX

{"id": 0, "node_type": "receive_message", "node_name": "receive_00", "key_node": true, "msg_queue": true, "input_map": {}, "choice_map": {"default": "judge_00"}, "attrs": {}}

{"id": 3, "node_type": "receive_message", "node_name": "receive_01", "key_node": true, "msg_queue": true, "input_map": {}, "choice_map": {"default": "judge_01"}, "attrs": {}}

{"id": 6, "node_type": "receive_message", "node_name": "receive_02", "key_node": true, "msg_queue": true, "input_map": {}, "choice_map": {"default": "judge_02"}, "attrs": {}}

{"id": 12, "node_type": "receive_message", "node_name": "receive_03", "key_node": true, "msg_queue": true, "input_map": {}, "choice_map": {"default": "judge_03"}, "attrs": {}}

### Type: receive_message | Name: receive_user_info

{"id": 0, "node_type": "receive_message", "node_name": "receive_user_info", "input_map": {}, "choice_map": {"default": "judge_report"}, "attrs": {}}

### Type: receive_motion_change_result | Name: receive_step_X_motion_change_result

{"id": 14, "node_type": "receive_motion_change_result", "node_name": "receive_step_2_motion_change_result", "input_map": {}, "choice_map": {"default": "finish"}, "attrs": {}}
