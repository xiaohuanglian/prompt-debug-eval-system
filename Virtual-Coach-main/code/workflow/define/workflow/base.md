# 工作流

工作流是一个基于异步编程的模块化节点json配置文件，用于构建复杂的服务流程。该系统支持流批一体化的Agentic Workflow 编排，通过标准化的节点设计实现快速的功能组装。

## 主要的特点是：

1.节点化设计：单一功能设计成标准的功能节点
2.异步支持：节点支持异步调用（asyncio）与预测执行

## 基本的格式：

```json
{
    "workflow_name": {                        // 工作流名称
        "start_node": "entry_node_name",      // 起始节点名称
        "listen_at_start": true,              // 是否在起始时监听消息
        "input_parameters": {},               // 工作流级别输入参数定义
        "nodes": [                    
            // 节点配置数组（存储所有节点实例）
        ]
    }
}
```
