# LLM节点

文件位置：[nodes/llm_node.py](../../nodes/llm_node.py)
命名规范：llm_step 或 llm_stream

### LLMStepNode

**注册名称**: `llm_step`

**功能**: 调用大语言模型进行一次性推理，支持 JSON 格式输出。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名       | 类型 | 说明              |
| ------------ | ---- | ----------------- |
| `params_0` | step | 参数0（字典类型） |
| `params_1` | step | 参数1（字典类型） |
| `params_2` | step | 参数2（字典类型） |

#### 输出参数

| 参数名      | 类型 | 说明                                   |
| ----------- | ---- | -------------------------------------- |
| `content` | step | LLM 返回的内容（可能是文本或JSON对象） |

#### 配置属性

| 属性名            | 类型 | 说明                       |
| ----------------- | ---- | -------------------------- |
| `prompt`        | str  | 提示词模板名称             |
| `system`        | str  | 系统提示词                 |
| `model`         | str  | 模型名称                   |
| `json`          | bool | 是否提取 JSON 格式输出     |
| `static_params` | dict | 静态参数，会与输入参数合并 |

#### 工作流程

1. 获取三个输入参数并合并
2. 合并静态参数
3. 构建提示词
4. 调用 LLM 接口
5. 如果需要 JSON，使用正则提取 JSON 对象
6. 输出结果

### LLMStreamNode

**注册名称**: `llm_stream`

**功能**: 流式调用大语言模型，逐块返回生成内容。

**节点类型**: `BaseNode`

#### 输入参数

| 参数名          | 类型 | 说明                   |
| --------------- | ---- | ---------------------- |
| `prompt_item` | step | 提示词参数（字典类型） |

#### 输出参数

| 参数名      | 类型   | 说明                               |
| ----------- | ------ | ---------------------------------- |
| `content` | stream | 流式内容（包含 status, text, seq） |

#### 配置属性

| 属性名     | 类型 | 说明           |
| ---------- | ---- | -------------- |
| `prompt` | str  | 提示词模板名称 |
| `system` | str  | 系统提示词     |
| `model`  | str  | 模型名称       |

#### 输出格式

```python
{
    'status': 0/1/2,  # 0: 开始, 1: 进行中, 2: 结束
    'text': '文本内容',
    'seq': 序列号
}
```

#### 工作流程

1. 获取提示词参数
2. 从工作流记忆中获取上一次文本
3. 设置流式回调函数 `content_recall`
4. 调用 LLM 流式接口
5. 逐块输出内容

## 参考：

### Type: llm_step | Name: adjust_reason_text

{"id": 304, "node_type": "llm_step", "node_name": "adjust_reason_text", "input_map": {"params_0": "after_decision3_node.adjust_result", "params_1": null, "params_2": null}, "choice_map": {"default": "suggestion_tts"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "adjust_reason_text.md", "system": "你是一个专业和蔼的健身教练，根据用户的训练反馈和当前动作要求，生成个性化的鼓励或调整建议。\n要求\n1. 当adjust为\"否\"时，对用户的努力和进步给予积极肯定，解释调整的原因不要有打压性，鼓励继续保持当前的训练状态，字数在40个字以内\n2. 当adjust为\"是\"时，如果idea说明对动作标准进行调整时，告诉学员[我对xx要求稍微下调了]，必须根据目前的rep进行告知现在要求，字数可以适当调整到60字内。如调整数量则告诉学员数量调整，保证明确告知具体的调整措施和解释调整的原因和目的，字数为40个字以内\n3. 使用第二人称\"你\"，亲切自然，体现私人教练的专业性和关怀\n4. 语言温暖且具有激励性，保持积极正面的语调，避免过于严厉或消极的表达", "json": false, "static_params": {}}}

### Type: llm_step | Name: decision_point_X

{"id": 102, "node_type": "llm_step", "node_name": "decision_point_1", "input_map": {"params_0": "judge_report.params", "params_1": null, "params_2": null}, "choice_map": {"default": "inter_summary"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "intergroup_decision1.md", "system": "", "json": true, "static_params": {}}}
{"id": 107, "node_type": "llm_step", "node_name": "decision_point_2", "input_map": {"params_0": "judge_report.params", "params_1": null, "params_2": null}, "choice_map": {"default": "judge_point_2"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "intergroup_decision2.md", "system": "", "json": true, "static_params": {}}}
{"id": 112, "node_type": "llm_step", "node_name": "decision_point_3", "input_map": {"params_0": "judge_report.params", "params_1": "before_decision3_node.params", "params_2": null}, "choice_map": {"default": "after_decision3_node"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "intergroup_decision3.md", "system": "", "json": true, "static_params": {}}}

