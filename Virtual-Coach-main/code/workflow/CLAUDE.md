# CLAUDE.md

此文件为 Claude Code (claude.ai/code) 在处理此代码库时提供指导。

## 项目概述

Workflow 是一个基于异步编程的模块化节点工作流系统，用于构建复杂的服务流程。该系统支持流批一体化的 Agentic Workflow 编排，通过标准化的节点设计实现快速的功能组装。

### 设计目标

- **实现流批一体化的Agentic Workflow编排**
  - 快速的大模型接入（通过 `llm_api.py` 集成智谱AI等LLM服务）
  - 流处理功能与批处理功能的混合快速编排
  - 支持 step（批处理）和 stream（流处理）两种数据流类型
- **使用极简的设计思路**
  - 减少封装的复杂性，专注于核心功能
  - 减少代码量，提高维护性
  - 通过JSON配置文件定义工作流，无需编程即可构建复杂流程

### 关键技术决策

- **节点化设计**：单一功能设计成标准的功能节点
  - 标准化的输入、输出、运行函数等
  - 使用 `@register_class` 装饰器自动注册节点
  - 所有节点继承自 `BaseNode` 基类
- **异步支持**：节点支持异步调用（asyncio）与预测执行
  - 提前执行工作流后面的节点，提高工作流效率
  - 使用 `async/await` 语法进行异步操作
- **参数传递系统**：支持参数传递的异步检查，用于预测执行
  - 通过 `input_map` 定义参数来源映射
  - 通过 `choice_map` 定义分支选择映射
- **JSON配置驱动**：工作流通过JSON文件定义，实现配置与代码分离

## 项目结构

### 主要目录结构

```
workflow/
├── nodes/              # 工作流节点实现模块
│   ├── __init__.py
│   ├── asr_node.py     # ASR（语音识别）节点
│   ├── tts_node.py     # TTS（文本转语音）节点，支持多种流类型转换
│   ├── llm_node.py     # LLM（大语言模型）节点，支持step和stream模式
│   ├── check_confirm.py # 接收、判断、发送等基础节点
│   └── between_set.py   # 组间决策相关节点
├── define/             # 工作流和节点的定义文档
│   ├── workflow/       # 工作流定义文档
│   │   ├── base.md     # 工作流基础格式定义
│   │   ├── service_s03.md  # 组内动作调整指导工作流
│   │   └── between_set.md  # 组间休息分析和决策工作流
│   ├── node/           # 节点定义文档
│   │   ├── base.md     # 节点基础格式定义
│   │   ├── receive.md  # 接收节点定义
│   │   ├── judge.md    # 判断节点定义
│   │   ├── llm.md      # LLM节点定义
│   │   ├── tts.md      # TTS节点定义
│   │   ├── asr.md      # ASR节点定义
│   │   └── ...         # 其他节点类型定义
│   └── action/         # 动作定义文档
│       ├── add.md      # 添加节点操作
│       └── modify.md    # 修改节点操作
├── prompt/             # 提示词模板
│   ├── http/           # HTTP接口使用的提示词模板
│   └── ws/             # WebSocket接口使用的提示词模板
│       ├── user_question.md      # 用户问题反馈提示词
│       ├── user_adjust.md        # 用户调整指导提示词
│       ├── intergroup_decision1.md  # 组间决策1提示词
│       ├── intergroup_decision2.md  # 组间决策2提示词
│       ├── intergroup_decision3.md  # 组间决策3提示词
│       ├── intergroup_summary.md    # 组间总结提示词
│       ├── pic_summary.md           # 图片总结提示词
│       └── adjust_reason_text.md    # 调整原因说明提示词
├── analysis/           # 分析工具
│   ├── analysis_node_name.py
│   ├── analysis_node_type.py
│   └── example/        # 示例工作流配置文件
├── llm_api.py          # LLM API接口封装（智谱AI）
├── llm_key.py          # LLM API密钥配置
├── main.py             # 入口文件
├── README.md           # 项目说明文档
└── CLAUDE.md           # 本文件
```

### 模块职责

