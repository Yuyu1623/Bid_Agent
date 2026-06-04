# Dowell 投标工具箱

这是一个面向招标文件解析、核对和标书生成的本地工具。项目包含 Python FastAPI 后端和 Electron 桌面前端，可以解析 PDF、Word 等招标文件，调用大模型提取项目概述、技术要求、资格/符合性审查、评分要求，并支持人工修改解析后的原文后重新分析。

`.env` 中的密钥和本地配置不要提交到仓库，请使用 `.env.example` 作为配置模板。

## 功能概览

- 支持上传 PDF、Word、图片、HTML 等招标文件
- 支持 MinerU VLM、MinerU Pipeline、MinerU-HTML 模型解析
- 支持 `pdfplumber`、`docx2python` 本地解析方式
- 支持解析后的 Markdown 原文展示、编辑、复制、展开和导出
- 支持用人工修改后的解析内容重新调用大模型分析
- 支持大模型流式输出和非流式输出
- 大模型分析默认并行处理，失败后自动降级为串行处理
- 支持三步前端流程：上传招标文件、招标文件分析核对、标书生成
- 提供 FastAPI 后端接口和 Electron 桌面客户端

## 当前流程

1. 上传招标文件
   前端上传文件到后端，后端调用 MinerU 或本地解析器解析文件，并调用大模型提取结构化信息。

2. 招标文件分析核对
   前端显示大模型分析结果，同时在“解析原文”页签展示解析后的 Markdown。用户可以直接修改解析原文，并点击“用修改内容重新分析”。

3. 标书生成
   点击“核对完成”后进入标书生成步骤。目前这一步先做了上方工作台样式，占位模块包括技术方案生成、商务响应生成、废标项检查和终稿组装。

## 项目结构

```text
.
├── bid_parser_api.py          # FastAPI 后端接口
├── bid_document_parser.py     # 招标文件解析和章节拆分
├── bid_analysis_service.py    # 招标文件分析服务
├── bid_analysis_prompts.py    # 大模型分析提示词
├── llm_client.py              # 大模型调用封装，支持同步、异步和流式
├── llm_model_config.py        # 前端模型名称和真实模型 ID 映射
├── MinerU_pdf_parse_tool.py   # MinerU 文件解析工具
├── SerpApi_search_tool.py     # SerpApi 搜索工具
├── plan_and_solve_agent.py    # Plan-and-Solve 智能体逻辑
├── run_plan_and_solve.py      # 命令行入口
├── requirements.txt           # Python 依赖
└── electron_client/           # Electron 桌面客户端
```

## 环境要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- npm
- 可用的大模型 API Key
- 如使用 MinerU 解析，需要 MinerU API Token

## 安装依赖

建议使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

安装 Electron 客户端依赖：

```powershell
cd electron_client
npm install
```

## 配置环境变量

复制配置模板：

```powershell
copy .env.example .env
```

编辑 `.env`，填写自己的密钥和模型信息：

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

当前前端模型下拉框展示的是易读名称，后端会通过 `llm_model_config.py` 映射为供应商官方模型 ID。当前供应商只配置了硅基流动。

## 启动后端

必须在项目根目录启动后端：

```powershell
cd C:\Users\Dowell\Desktop\plan_and_solve_agent
python -m uvicorn bid_parser_api:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/health
```

正常返回：

```json
{"status":"ok"}
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

如果提示端口占用，说明 8000 已经有后端在运行，可以直接使用，或换端口启动。前端填写的后端地址必须和 FastAPI 启动端口一致。

## 常用接口

- `GET /health`
  后端健康检查。

- `POST /bid-documents/parse`
  根据本地路径或远程 URL 解析文件。

- `POST /bid-documents/upload`
  上传文件并解析，返回章节列表。

- `POST /bid-documents/upload-analyze`
  上传文件，解析后调用大模型，非流式一次性返回结果。

- `POST /bid-documents/upload-analyze-stream`
  上传文件，解析后调用大模型，前端可流式接收结果。

- `POST /bid-documents/analyze-content`
  使用人工修改后的解析内容重新分析，非流式返回。

- `POST /bid-documents/analyze-content-stream`
  使用人工修改后的解析内容重新分析，流式返回。

## 大模型并行策略

当前分析模块包括：

- 项目概述
- 技术要求
- 资格和符合性审查
- 评分要求

无论前端选择流式还是非流式，后端都会优先并行请求这四个大模型任务。如果并行失败，会自动降级为串行请求，尽量保证任务可以继续完成。

流式输出时，前端会边接收边更新对应模块内容；非流式输出时，前端会等待全部完成后一次性展示结果。

## 启动前端

项目开发阶段建议先用源码启动 Electron，不急着打包 exe：

```powershell
cd C:\Users\Dowell\Desktop\plan_and_solve_agent\electron_client
npm start
```

前端默认后端地址是：

```text
http://127.0.0.1:8000
```

如果后端换了端口，比如 `8010`，前端也要改为：

```text
http://127.0.0.1:8010
```

## 打包 exe

项目结束或阶段稳定后再打包：

```powershell
cd electron_client
npm run dist
```

打包产物会输出到：

```text
electron_client/dist/
```

注意：修改源码后，旧 exe 不会自动更新，必须重新打包才会包含最新界面和逻辑。

## 排查处理失败

如果前端提示无法连接后端，先检查：

```text
http://127.0.0.1:8000/health
```

如果不通，启动后端：

```powershell
cd C:\Users\Dowell\Desktop\plan_and_solve_agent
python -m uvicorn bid_parser_api:app --host 127.0.0.1 --port 8000
```

如果 `/health` 正常但解析失败：

- 检查 `.env` 中的 `MINERU_API_TOKEN`
- 检查网络和代理是否能访问 MinerU
- 检查文件格式是否支持
- 使用较小页面范围测试大文件，例如 `1-5`

如果大模型失败：

- 检查 `LLM_API_KEY`
- 检查 `LLM_BASE_URL`
- 检查 `LLM_MODEL_ID` 或前端模型映射
- 检查网络和代理

## 不建议提交的内容

- `.env`
- `.venv/`
- `electron_client/node_modules/`
- `electron_client/dist/`
- `__pycache__/`
- 临时输出文件和日志

## 后续计划

- 接入正式的 Step 3 标书生成逻辑
- 增加 Word / PDF 导出能力
- 增加模板套版能力
- 增加废标项检查和响应完整性检查
- 增加更多本地解析方式
- 增加自动化测试和发布流程
