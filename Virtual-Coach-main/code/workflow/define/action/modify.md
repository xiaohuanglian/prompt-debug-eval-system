
# **修改已有节点的具体值**

todo：需要枚举具体哪些部分可以修改

## 1.修改预录音频URL

输入：新的URL地址
修改方法：修改对应 audio_dispatch_xx 节点的 attrs.audio_url 配置：
{
    "attrs": {
        "audio_url": {
            "good": {
                "type": "url",
                "url": "新的URL地址",
                "text": "反馈文本"
            }
        }
    }
}

## 2.修改TTS发音人

输入：新的发音人ID
修改方法：修改 tts_xx 节点的 attrs.speaker_id：
{
    "attrs": {
        "speaker_id": "新的发音人ID"
    }
}

## 3.调整LLM提示词

输入：调整后的LLM提示词
修改方法：修改节点的 attrs.system 字段

## 4.调整最大重试次数

输入：最大重试次数
修改方法：当前工作流固定为最多 4 次尝试（receive_00 ~ receive_03）。如需修改：添加更多 receive/judge/audio_dispatch 节点组，然后修改 choice_map 指向新的节点。
