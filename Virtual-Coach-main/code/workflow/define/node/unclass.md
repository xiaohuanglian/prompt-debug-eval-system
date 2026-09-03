# 其他节点

## 参考：

### Type: after_decisionX | Name: after_decisionX_node

{"id": 113, "node_type": "after_decision3", "node_name": "after_decision3_node", "input_map": {"llm_res": "decision_point_3.content", "params": "judge_report.params"}, "choice_map": {"default": "adjust_reason_text"}, "attrs": {"step_name": "step_2", "status": "visual"}}

### Type: before_decisionX | Name: before_decisionX_node

{"id": 111, "node_type": "before_decision3", "node_name": "before_decision3_node", "key_node": true, "input_map": {"choice": "judge_point_2.choice", "llm_res": "decision_point_2.content", "asr_text": "step_1_asr.asr_text", "trace": "judge_report.params"}, "choice_map": {"default": "decision_point_3"}, "attrs": {}}

### Type: get_pic | Name: download_pic

{"id": 101, "node_type": "get_pic", "node_name": "download_pic", "input_map": {"pkg": "judge_report.parsed_pkg", "token": "judge_report.token"}, "choice_map": {"default": "decision_point_1"}, "attrs": {}}
