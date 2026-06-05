# Dowell 投标工具箱

Dowell 投标工具箱是一个面向招标文件解析、核对和标书生成的本地桌面工具。项目由 Python FastAPI 后端和 Electron 桌面前端组成，支持解析 PDF、Word、图片、HTML 等招标文件，并调用大模型提取投标人须知、商务内容、技术要求、资格审查和评分要求。

本仓库会持续更新。`.env` 中的 API Key、Token、本地路径等个人配置不要提交到 GitHub，请使用 `.env.example` 作为配置模板。

## 当前技术路径

```text
招标文件
  -> Electron 桌面端上传
  -> FastAPI 后端接收
  -> 解析策略选择
      -> MinerU API / MinerU 本地 Pipeline
      -> pdfplumber 本地 PDF 解析
      -> docx2python / python-docx Word 解析
      -> DOCX 图片 OCR 补充
  -> Markdown / 章节结构化
  -> 大模型并发分析
      -> 投标人须知
      -> 技术要求
      -> 资格审查
      -> 评分要求
  -> Electron 前端五大模块展示
```

## 功能概览

- 支持上传 PDF、Word、图片、HTML 等招标文件
- 支持自动解析策略推荐，也支持手动选择解析方式
- 支持 MinerU VLM、MinerU Pipeline、MinerU-HTML
- 支持本地 MinerU Pipeline
- 支持 `pdfplumber` 本地 PDF 解析
- 支持 `docx2python`、`python-docx` Word 解析
- 支持 DOCX 图片 OCR，使用 RapidOCR / Tesseract 作为本地补充
- 支持大模型流式输出和非流式输出
- 支持四个大模型分析任务并发执行
- 支持修改解析后的内容并重新分析
- 前端按五大模块展示：投标人须知、商务内容、技术要求、资格审查、评分要求
- 资格审查支持资格性审查、符合性审查、废标项切换查看
- 评分要求支持商务评分、技术评分切换查看

## 项目结构

```text
.
├── bid_parser_api.py          # FastAPI 后端接口，包括上传、解析、分析和流式接口
├── bid_analysis_service.py    # 招标文件分析服务，负责解析后并发调用大模型
├── bid_analysis_prompts.py    # 大模型分析 Prompt
├── bid_document_parser.py     # 招标文件解析入口和章节拆分
├── bid_parse_strategy.py      # 解析方式推荐和解析质量报告
├── bid_image_analysis.py      # 文档图片分析和 OCR 辅助能力
├── MinerU_pdf_parse_tool.py   # MinerU API 文档解析工具
├── llm_client.py              # OpenAI-compatible 大模型客户端，支持同步、异步、流式
├── llm_model_config.py        # 前端模型名称与真实模型 ID 映射
├── SerpApi_search_tool.py     # SerpApi 搜索工具
├── plan_and_solve_agent.py    # Plan-and-Solve Agent 逻辑
├── run_plan_and_solve.py      # 命令行入口
├── requirements.txt           # Python 依赖
├── MINERU_LOCAL_DEPLOY.md     # MinerU 本地部署说明
└── electron_client/           # Electron 桌面客户端
    ├── main.js
    ├── preload.js
    ├── renderer.html
    ├── renderer.js
    ├── styles.css
    ├── package.json
    └── package-lock.json
```

## 环境要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- npm
- 可用的大模型 API Key
- 如使用 MinerU API，需要 MinerU API Token
- 如使用本地 MinerU Pipeline，需要本机可运行 MinerU CLI
- 如使用 Tesseract OCR，需要本机安装 Tesseract

## 安装 Python 依赖

建议使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Python 依赖包括：

- `fastapi`、`uvicorn`：后端 API 服务
- `openai`：OpenAI-compatible 大模型调用
- `python-dotenv`：读取本地环境变量
- `pdfplumber`：本地 PDF 文本解析
- `docx2python`、`python-docx`：Word 文档解析
- `pillow`、`opencv-python`、`rapidocr-onnxruntime`、`pytesseract`：图片和 OCR 辅助解析
- `requests`、`pydantic`、`python-multipart`：接口、校验和上传支持

## 安装 Electron 客户端依赖

```powershell
cd electron_client
npm install
```

Electron 客户端主要依赖：

- `electron`
- `electron-builder`

## 配置环境变量

复制模板：

```powershell
copy .env.example .env
```

编辑 `.env`，填入自己的密钥和模型信息：

