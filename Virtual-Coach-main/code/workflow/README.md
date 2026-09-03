# **使用 prompt 生成工作流配置文件**

## **1. 需求分析**

输入：无编程经验用户输入具体的被服务需求

输出：利用LLM工程实现对服务需求的分析，然后生成适配具体需求的工作流配置文件，可用于后续软件的直接执行

实例：

1. 修改已有工作流内容，比如：“我认为刚刚的服务中语言太专业，听不懂”
2. 重组已有工作流流程，比如：“我不想每次都进行视角对齐，只在第一次进行”
3. 新增工作流，比如：“我想要一个连续计数100次的俯卧撑锻炼服务”、“我是一个***情况的业余健身爱好人士，帮我形成一个具有***特点的服务流程”

## 2. 基本设计与实现

### 2.1 总体原则

模版化+最小修改原则：主要利用大模型进行模版的调用与组合，尽可能减少对模版的修改

### 2.2 模版化

### 2.2.1 已有工作流信息

基本定义参见[./define/workflow/base.md](./define/workflow/base.md)

#### 2.2.1.1 组内动作调整指导工作流

详细定义参见[./define/workflow/service_s03.md](./define/workflow/service_s03.md)

#### 2.2.1.2 组间休息分析和决策工作流

详细定义参见[./define/workflow/between_set.md](./define/workflow/between_set.md)

### 2.2.2 已有节点信息

基本定义参见[./define/node/base.md](./define/node/base.md)

#### 2.2.2.1 接收节点

详细定义参见[./define/node/receive.md](./define/node/receive.md)

#### 2.2.2.2 判断节点

详细定义参见[./define/node/judge.md](./define/node/judge.md)

#### 2.2.2.3 LLM节点

详细定义参见[./define/node/llm.md](./define/node/llm.md)

#### 2.2.2.4 TTS节点

详细定义参见[./define/node/tts.md](./define/node/tts.md)

#### 2.2.2.5 发送节点

详细定义参见[./define/node/send.md](./define/node/send.md)

#### 2.2.2.6 确认节点

详细定义参见[./define/node/ack.md](./define/node/ack.md)

#### 2.2.2.7 ASR节点

详细定义参见[./define/node/asr.md](./define/node/asr.md)

#### 2.2.2.8 组间节点

详细定义参见[./define/node/intergroup.md](./define/node/intergroup.md)

#### 2.2.2.9 未归类节点

详细定义参见[./define/node/unclass.md](./define/node/unclass.md)

### 2.3 最小修改对应的决策

#### 2.3.1 修改已有节点的具体值

详细定义参见[./define/action/modify.md](./define/action/modify.md)

#### 2.3.2 添加新节点

详细定义参见[./define/action/add.md](./define/action/add.md)

## 3.使用方式

命令行启动后端：

```shell
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

在浏览器访问后端提供的同源页面（不要直接以 file:// 打开 HTML）：

```shell
http://127.0.0.1:8000/
```

该服务仅供本机开发使用，拒绝远程客户端与其他来源网页。`example_path` 只能指向 `example/` 下的 JSON。没有多用户认证，不适合通过反向代理或端口转发公开部署。

## 4. 维护防护

1. 公开版包含研究用节点定义；节点执行依赖未包含的上游运行引擎。需自行提供兼容实现，不能直接运行这些节点。
2. 修改代码中对LLM的调用方式，当前采用的是llm_api.py文件，可以使用类似实现的llm相关调用函数进行相关功能替代

## 5. 相关文档

* [仓库安全与运行边界](../../../../SECURITY.md)
