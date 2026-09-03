# 节点

节点是工作流的基本执行单元，数据结构为一个单一功能抽象的标准json，具体的键包括：

```json
{
    "id": 0,                          *// 节点编号ID（唯一标识）*
    "node_type": "node_type_name",    *// 节点类型（对应注册的别名）*
    "node_name": "node_instance_name", *// 节点实例名称（工作流内唯一，用于节点间的引用）*
    "key_node": true,                 *// 是否为关键节点（可选）*
    "msg_queue": true,                *// 是否使用消息队列（可选）*
    "input_map": {                    *// 输入参数映射（定义参数来源）*
        "input_param": "source_node.output_param"    // 从其他节点输出获取参数。具体定义，input_param是节点定义的输入参数名，source_node是数据来源的节点名称，output_param是来源节点的输出参数名，"source_node.output_param"可以为空，即""。
    },
    "choice_map": {                   *// 分支选择映射（定义节点执行后的不同分支的下一跳节点）*
        "branch_name": "next_node_name" // branch_name是分支名称，next_node_name是该分支对应的下一个节点名称
    },
    "attrs": {                        *// 节点特定的配置属性*
        *// 节点配置参数*
    }
}
```

## 一些基本的命名规范：

### 1.节点命名规范：

接收节点: receive_xx 或 receive_user_info
判断节点: judge_xx 或 judge_report
LLM 节点: llm_step 或 llm_stream
TTS 节点: tts_xx
发送节点: send_xx 或 send_data_xx
确认节点: receive_xx_ack 或 receive_ack

### 2.音频类型说明

url：预录音频，用于URL固定反馈语句
tts：实时TTS生成，用于个性化反馈
stream：流式音频，用于实时流式播放

### 3.分支命名规范：

default：默认分支，用于常规流程
good：动作标准，用于达标情况
improved：有改善，用于进步情况
not_improved：未改善，用于需继续努力
other_problem：其他问题，用于特殊错误
asr：需要ASR，用于需要语音交互
skip：跳过，用于不需要交互
no_data：无数据，用于异常情况

### 4.已有LLM提示词模版

[user_question.md](../../prompt/ws/user_question.md): 用户动作问题反馈
[user_adjust.md](../../prompt/ws/user_adjust.md): 用户调整指导
[intergroup_decision1.md](../../prompt/ws/intergroup_decision1.md): 组间决策1（等级判断）
[intergroup_decision2.md](../../prompt/ws/intergroup_decision2.md): 组间决策2（沟通判断）
[intergroup_decision3.md](../../prompt/ws/intergroup_decision3.md): 组间决策3（调整判断）
[intergroup_summary.md](../../prompt/ws/intergroup_summary.md): 组间总结
[pic_summary.md](../../prompt/ws/pic_summary.md): 图片总结
[adjust_reason_text.md](../../prompt/ws/adjust_reason_text.md): 调整原因说明