- **nodes/**: 定义工作流中的各类处理节点实现
  - `asr_node.py`: ASR语音识别节点，支持VAD（语音活动检测）
  - `tts_node.py`: TTS文本转语音节点，支持多种流类型转换（step2step, step2stream, stream2step, stream2stream）
  - `llm_node.py`: LLM大语言模型节点，支持step和stream两种模式
  - `check_confirm.py`: 基础节点（接收消息、判断动作、发送数据等）
  - `between_set.py`: 组间决策相关节点（决策、确认、资源发送等）
- **define/**: 存放工作流和节点的定义文档，用于LLM生成工作流配置
  - `workflow/`: 工作流模板定义
  - `node/`: 节点类型定义
  - `action/`: 操作定义（添加、修改节点）
- **prompt/**: 存放各类提示词模板，按接口类型分类
  - `http/`: HTTP接口使用的提示词
  - `ws/`: WebSocket接口使用的提示词
- **analysis/**: 工作流分析工具和示例配置

## 架构概览

### 核心组件

**工作流引擎系统：**

- **节点基类** (`BaseNode`): 所有节点的基类，定义标准化的输入输出接口

  - 节点通过 `@register_class` 装饰器注册
  - 支持 `NodeType.BaseNode`、`NodeType.StepNode`、`NodeType.StreamNode` 等类型
  - 通过 `input_parameters` 和 `output_parameters` 定义数据流
  - 通过 `choices` 定义分支选项，通过 `choice_map` 映射到下一节点
- **工作流管理器** (`WorkflowManager`): 管理工作流的执行

  - 从JSON配置文件加载工作流定义
  - 管理节点的生命周期和执行顺序
  - 处理节点间的参数传递和分支选择
  - 支持异步执行和预测执行
- **节点实现** (`nodes/`): 各类功能节点的具体实现

  - `asr_node.py`: ASR语音识别节点（`asr_vad`）
  - `tts_node.py`: TTS节点，支持多种流类型转换
    - `tts_step2step`: 批处理文本转批处理音频
    - `tts_step2stream`: 批处理文本转流式音频
    - `tts_stream2step`: 流式文本转批处理音频
    - `tts_stream2stream`: 流式文本转流式音频
    - `tts_step2file`: 批处理文本转音频文件
    - `tts_stream2file`: 流式文本转音频文件
  - `llm_node.py`: LLM节点
    - `llm_step`: 批处理LLM调用
    - `llm_stream`: 流式LLM调用
  - `check_confirm.py`: 基础业务节点
    - `receive_message`: 接收消息节点
    - `judge_motion`: 判断动作节点
    - `send_audio_dispatch`: 发送音频分发节点
    - `send_audio_data`: 发送音频数据节点
  - `between_set.py`: 组间决策相关节点
    - `send_ack` / `receive_ack`: 确认节点
    - `send_step_resource`: 发送步骤资源节点
    - `clac_trace`: 计算轨迹节点
    - `get_pic`: 获取图片节点
    - `send_decision1/2/3`: 决策发送节点
    - `judge_decision2`: 决策判断节点
    - 等等

**LLM集成：**

- `llm_api.py` - LLM API接口封装
  - 使用智谱AI（ZhipuAI）SDK
  - 支持流式和非流式调用
  - 支持深度思考模式（thinking mode）
  - 提供 `llm_chat`、`llm_chat_stream`、`llm_chat_with_prompt` 等接口

**提示词系统：**

- `prompt/` - 提示词模板目录
  - `ws/`: WebSocket接口使用的提示词模板
    - `user_question.md`: 用户问题反馈
    - `user_adjust.md`: 用户调整指导
    - `intergroup_decision1/2/3.md`: 组间决策提示词
    - `intergroup_summary.md`: 组间总结
    - `pic_summary.md`: 图片总结
    - `adjust_reason_text.md`: 调整原因说明

### 关键架构模式

**基于节点的工作流引擎：**

- 工作流由相互连接的节点组成，异步处理数据
- 节点通过 `input_map` 和 `output_parameters` 进行参数传递
- 支持不同的数据流类型：
  - `step`: 批处理数据，一次性输入输出
  - `stream`: 流式数据，连续输入输出
- 使用 asyncio 进行事件驱动执行
- 通过 `wait_for_event()` 实现节点间的同步
- 通过 `get_input()` 和 `set_output()` 进行数据传递

**工作流配置格式：**

- JSON格式定义工作流结构
- 每个工作流包含：
  - `workflow_name`: 工作流名称
  - `start_node`: 起始节点名称
  - `listen_at_start`: 是否在起始时监听消息
  - `input_parameters`: 工作流级别输入参数定义
  - `nodes`: 节点配置数组
- 每个节点包含：
  - `id`: 节点编号ID
  - `node_type`: 节点类型（对应注册的别名）
  - `node_name`: 节点实例名称
  - `key_node`: 是否为关键节点（可选）
  - `msg_queue`: 是否使用消息队列（可选）
  - `input_map`: 输入参数映射
  - `choice_map`: 分支选择映射
  - `attrs`: 节点特定的配置属性

**节点注册机制：**

- 使用 `@register_class('node_alias')` 装饰器注册节点
- 节点类必须继承 `BaseNode`
- 在 `__init__` 中定义 `input_parameters`、`output_parameters`、`choices`
- 实现 `async run()` 方法作为节点执行逻辑

### 重要文件关系

- **工作流定义** (`define/workflow/*.md`): 定义工作流模板和规范
- **节点定义** (`define/node/*.md`): 定义节点类型和规范
- **节点实现** (`nodes/*.py`): 节点的具体实现代码
- **提示词模板** (`prompt/ws/*.md`): LLM节点使用的提示词模板
- **LLM接口** (`llm_api.py`): 封装LLM API调用
- **工作流配置** (`analysis/example/*.json`): 示例工作流JSON配置文件

## 编码规范

### 代码风格

- **命名规范**:

  - 类名: 使用CamelCase (如 `BaseNode`, `WorkFlow`)
  - 函数和变量: 使用snake_case (如 `setup_logging`, `request_id`)
  - 常量: 使用全大写加下划线 (如 `LOG_FORMAT`, `TIMEOUT`)
- **代码格式**:

  - 使用4个空格进行缩进，不使用Tab
  - 每行代码不超过100个字符
  - 文件编码为UTF-8
- **类型注解**:

  - 函数参数和返回值必须添加类型注解
  - 使用 `from typing import`导入必要的类型

### 文档注释

- 每个Python文件开头添加文件功能说明
- 每个函数和类必须包含文档字符串
- 关键代码添加行内注释解释其逻辑

示例：

```python
"""配置应用程序日志系统"""
def setup_logging(config):
    # 日志格式：包含时间、级别、模块、请求ID、消息
    log_format = logging.Formatter(
        config.get("LOG_FORMAT", "%(asctime)s - %(levelname)s - %(module)s - %(request_id)s - %(message)s")
    )
```

### 导入规范

- 标准库导入放在最前面
- 第三方库导入放在中间
- 项目内部模块导入放在最后
- 使用相对导入时注意路径层级

## 日志规范

### 日志使用

- **节点日志**: 使用 `self.parent_workflow.log('level', 'message')` 记录日志
- **调试日志**: 使用 `print()` 语句输出调试信息（开发阶段）
- **异常日志**: 在 try-except 块中记录异常信息，包含详细上下文

示例：

```python
# 节点中使用日志
self.parent_workflow.log('debug', f"after waiting receive_message {self.name}")

# 异常处理
try:
    # 节点逻辑
    pass
except Exception as e:
    print(f"节点执行错误: {str(e)}")
    # 或使用日志
    self.parent_workflow.log('error', f"节点 {self.name} 执行失败: {str(e)}")
```

## 工作流系统规范

### 节点定义

- **所有节点必须继承自 `BaseNode` 类**
- **使用 `@register_class('node_alias')` 装饰器注册节点**
- 根据功能设置节点类型（`NodeType.BaseNode`、`NodeType.StepNode`、`NodeType.StreamNode`）
- 在 `__init__` 中明确定义：
  - `input_parameters`: 输入参数定义（格式：`{'param_name': 'step'|'stream'}`）
  - `output_parameters`: 输出参数定义（格式：`{'param_name': 'step'|'stream'}`）
  - `choices`: 分支选项列表（如 `['default', 'good', 'improved']`）
- 实现 `async run(self, input_parameters: dict=[])` 方法

### 节点执行流程

1. **获取输入**: 使用 `await self.get_input('param_name')` 获取输入参数
2. **等待事件**: 使用 `await self.wait_for_event()` 等待前置节点完成
3. **处理逻辑**: 执行节点的核心业务逻辑
4. **设置输出**: 使用 `await self.set_output('param_name', value)` 设置输出参数
5. **选择分支**: 使用 `self.set_choice('branch_name')` 选择下一跳分支
6. **返回结果**: 返回 `True` 表示执行成功

### 工作流配置

- **工作流配置文件使用JSON格式**
- 配置文件定义节点关系和参数映射
- 工作流支持上下文管理和参数传递
- 通过 `input_map` 定义参数来源：`"input_param": "source_node.output_param"`
- 通过 `choice_map` 定义分支映射：`"branch_name": "next_node_name"`

### 数据流类型

- **step（批处理）**: 一次性输入输出，数据完整后处理
- **stream（流处理）**: 连续输入输出，支持流式处理
- 节点可以定义不同流类型的输入输出参数
- TTS节点支持多种流类型转换（step2step, step2stream, stream2step, stream2stream）

### 异步编程

- **工作流中的节点方法必须使用异步实现**
- 使用 `async/await` 语法进行异步操作
- 使用 `asyncio.Queue` 处理流式数据
- 避免阻塞操作，如需要使用线程池执行

## 配置管理

### LLM配置

- **LLM API密钥**: 在 `llm_key.py` 中配置 `api_key`
- **LLM模型**: 在 `llm_api.py` 中配置默认模型（如 `glm-4.7`）
- **LLM调用**: 通过 `llm_api.py` 中的函数进行调用
  - `llm_chat(prompt)`: 非流式调用
  - `llm_chat_stream(prompt)`: 流式调用
  - `llm_chat_with_prompt(system_prompt, user_prompt)`: 带系统提示词的调用

### 节点配置

- **节点配置在JSON工作流文件的 `attrs` 字段中定义**
- 不同节点类型有不同的配置项：
  - LLM节点: `model`, `prompt`, `system`, `json`, `static_params`
  - TTS节点: `speaker_id`, `encode`, `key`
  - ASR节点: `step_name`, `if_result_audio`, `result_audio_empty`, `result_audio_receive`
  - 发送节点: `step_name`, `status`, `audio_url`, `static_resouce`

### 提示词配置

- **提示词模板存放在 `prompt/ws/` 目录**
- 在节点配置中通过 `prompt` 字段引用（如 `"prompt": "user_question.md"`）
- 提示词支持参数替换，通过 `params` 传递参数

## 依赖管理

### 包管理工具

- 使用pip进行依赖管理
- Python版本要求：>=3.9

### 主要依赖

- **zai-sdk**: 智谱AI SDK，用于LLM调用
- **asyncio**: Python异步编程库（标准库）
- **json**: JSON处理（标准库）
- **base64**: Base64编码（标准库）
- **wave**: WAV文件处理（标准库）
- **httpx**: HTTP客户端（用于外部API调用）
- **re**: 正则表达式（标准库）

### 安装依赖

```bash
pip install zai-sdk httpx
```

## 节点类型说明

### LLM节点

**llm_step**: 批处理LLM调用

- 输入: `params_0`, `params_1`, `params_2` (step类型)
- 输出: `content` (step类型)
- 配置: `model`, `prompt`, `system`, `json`, `static_params`
- 用途: 一次性LLM调用，返回完整结果

**llm_stream**: 流式LLM调用

- 输入: `prompt_item` (step类型)
- 输出: `content` (stream类型)
- 配置: `model`, `prompt`, `system`
- 用途: 流式LLM调用，实时返回生成内容

### TTS节点

**tts_step2step**: 批处理文本转批处理音频

- 输入: `content` (step类型)
- 输出: `pcm_data` (step类型)
- 配置: `speaker_id`, `encode`, `key`

**tts_step2stream**: 批处理文本转流式音频

- 输入: `content` (step类型)
- 输出: `pcm_stream` (stream类型)
- 配置: `speaker_id`, `encode`

**tts_stream2step**: 流式文本转批处理音频

- 输入: `content` (stream类型)
- 输出: `pcm_data` (step类型)
- 配置: `speaker_id`, `encode`

**tts_stream2stream**: 流式文本转流式音频

- 输入: `content` (stream类型)
- 输出: `pcm_stream` (stream类型)
- 配置: `speaker_id`, `encode`

**tts_step2file**: 批处理文本转音频文件

- 输入: `data` (step类型)
- 输出: 无
- 配置: `encode`, `file` (包含 `path`, `channels`, `sample_rate`, `sample_width`)

**tts_stream2file**: 流式文本转音频文件

- 输入: `content` (stream类型)
- 输出: 无
- 配置: `encode`, `file`

### ASR节点

**asr_vad**: 带VAD的语音识别节点

- 输入: 无（从消息队列接收）
- 输出: `asr_text` (step类型)
- 配置: `step_name`, `if_result_audio`, `result_audio_empty`, `result_audio_receive`
- 功能: 接收音频流，进行语音识别，在句子结束时触发回调

### 基础业务节点

**receive_message**: 接收消息节点

- 输入: 无（从消息队列接收）
- 输出: `pkg`, `last_message_id` (step类型)
- 功能: 接收外部消息，等待 `wait_for_event()` 后获取消息

**judge_motion**: 判断动作节点

- 输入: `pkg` (step类型)
- 输出: `pkg_step`, `adjust`, `status`, `prompt_item` (step类型)
- 功能: 分析动作数据，判断动作质量（good/improved/not_improved/other_problem）

**send_audio_dispatch**: 发送音频分发节点

- 输入: `pkg_step`, `adjust`, `status` (step类型)
- 输出: `response` (step类型)
- 分支: `good`, `improved`, `not_improved`, `other_problem`
- 配置: `audio_url` (定义不同状态对应的音频URL或TTS类型)

**send_audio_data**: 发送音频数据节点

- 输入: `response`, `data` (step类型)
- 输出: 无
- 功能: 将TTS生成的音频数据填充到响应中并发送

## 安全规范

- **API密钥管理**: 敏感信息（如LLM API密钥）存放在 `llm_key.py` 中，不应提交到版本控制
- **参数验证**: 节点实现中应对输入参数进行验证
- **异常处理**: 异常处理要全面，使用 try-except 捕获异常
- **日志记录**: 日志记录中避免包含敏感数据（如API密钥、用户隐私信息）

## 开发与测试规范

### 开发流程

- 使用小步迭代方式开发
- 代码修改后及时进行测试
- 新功能开发前先查看 `define/` 目录下的定义文档
- 遵循节点命名规范和分支命名规范

### 节点开发规范

1. **创建新节点**:

   - 继承 `BaseNode` 类
   - 使用 `@register_class('node_alias')` 装饰器注册
   - 在 `__init__` 中定义输入输出参数和分支选项
   - 实现 `async run()` 方法
2. **节点命名规范**:

   - 接收节点: `receive_xx` 或 `receive_user_info`
   - 判断节点: `judge_xx` 或 `judge_report`
   - LLM节点: `llm_step` 或 `llm_stream`
   - TTS节点: `tts_xx`
   - 发送节点: `send_xx` 或 `send_data_xx`
   - 确认节点: `receive_xx_ack` 或 `receive_ack`
3. **分支命名规范**:

   - `default`: 默认分支
   - `good`: 动作标准
   - `improved`: 有改善
   - `not_improved`: 未改善
   - `other_problem`: 其他问题
   - `asr`: 需要ASR
   - `skip`: 跳过
   - `no_data`: 无数据

## 开发注意事项

- **异步编程**: 系统使用 asyncio 进行异步操作，所有节点方法必须是异步的
- **参数传递**: 使用 `await self.get_input()` 获取输入，使用 `await self.set_output()` 设置输出
- **事件同步**: 使用 `await self.wait_for_event()` 等待前置节点完成
- **分支选择**: 使用 `self.set_choice()` 选择分支，必须在 `choice_map` 中定义对应关系
- **流式处理**: 流式节点需要循环处理输入，直到收到结束信号（`status == 2`）
- **错误处理**: 在 `run()` 方法中使用 try-except 捕获异常，记录错误信息
- **日志记录**: 使用 `self.parent_workflow.log()` 或 `print()` 记录关键信息
- **上下文访问**: 使用 `self.parent_workflow.get_context('key')` 访问工作流上下文（如handler、asr_tencent、tts_xunfei等）

## 工作流设计原则

### 核心理念

- **KISS原则**：保持简单，专注核心功能
- **单一职责**：每个节点都有明确的单一职责
- **YAGNI原则**：只实现真正需要的功能，避免过度设计
- **配置驱动**：通过JSON配置定义工作流，实现配置与代码分离

### 设计特点

- **节点化设计**: 单一功能封装成标准节点
- **流批一体化**: 支持step和stream两种数据流类型
- **异步执行**: 使用asyncio实现高效的异步处理
- **参数映射**: 通过input_map和choice_map实现灵活的节点连接
- **模板化**: 通过define目录下的模板定义，支持LLM生成工作流配置

## 使用场景

### 典型工作流

1. **组内动作调整指导工作流** (`service_s03`):

   - 实时接收用户动作数据
   - 判断动作质量
   - 提供个性化反馈和指导
   - 支持多轮交互和调整
2. **组间休息分析和决策工作流** (`between_set`):

   - 分析组内训练数据
   - 生成总结报告
   - 决策是否需要调整训练计划
   - 与用户进行二次沟通
   - 生成调整建议

### 工作流生成

- 使用LLM根据用户需求生成工作流配置
- 参考 `define/` 目录下的模板定义
- 遵循节点命名和分支命名规范
- 通过 `analysis/` 目录下的工具分析工作流结构

## 快速参考

### 核心概念

- **工作流 (Workflow)**: 由节点组成的执行流程，通过JSON配置文件定义
- **节点 (Node)**: 工作流的基本执行单元，实现单一功能
- **数据流类型**:
  - `step`: 批处理，一次性完整数据
  - `stream`: 流处理，连续数据流
- **参数映射**:
  - `input_map`: 定义输入参数来源 `"input_param": "source_node.output_param"`
  - `choice_map`: 定义分支下一跳 `"branch_name": "next_node_name"`

### 关键API

- `await self.get_input('param_name')`: 获取输入参数
- `await self.set_output('param_name', value)`: 设置输出参数
- `await self.wait_for_event()`: 等待前置节点完成
- `await self.get_message()`: 从消息队列获取消息（用于receive节点）
- `self.set_choice('branch_name')`: 选择分支
- `self.parent_workflow.get_context('key')`: 访问工作流上下文
- `self.parent_workflow.log('level', 'message')`: 记录日志

### 节点开发模板

```python
from node import BaseNode, NodeType
from register_node import register_class

@register_class('my_node')
class MyNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode)
      
        self.input_parameters = {
            'input_data': 'step'
        }
        self.output_parameters = {
            'output_data': 'step'
        }
        self.choices = ['default']
      
        # 从config中获取配置
        self.my_config = config['attrs'].get('my_key', 'default_value')
  
    async def run(self, input_parameters: dict=[]):
        try:
            # 1. 获取输入
            data = await self.get_input('input_data')
          
            # 2. 等待事件
            await self.wait_for_event()
          
            # 3. 处理逻辑
            result = self.process(data)
          
            # 4. 设置输出
            await self.set_output('output_data', result)
          
            # 5. 选择分支
            self.set_choice('default')
          
            return True
        except Exception as e:
            print(f"节点执行错误: {str(e)}")
            return False
  
    def process(self, data):
        # 自定义处理逻辑
        return data
```

### 工作流配置示例

```json
{
  "my_workflow": {
    "start_node": "receive_00",
    "listen_at_start": true,
    "input_parameters": {},
    "nodes": [
      {
        "id": 0,
        "node_type": "receive_message",
        "node_name": "receive_00",
        "key_node": true,
        "msg_queue": true,
        "input_map": {},
        "choice_map": {
          "default": "judge_00"
        },
        "attrs": {}
      },
      {
        "id": 1,
        "node_type": "judge_motion",
        "node_name": "judge_00",
        "input_map": {
          "pkg": "receive_00.pkg"
        },
        "choice_map": {
          "default": "audio_dispatch_00"
        },
        "attrs": {}
      }
    ]
  }
}
```
