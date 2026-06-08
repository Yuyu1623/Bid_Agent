# MinerU 本地化部署说明

本项目已经支持通过 `MinerU 本地 Pipeline` 解析方式调用本机 `mineru` 命令。你只需要先在本机或服务器安装 MinerU，然后在前端解析方式中选择 `MinerU 本地 Pipeline`。

## 当前机器建议

你的 CPU 是 `13th Gen Intel(R) Core(TM) i5-13500H`，这不是 NVIDIA CUDA GPU。它一般只有 Intel 核显，不能给 vLLM / CUDA 推理带来明显加速。

因此本机优先建议使用：

```text
MinerU 本地 Pipeline
```

这条路线可以离线/本地解析，但速度不一定比 MinerU 云端 VLM 快。它的优势是不用公网 API 排队、文件不出本机。

## 方案一：Windows 本机安装 MinerU

建议使用 Python 3.10 ~ 3.12。官方说明里提到 Windows 下因为 `ray` 依赖限制，不建议使用 Python 3.13。

```powershell
python -m venv .mineru-venv
.\.mineru-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install uv
uv pip install -U "mineru[all]"
```

安装完成后测试：

```powershell
mineru --help
```

如果可以看到帮助信息，说明命令可用。

测试解析一个文件：

```powershell
mineru -p C:\path\to\demo.pdf -o C:\path\to\mineru_output -b pipeline -l ch
```

然后在本项目的前端选择：

```text
PDF / 文档解析方式 -> MinerU 本地 Pipeline
```

## 方案二：指定 MinerU 命令路径

如果本项目后端找不到 `mineru` 命令，可以在 `.env` 里指定完整路径：

```env
MINERU_LOCAL_COMMAND=C:\Users\Dowell\Desktop\plan_and_solve_agent\.mineru-venv\Scripts\mineru.exe
```

重启后端后生效：

```powershell
python -m uvicorn bid_parser_api:app --host 127.0.0.1 --port 8000
```

## 方案三：WSL2 / Docker 部署

官方 Docker 部署只支持 Linux 和 Windows WSL2 环境。Docker 镜像中默认集成 vLLM 推理加速框架，适合有 NVIDIA GPU 的机器。

如果你有 NVIDIA GPU 服务器，推荐部署 `mineru-api`：

```bash
git clone https://github.com/opendatalab/MinerU.git
cd MinerU/docker
docker compose --profile api up -d
```

默认服务端口一般是：

```text
http://localhost:8000
```

如果和本项目 FastAPI 的 `8000` 端口冲突，可以把 MinerU 放到其他端口，例如 `8001`。

## 方案四：局域网 GPU 服务器

如果你的笔记本没有 NVIDIA GPU，但公司/局域网有 GPU 服务器，推荐：

```text
本机 Electron 前端 -> 本机 bid_parser_api -> 局域网 MinerU 服务
```

后续可以再给本项目增加 `MinerU 本地 API` 解析方式，直接调用局域网 `mineru-api`，避免在本机跑模型。

## 当前项目已支持的本地入口

当前已经接入：

```text
MinerU 本地 Pipeline
```

它会在后端执行类似命令：

```powershell
mineru -p <上传文件路径> -o <输出目录> -b pipeline -l ch
```

解析完成后，后端会在输出目录中查找 Markdown 文件，并继续拆分章节、交给大模型分析。

## 常见问题

### 1. 报错 Local MinerU command not found

说明系统找不到 `mineru` 命令。处理方式：

- 确认 MinerU 虚拟环境已安装
- 在命令行运行 `mineru --help`
- 或在 `.env` 中配置 `MINERU_LOCAL_COMMAND`

### 2. 本地 Pipeline 仍然慢

如果没有 NVIDIA GPU，CPU 解析复杂扫描 PDF 仍然会慢。建议：

- Word 文件继续用 `docx2python`
- 文本 PDF 用 `pdfplumber`
- 扫描件或复杂表格再用 MinerU
- 给同一文件增加解析缓存

### 3. Docker 启动失败

优先检查：

- 是否在 Linux 或 Windows WSL2
- Docker 是否可用
- NVIDIA 驱动和 NVIDIA Container Toolkit 是否安装
- 显存是否足够

## 后续可优化

- 增加 `MinerU 本地 API` 解析方式
- 增加文件 hash 缓存，避免重复解析
- 自动判断 Word / 文本 PDF / 扫描 PDF，选择最快解析器
- 支持局域网 MinerU GPU 服务
