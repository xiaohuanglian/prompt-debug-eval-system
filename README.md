# Prompt 自动化调试与评测系统

从需求描述自动生成 Prompt，合成评测数据，运行评测并迭代优化。附带桌面 GUI 与 LLM 网关部署脚本。

本仓库包含通用演示与历史研究代码。新增业务场景、运行日志和凭据默认留在本地；公开范围与限制见 [SECURITY.md](SECURITY.md)。自动扫描不能证明所有内容均无敏感信息，也不能清除 Git 历史。

## 结构

```
gui_app/                 桌面 GUI
Virtual-Coach-main/      评测流水线、模型接入、工作流
  data/prompt/SampleScenario/   示例场景
上线prompt/              LLM 网关 CLI 与示例部署脚本
```

## 快速开始

以下命令从仓库根目录执行，要求 Python 3.10+：

```bash
conda create -n vc python=3.10
conda activate vc
python -m pip install -e ./Virtual-Coach-main
python -m pip install -r ./gui_app/requirements.txt
```

复制密钥模板后填写（不要提交）：

```powershell
Copy-Item Virtual-Coach-main/code/models/api_keys_template.py Virtual-Coach-main/code/models/api_keys.py
Copy-Item Virtual-Coach-main/code/workflow/llm_key.example.py Virtual-Coach-main/code/workflow/llm_key.py
```

在 `api_keys.py` 中填写所选供应商的 URL、API_KEY、MODEL。这是本地受信任 Python 配置，不要从陌生来源复制可执行配置。GUI/流水线会在运行时注入配置；生成模型源码不会写入密钥、服务地址或具体模型名。独立运行新生成的适配器时也可设置对应的 `<PREFIX>_API_KEY`、`<PREFIX>_URL`、`<PREFIX>_MODEL` 环境变量。

从仓库根目录启动 GUI（Windows）：

```powershell
.\gui_app\run.bat
```

也可使用 `python gui_app/main.py`，或进入 `Virtual-Coach-main` 后运行 `python main.py` 使用命令行流水线。

跨语言演示可先离线预览：

```bash
python cross_lingual_test/cross_lingual_test.py --dry-run
```

网关 CLI 使用 `GATEWAY_BASE_URL` 和 `GATEWAY_API_KEY`（兼容 `STREAMBRIDGE_*`）。请通过本地环境或 GUI 输入网关专用密钥；GUI 不保存密钥，也不再复用模型供应商密钥。CLI 保留 `--api-key` 兼容选项，但环境变量可避免在命令参数中暴露凭据。网关默认地址为 `http://127.0.0.1:8080`。

## 配置说明

- `code/models/api_keys.py` 与 `code/workflow/llm_key.py` 已忽略
- 网关默认地址为 `http://127.0.0.1:8080`
- 示例音频/图片 URL 均为 `https://example.com/...` 占位符
- Kimi 独立适配器使用 `KIMI_API_KEY` 或本地配置的 `KIMI_*`，不会默认读取 `OPENAI_API_KEY`
- GPT 独立适配器默认使用 OpenAI 官方端点；第三方服务需明确设置 `GPT_BASE_URL` 并提供该服务对应的密钥
- 工作流 HTTP 服务仅限本机同源访问，启动方法见 [工作流说明](Virtual-Coach-main/code/workflow/README.md)
- 部分历史评测脚本依赖未发布资源，不属于可直接运行的示例；公开演示从 `SampleScenario` 或跨语言 `--dry-run` 开始

## 发布前检查

```bash
python scripts/check_public_release.py
python scripts/check_public_release.py --staged
python scripts/check_public_release.py --history
```

默认检查本地待发布内容，`--staged` 检查完整暂存区，`--history` 另外审计可达历史。历史审计会报告旧提交中仍存在的个人元数据；它不执行历史重写。不要使用 `git add -f` 将被忽略的真实业务文件加入公开仓库。

基于 [Virtual Coach](https://github.com/dujh22/Virtual-Coach) 扩展。仓库附带 [MIT 文本](LICENSE)，上游授权证据与适用范围仍需维护者确认，见 [来源说明](THIRD_PARTY_NOTICES.md)。