```env
LLM_MODEL_DISPLAY_NAME=
LLM_MODEL_ID=your-model-id
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_TIMEOUT=120
LLM_MAX_CONCURRENCY=5

MINERU_API_TOKEN=your-mineru-token
MINERU_REQUEST_TIMEOUT=60

SERPAPI_API_KEY=your-serpapi-key
```

注意：`.env` 已加入 `.gitignore`，不要提交真实密钥。

## 启动后端

在项目根目录启动 FastAPI：

```powershell
python -m uvicorn bid_parser_api:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/health
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 启动前端

```powershell
cd electron_client
npm start
```

前端默认连接：

```text
http://127.0.0.1:8000
```

如果后端端口发生变化，请在前端“后端地址”中同步修改。

## 常用接口

- `GET /health`
  后端健康检查。

- `POST /bid-documents/parse`
  根据本地路径或远程 URL 解析招标文件。

- `POST /bid-documents/upload`
  上传文件并解析，返回章节和解析质量信息。

- `POST /bid-documents/analyze`
  根据本地路径或远程 URL 解析并调用大模型分析。

- `POST /bid-documents/upload-analyze`
  上传文件，解析后调用大模型分析，返回完整 JSON。

- `POST /bid-documents/upload-analyze-stream`
  上传文件，解析后以 Server-Sent Events 流式返回分析过程和结果。

- `POST /bid-documents/analyze-content`
  使用人工修改后的解析内容重新分析。

- `POST /bid-documents/analyze-content-stream`
  使用人工修改后的解析内容流式重新分析。

## 解析方式

当前支持的解析方式包括：

```text
auto                  自动推荐解析方式
mineru_vlm            MinerU VLM
mineru_pipeline       MinerU Pipeline
mineru_html           MinerU-HTML
mineru_local_pipeline 本地 MinerU Pipeline
pdfplumber            本地 PDF 文本解析
docx2python           本地 Word 文本解析
docx2python_image_ocr Word 文本解析 + 图片 OCR
```

`auto` 会根据文件类型、文本量、DOCX 图片数量等因素推荐解析方式。

## 大模型分析策略

后端会将解析后的文档内容组装为 Markdown，然后并发执行四个大模型分析任务：

- 投标人须知 / 项目概览
- 技术要求
- 资格审查
- 评分要求

前端可以选择：

- 流式输出
- 非流式输出

流式接口会边分析边返回事件；非流式接口会等待全部分析完成后一次性返回结果。

## MinerU 本地部署

项目支持本地 MinerU Pipeline。详细安装和配置见：

```text
MINERU_LOCAL_DEPLOY.md
```

如果后端找不到 `mineru` 命令，可以在 `.env` 中配置本地命令路径：

```env
MINERU_LOCAL_COMMAND=C:\path\to\mineru.exe
```

本地路径属于个人配置，不要提交到 GitHub。

## 打包桌面端

项目稳定后可以打包 Windows 便携版：

```powershell
cd electron_client
npm run dist
```

打包产物输出到：

```text
electron_client/dist/
```

`electron_client/dist/` 已加入 `.gitignore`，不要提交打包产物。

## 不要提交的内容

以下内容不应上传到 GitHub：

```text
.env
.venv/
.mineru-venv/
electron_client/node_modules/
electron_client/dist/
__pycache__/
*.pyc
logs/
outputs/
uploads/
temp/
tmp/
```

## 更新到 GitHub

提交前先检查敏感文件是否被跟踪：

```bash
git status --short
git ls-files .env
git ls-files .venv .mineru-venv electron_client/node_modules electron_client/dist __pycache__
```

如果 `git ls-files .env` 有输出，先从 Git 索引移除，但保留本地文件：

```bash
git rm --cached .env
```

如果虚拟环境、依赖目录、构建产物或缓存目录被跟踪，执行：

```bash
git rm -r --cached .venv
git rm -r --cached .mineru-venv
git rm -r --cached electron_client/node_modules
git rm -r --cached electron_client/dist
git rm -r --cached __pycache__
```

如果某条命令提示路径不存在或没有被跟踪，可以忽略。

确认没有敏感文件后提交：

```bash
git add .
git status --short
git commit -m "Update project documentation and technical path"
git push origin master
```

如果之前已经把 `.env` 或密钥推送到 GitHub，建议立即更换相关 API Key 和 Token。

## 后续计划

- 完善标书生成模块
- 增加 Word / PDF 导出能力
- 增加模板套版能力
- 增加废标项检查和响应完整性检查
- 增加自动化测试和发布流程
