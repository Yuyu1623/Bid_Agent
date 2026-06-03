# Bid Agent

Bid Agent 是一个面向投标/招标文件的本地分析工具，包含 Python 后端能力和 Electron 桌面客户端。项目可以解析投标文档，提取章节内容，并结合大模型生成投标文件分析结果。

这个仓库会持续更新。`.env` 中的密钥和本地配置不会提交到 GitHub，请使用 `.env.example` 作为配置模板。

## 功能概览

- 支持投标文档解析，返回结构化章节内容
- 支持调用 MinerU 解析 PDF、Word 等文档
- 支持本地解析方式作为补充
- 支持通过大模型生成投标文件分析结果
- 提供 FastAPI 后端接口
- 提供 Electron 桌面端界面

## 项目结构

```text
.
├── bid_parser_api.py          # FastAPI 后端入口
├── bid_document_parser.py     # 文档解析调度
├── bid_analysis_service.py    # 招标文件分析服务
├── bid_analysis_prompts.py    # 分析提示词
├── llm_client.py              # 大模型调用封装
├── llm_model_config.py        # 模型供应商配置
├── MinerU_pdf_parse_tool.py   # MinerU 文档解析工具
├── SerpApi_search_tool.py     # SerpApi 搜索工具
├── run_plan_and_solve.py      # Plan-and-Solve 命令行入口
├── requirements.txt           # Python 依赖
└── electron_client/           # Electron 桌面客户端
```

## 环境要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- npm
- 可用的大模型 API Key
- 如使用 MinerU 解析，需要 MinerU API Token

## 安装 Python 依赖

建议使用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置环境变量

复制配置模板：

```bash
copy .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

然后编辑 `.env`，填入自己的密钥和模型信息：

```env
LLM_MODEL_ID=your-model-id
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_TIMEOUT=120
LLM_MAX_CONCURRENCY=5

MINERU_API_TOKEN=your-mineru-token
MINERU_REQUEST_TIMEOUT=60

SERPAPI_API_KEY=your-serpapi-key
```

注意：`.env` 已加入 `.gitignore`，不要把真实密钥提交到仓库。

## 运行后端 API

启动 FastAPI 服务：

```bash
uvicorn bid_parser_api:app --reload --host 127.0.0.1 --port 8000
```

启动后可以打开接口文档：

```text
http://127.0.0.1:8000/docs
```

常用接口：

- `POST /bid-documents/parse`：根据本地路径或远程 URL 解析文档
- `POST /bid-documents/upload`：上传文档并解析
- `POST /bid-documents/analyze`：解析并生成分析结果
- `POST /bid-documents/upload-analyze`：上传文档并生成分析结果

## 运行命令行 Agent

交互式运行：

```bash
python run_plan_and_solve.py
```

直接传入问题：

```bash
python run_plan_and_solve.py "请分析这个投标文件的核心评分点"
```

Windows 用户也可以双击 `run.bat`。

## 运行桌面客户端

进入 Electron 客户端目录并安装依赖：

```bash
cd electron_client
npm install
```

启动桌面端：

```bash
npm start
```

打包 Windows 便携版：

```bash
npm run dist
```

打包产物会输出到 `electron_client/dist/`，该目录不会提交到 GitHub。

## 上传和持续更新

推荐提交内容：

- Python 源码
- Electron 客户端源码
- `requirements.txt`
- `electron_client/package.json`
- `electron_client/package-lock.json`
- `.env.example`
- `.gitignore`
- `README.md`

不要提交：

- `.env`
- `.venv/`
- `electron_client/node_modules/`
- `electron_client/dist/`
- `__pycache__/`
- 临时输出文件和日志

如果本地已安装 Git，可以使用：

```bash
git add .
git commit -m "Initial Bid Agent project"
git push origin master
```

如果 GitHub 远端仓库已有旧文件，需要完全替换远端内容，可以在确认无误后清空远端分支并推送当前项目。执行前请确认旧文件不再需要保留。

## 后续计划

- 完善桌面端交互体验
- 增加更多本地文档解析能力
- 增加分析结果导出
- 增加测试用例和自动化发布流程