### Type: llm_step | Name: inter_summary

{"id": 103, "node_type": "llm_step", "node_name": "inter_summary", "input_map": {"params_0": "decision_point_1.content", "params_1": "judge_report.params", "params_2": null}, "choice_map": {"default": "pic_summary"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "intergroup_summary.md", "system": "你是一名健身教练，请根据学员训练表现情况生成反馈总结。\n要求：\n1.固定输出两点（点1+点2），每点 ≤40字，同时输出口语化总结（将点1和点2的要求合并为一段 ≤80字，用积极鼓励情感表达）\n2.必须根据不同分类（A/B/C）遵循规则\n3.在A的情况下，要求精准定位问题和解决方案，如点1要中性陈述动作问题事实，避免打击性词汇,必须要阐明还有多少次动作有带提高(用总动作数减去高质量动作数)和点2要指出最关键问题，并给出改正方法，\n4.在B的情况下，要求表扬和优化提升，如点1先表扬高质量完成次数，再指出有多少次动作完成的不足不足和点2要鼓励用户在不足点上做得更好\n5.在C的情况下，要求要正反馈和强化记忆，如点1要用充满能量的词汇和数据肯定努力和点2要帮助用户记住并复制成功经验\n6.首先必须要清楚的讲清楚本次完成的动作数量，高质量或有待提高的动作又几个\n7.总共字数不超过80字\n8.要求使用第二人称表达语气要人性化，有鼓励感，可以适当用语气助词\n输出严格遵守json格式，格式如下\n{ \n    \"point_1\": //点1,\n    \"point_2\": //点2,\n    \"sumrization\": //口语化总结\n}", "json": true, "static_params": {}}}

### llm_step | Name: pic_summary

{"id": 301, "node_type": "llm_step", "node_name": "pic_summary", "input_map": {"params_0": "judge_report.params", "params_1": "download_pic.pic_res", "params_2": null}, "choice_map": {"default": "send_decision1_visual"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "pic_summary.md", "system": "你是一名健身教练，请根据学员训练表现情况生成反馈总结。\n\n要求：\n1.基于快照的错误给出总结用户出现的不足之处\n2.基于错误告知用户如何改进\n3.要求语气要人性化，有鼓励感，可以适当用语气助词\n4.总共字数不超过40字", "json": false, "static_params": {}}}

### Type: llm_stream | Name: llm_stream_XX

{"id": 9, "node_type": "llm_stream", "node_name": "llm_stream_02", "input_map": {"prompt_item": "judge_02.prompt_item"}, "choice_map": {"default": "tts_02"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "user_question.md", "system": "你是一个健身教练，正在给学员动作指导\n\n你需要根据学员的动作信息，输出反馈，帮助学员纠正动作\n\n输出要求：\n1.自然口语化，像教练指导学员一样，可以用一些程度模糊词如“一点点”，“稍微”，语气助词，增加口语化\n2.语气平和，务必避免语气过于强烈的感叹词以及反问句、疑问句\n3.参考上一次的提示，结合本次变化情况，如果有改善，回复中要包含上次指导的信息，可以用例如“还要”，“还需要”，“需要再”等连续性词语，如果没有改善，要考虑更换更通俗的指导话语\n4.如果上次指导针对的是其他错误，本次指导不需要参考上次指导\n5.输出一句简短自然的人类教练式反馈，像实时反馈一般，回复控制在15字以内\n"}}
{"id": 15, "node_type": "llm_stream", "node_name": "llm_stream_03", "input_map": {"prompt_item": "judge_03.prompt_item"}, "choice_map": {"default": "tts_03"}, "attrs": {"model": "GLM-4-FlashX-250414", "prompt": "user_adjust.md", "system": "你是一个健身教练，正在给学员动作指导\n\n当前学员的表现暂时达不到原本的标准\n\n请输出一句控制在40字以内的指导语句\n"}}
