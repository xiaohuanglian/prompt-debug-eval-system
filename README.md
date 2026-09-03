# Prompt 自动化调试与评测系统

从需求描述自动生成 Prompt，合成评测数据，运行评测并迭代优化。附带桌面 GUI 与 LLM 网关部署脚本。

本仓库为公开版本：不含生产 Prompt、真实评测集、密钥和内部服务地址。本地仍可保留这些文件（已写入 `.gitignore`）。

## 结构

```
gui_app/                 桌面 GUI
Virtual-Coach-main/      评测流水线、模型接入、工作流
  data/prompt/SampleScenario/   示例场景
上线prompt/              LLM 网关 CLI 与示例部署脚本
```

## 快速开始

```bash
conda create -n vc python=3.10
conda activate vc
cd Virtual-Coach-main
pip install -e .
pip install -r ../gui_app/requirements.txt
```

复制密钥模板后填写（不要提交）：

```bash
cp code/models/api_keys_template.py code/models/api_keys.py
cp code/workflow/llm_key.example.py code/workflow/llm_key.py
```

启动 GUI：

```bash
gui_app/run.bat
```

部署脚本通过环境变量连接网关，例如：

```bash
set GATEWAY_BASE_URL=http://127.0.0.1:8080
set GATEWAY_API_KEY=your_key
```

## 配置说明

- `code/models/api_keys.py` 与 `code/workflow/llm_key.py` 已忽略
- 网关默认地址为 `http://127.0.0.1:8080`
- 示例音频/图片 URL 均为 `https://example.com/...` 占位符

基于 [Virtual Coach](https://github.com/dujh22/Virtual-Coach) 扩展。许可证见 [LICENSE](LICENSE)（MIT）。
