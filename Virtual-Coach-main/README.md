# Virtual Coach (虚拟教练)

基于大语言模型的 Prompt 开发与评测工具，包含 Virtual Coach 衍生研究示例。

公开版安装入口见[仓库首页](../README.md)，发布边界见[安全说明](../SECURITY.md)，上游授权状态见[来源说明](../THIRD_PARTY_NOTICES.md)。

## 📖 项目简介

Virtual Coach 是一个基于大语言模型（LLM）的智能虚拟教练系统，旨在为用户提供个性化的交互式课程生成和指导服务。该系统结合了先进的AI技术和教育理论，为用户提供智能化的学习体验。

系统核心功能包括：

- **Prompt 自动化调试与评测**: 从需求描述自动生成 Prompt，自动合成评测数据，运行评测并提供优化建议，支持版本化迭代
- **工作流生成系统**: 通过自然语言描述自动生成可执行的工作流配置
- **多模型支持**: 支持多种大语言模型（GLM-4-Air、科大讯飞X1等），自动发现和加载
- **评估系统**: 提供决策场景 Prompt 和工作流的评估和性能分析功能

## 🏗️ 项目结构

```
Virtual-Coach/
├── main.py                         # Prompt 自动化调试与评测入口
├── code/                           # 源代码目录
│   ├── models/                    # 模型接口模块
│   ├── eval/                      # 评估模块
│   │   └── eval_prompt_*.py      # 评估场景脚本
│   ├── pipeline/                  # Prompt 自动化调试与评测流水线
│   │   ├── cli_utils.py          # CLI 交互工具
│   │   ├── model_resolver.py     # 模型发现与动态加载
│   │   ├── prompt_generator.py   # LLM 驱动的 Prompt 生成
│   │   ├── eval_data_generator.py# 评测数据自动生成
│   │   ├── eval_code_generator.py# 评测脚本模板化生成
│   │   ├── eval_runner.py        # 并行评测执行引擎
│   │   ├── optimizer.py          # 错误分析与优化建议
│   │   ├── version_manager.py    # Prompt 版本管理
│   │   └── json_utils.py         # JSON 提取工具
│   ├── workflow/                  # 工作流模块
│   │   ├── nodes/                 # 工作流节点实现
│   │   ├── define/                # 工作流定义文档
│   │   ├── prompt/                # 工作流提示词
│   │   └── analysis/              # 工作流分析工具
│   ├── utils/                     # 工具函数
│   └── agent/                     # Agent 模块
├── data/                           # 数据文件目录
│   ├── eval/                      # 评估数据
│   ├── eval_result/               # 评估结果
│   ├── prompt/                    # 提示词数据（支持版本化子目录）
│   └── trace/                     # 追踪数据
├── paper/                          # 论文相关文件
├── pyproject.toml                 # 项目构建配置
└── README.md                      # 项目说明文档
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 相关依赖包（详见pyproject.toml）

### 安装步骤

#### **1. 克隆项目**

```bash
git clone https://github.com/xiaohuanglian/prompt-debug-eval-system.git
cd prompt-debug-eval-system/Virtual-Coach-main
```

#### **2. 安装依赖**

```bash
# 推荐使用conda创建虚拟环境
conda create -n vc python=3.10
conda activate vc

# 安装项目包
pip install -e .
```

#### **3. 配置API密钥**

参照 `code/models/api_keys_template.py` 创建 `code/models/api_keys.py` 文件，只需要提供对应模型的key即可，其他可以留空：

```python
OPENAI_URL="API调用请求的网址"
OPENAI_API_KEY="API_KEY"
OPENAI_MODEL="具体请求的模型"
```

#### 4. 构造LLM调用基本文件

```bash
cd ./code/utils 
python auto_generate_llm_call.py
```

## 📖 使用说明

### Prompt 自动化调试与评测

系统提供了一套完整的 Prompt 工程自动化流水线，支持从需求到评测的全流程自动化：

```bash
python main.py
```

**完整流程：**

1. **模型选择** — 分别选择 Helper 模型（生成 prompt/数据/建议）和 Target 模型（被评测）
2. **需求输入** — 输入场景名称和任务需求描述
3. **自动生成 Prompt** — Helper 模型根据需求生成 prompt 模板，用户可确认/编辑/重新生成
4. **生成评测数据** — 支持两种模式：
   - 全自动生成：LLM 根据 prompt 理解自动生成测试样本
   - 种子扩充：用户提供几个示例，LLM 扩展生成更多样本
5. **生成评测脚本** — 自动生成可独立运行的评测脚本
6. **运行评测** — 8 线程并行评测，显示准确率和耗时统计
7. **优化建议** — 分析错误样本，Helper 模型给出改进建议
8. **迭代优化** — 修改 prompt → 保存新版本 → 重新评测，循环至满意

**版本管理：**

每次修改 prompt 自动保存为新版本，支持断点续接：

```
data/prompt/{ScenarioName}/
    v1.py       # 初始版本
    v2.py       # 改进版
    v3.py       # ...
```

### 工作流生成系统

工作流系统支持通过自然语言描述自动生成可执行的工作流配置。详细使用说明请参考 `code/workflow/README.md`。

主要功能：

- **工作流模板化**: 基于模板快速生成工作流
- **节点管理**: 支持多种节点类型（接收、判断、LLM、TTS、发送、确认、ASR等）
- **工作流修改**: 支持修改已有工作流和添加新节点
- **决策分析**: 提供组间休息分析和决策功能

### 评估系统

系统提供了多个决策场景的评估功能，位于 `code/eval/` 目录下：

- `eval_prompt_DecisionScenario1.py` - 决策场景1评估
- `eval_prompt_DecisionScenario2.py` - 决策场景2评估
- `eval_prompt_DecisionScenario3.py` - 决策场景3评估
- `eval_prompt_DecisionScenario4.py` - 决策场景4评估

评估数据位于 `data/eval/` 目录，评估结果保存在 `data/eval_result/` 目录。

## 历史示例限制

`code/eval/eval_prompt_DecisionScenario*.py` 和训练总结脚本保留为历史研究参考，依赖的部分 Prompt 或数据集未随公开版发布，不能直接作为开箱即用示例运行。请通过 `main.py` 或 GUI 使用 `SampleScenario` 文档生成自己的评测脚本。工作流节点实现还依赖上游执行引擎，当前仓库主要提供配置生成和研究参考。
