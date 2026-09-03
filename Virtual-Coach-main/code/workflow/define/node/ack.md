# 检查确认节点

文件位置：[nodes/check_confirm.py](../../nodes/check_confirm.py)
命名规范：receive_xx_ack 或 receive_ack

## 参考：

### Type: receive_ack | Name: receive_step_X_audio_ack

{"id": 5, "node_type": "receive_ack", "node_name": "receive_step_0_audio_ack", "input_map": {"last_message_id": "send_decision1_audio.last_message_id"}, "choice_map": {"default": "decision_point_2"}, "attrs": {"step_name": "step_0", "status": "audio"}}
{"id": 13, "node_type": "receive_ack", "node_name": "receive_step_2_audio_ack", "input_map": {"last_message_id": "send_decision3_audio_node.last_message_id"}, "choice_map": {"default": "receive_step_2_motion_change_result"}, "attrs": {}}

### Type: receive_ack | Name: receive_step_X_visual_ack

{"id": 3, "node_type": "receive_ack", "node_name": "receive_step_0_visual_ack", "input_map": {"last_message_id": "send_decision1_visual.last_message_id"}, "choice_map": {"default": "tts_append"}, "attrs": {"step_name": "step_0", "status": "visual"}}

### Type: receive_ack | Name: receive_step_X_visual_audio_ack

{"id": 7, "node_type": "receive_ack", "node_name": "receive_step_1_visual_audio_ack", "input_map": {"last_message_id": "send_decision2_content.last_message_id"}, "choice_map": {"default": "step_1_asr"}, "attrs": {}}
