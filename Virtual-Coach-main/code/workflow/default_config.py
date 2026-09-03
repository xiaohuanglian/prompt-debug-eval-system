max_iteration = 10

default_user_standardized_output = "./example/wf_setup_s03_inter.json"

default_knewledge = {
    "base": {
        "base": "./define/base/base.md",
        "test_input": "./define/base/test_input.md",
    },
    "workflow": {
        "base": "./define/workflow/base.md",
        "service_s03": "./define/workflow/service_s03.md",
        "between_set": "./define/workflow/between_set.md",
    },
    "node": {
        "base": "./define/node/base.md",
        "ack": "./define/node/ack.md",
        "asr": "./define/node/asr.md",
        "intergroup": "./define/node/intergroup.md",
        "judge": "./define/node/judge.md",
        "llm": "./define/node/llm.md",
        "receive": "./define/node/receive.md",
        "send": "./define/node/send.md",
        "tts": "./define/node/tts.md",
        "unclass": "./define/node/unclass.md",
    },
    "node_code": {
        "asr": "./nodes/asr_node.py",
        "between_set": "./nodes/between_set_node.py",
        "check_confirm": "./nodes/check_confirm_node.py",
        "llm": "./nodes/llm_node.py",
        "tts": "./nodes/tts_node.py",
    },
    "prompts": {
        "user_question": "./prompt/ws/user_question.md",
        "user_adjust": "./prompt/ws/user_adjust.md",
        "intergroup_decision1": "./prompt/ws/intergroup_decision1.md",
        "intergroup_decision2": "./prompt/ws/intergroup_decision2.md",
        "intergroup_decision3": "./prompt/ws/intergroup_decision3.md",
        "intergroup_summary": "./prompt/ws/intergroup_summary.md",
        "pic_summary": "./prompt/ws/pic_summary.md",
        "adjust_reason_text": "./prompt/ws/adjust_reason_text.md",
    },
    "action": {
        "add": "./define/action/add.md",
        "modify": "./define/action/modify.md",
    },
}