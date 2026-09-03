# **添加新节点**

## 创建新节点的具体流程：

1.继承 BaseNode 类
2.使用 @register_class 装饰器注册节点
3.在 __init__ 中定义输入输出参数
4.实现 async run 方法

## 示例代码：

```python
from node import BaseNode, NodeType
from register_node import register_class

@register_class('my_custom_node')
class MyCustomNode(BaseNode):
    def __init__(self, config, workflow):
        super().__init__(config, workflow, NodeType.BaseNode)

        # 定义输入参数
        self.input_parameters = {
            'input_data': 'step'
        }

        # 定义输出参数
        self.output_parameters = {
            'output_data': 'step'
        }

        # 定义分支选项
        self.choices = ['option_a', 'option_b']

        # 获取配置
        self.custom_config = config['attrs'].get('custom_key', 'default_value')

    async def run(self, input_parameters: dict=[]):
        # 获取输入
        data = await self.get_input('input_data')

        # 等待事件
        await self.wait_for_event()

        # 处理数据
        result = self.process_data(data)

        # 设置输出
        await self.set_output('output_data', result)

        # 选择分支
        self.set_choice('option_a')

        return True

    def process_data(self, data):
        # 自定义处理逻辑
        return data
```

## 最佳实践

1.错误处理: 在 run 方法中使用 try-except 捕获异常
2.日志记录: 使用 print 或日志系统记录关键信息
3.类型注解: 为函数参数和返回值添加类型注解
4.文档注释: 为节点类和方法添加文档字符串
5.配置验证: 在 __init__ 中验证必要的配置参数
