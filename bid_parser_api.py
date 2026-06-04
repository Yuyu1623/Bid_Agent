# 这个脚本负责提供招标文件解析和分析的 FastAPI 后端接口。
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import AsyncIterator, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from bid_analysis_prompts import (
    build_price_scoring_messages_from_sections,
    build_project_overview_messages_from_sections,
    build_qualification_compliance_messages_from_sections,
    build_technical_scoring_messages_from_sections,
)
from bid_analysis_service import BidAnalysisResult, analyze_bid_document
from bid_document_parser import BidDocumentSection, parse_bid_document, split_bid_markdown_sections
from llm_client import LLM_Invoke
from llm_model_config import apply_llm_env_selection


app = FastAPI(title="Plan-and-Solve Bid Document Parser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _raise_api_error(exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()
    if "mineru" in lowered:
        error_type = "MinerU 解析失败"
    elif "llm" in lowered or "openai" in lowered or "model" in lowered:
        error_type = "大模型调用失败"
    elif "timeout" in lowered or "timed out" in lowered:
        error_type = "请求超时"
    elif "connection" in lowered or "network" in lowered or "fetch" in lowered:
        error_type = "网络连接失败"
    else:
        error_type = "后端处理失败"
    raise HTTPException(
        status_code=500,
        detail={
            "type": error_type,
            "message": message,
            "hint": (
                "如果是 MinerU 或大模型调用失败，优先检查网络、代理、API Key、模型名称和超时时间。"
                "如果是本地解析方式失败，检查文件格式和依赖包是否安装。"
            ),
        },
    ) from exc


def _stream_event(event_type: str, **payload: object) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


def _build_analysis_jobs(sections: List[BidDocumentSection]) -> list[tuple[str, str, list]]:
    return [
        (
            "project_overview",
            "项目概述",
            build_project_overview_messages_from_sections(sections),
        ),
        (
            "technical_scoring_requirements",
            "技术要求",
            build_technical_scoring_messages_from_sections(sections),
        ),
        (
            "qualification_compliance_requirements",
            "资格和符合性审查",
            build_qualification_compliance_messages_from_sections(sections),
        ),
        (
            "price_scoring_requirements",
            "评分要求",
            build_price_scoring_messages_from_sections(sections),
        ),
    ]


def _build_llm(llm_vendor: str, llm_model: Optional[str]) -> LLM_Invoke:
    resolved_model = None
    resolved_base_url = None
    if llm_model:
        resolved_model, resolved_base_url = apply_llm_env_selection(
            vendor=llm_vendor,
            model_name=llm_model,
        )
    return LLM_Invoke(model=resolved_model, base_url=resolved_base_url)


def _analyze_sections(
    sections: List[BidDocumentSection],
    llm_vendor: str,
    llm_model: Optional[str],
    stream_output: bool,
) -> BidAnalysisResult:
    llm = _build_llm(llm_vendor=llm_vendor, llm_model=llm_model)
    jobs = _build_analysis_jobs(sections)
    messages_batch = [messages for _, _, messages in jobs]
    try:
        (
            project_overview,
            technical_scoring_requirements,
            qualification_compliance_requirements,
            price_scoring_requirements,
        ) = llm.think_many_sync(messages_batch, stream=stream_output)
    except Exception:
        project_overview = llm.think(messages_batch[0], stream=stream_output)
        technical_scoring_requirements = llm.think(messages_batch[1], stream=stream_output)
        qualification_compliance_requirements = llm.think(
            messages_batch[2],
            stream=stream_output,
        )
        price_scoring_requirements = llm.think(messages_batch[3], stream=stream_output)

    return BidAnalysisResult(
        sections=sections,
        project_overview=project_overview,
        technical_scoring_requirements=technical_scoring_requirements,
        qualification_compliance_requirements=qualification_compliance_requirements,
        price_scoring_requirements=price_scoring_requirements,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class ParseDocumentRequest(BaseModel):
    document: str = Field(description="Local file path or remote document URL.")
    output_dir: Optional[str] = Field(default=None)
    parse_method: str = Field(default="mineru_vlm")
    model_version: str = Field(default="vlm")
    llm_vendor: str = Field(default="siliconflow")
    llm_model: Optional[str] = Field(default=None)
    stream_output: bool = Field(default=True)
    language: str = Field(default="ch")
    is_ocr: Optional[bool] = Field(default=None)
    enable_formula: bool = Field(default=True)
    enable_table: bool = Field(default=True)
    page_ranges: Optional[str] = Field(default=None)
    poll_interval: int = Field(default=5, ge=1)
    timeout: int = Field(default=600, ge=30)


class ParseDocumentResponse(BaseModel):
    sections: List[BidDocumentSection]


class AnalyzeDocumentResponse(BidAnalysisResult):
    pass


class AnalyzeContentRequest(BaseModel):
    file_content: str = Field(description="Edited parsed Markdown/text content.")
    llm_vendor: str = Field(default="siliconflow")
    llm_model: Optional[str] = Field(default=None)
    stream_output: bool = Field(default=True)


@app.post("/bid-documents/parse", response_model=ParseDocumentResponse)
def parse_document(request: ParseDocumentRequest) -> ParseDocumentResponse:
    try:
        sections = parse_bid_document(
            document=request.document,
            output_dir=request.output_dir,
            parse_method=request.parse_method,
            model_version=request.model_version,
            language=request.language,
            is_ocr=request.is_ocr,
            enable_formula=request.enable_formula,
            enable_table=request.enable_table,
            page_ranges=request.page_ranges,
            poll_interval=request.poll_interval,
            timeout=request.timeout,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return ParseDocumentResponse(sections=sections)


@app.post("/bid-documents/upload", response_model=ParseDocumentResponse)
def upload_document(
    file: UploadFile = File(...),
    output_dir: Optional[str] = Form(default=None),
    parse_method: str = Form(default="mineru_vlm"),
    model_version: str = Form(default="vlm"),
    llm_vendor: str = Form(default="siliconflow"),
    llm_model: Optional[str] = Form(default=None),
    language: str = Form(default="ch"),
    is_ocr: Optional[bool] = Form(default=None),
    enable_formula: bool = Form(default=True),
    enable_table: bool = Form(default=True),
    page_ranges: Optional[str] = Form(default=None),
    poll_interval: int = Form(default=5),
    timeout: int = Form(default=600),
) -> ParseDocumentResponse:
    suffix = Path(file.filename or "document").suffix
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / f"upload{suffix}"
        with temp_path.open("wb") as file_obj:
            file_obj.write(file.file.read())

        try:
            sections = parse_bid_document(
                document=str(temp_path),
                output_dir=output_dir,
                parse_method=parse_method,
                model_version=model_version,
                language=language,
                is_ocr=is_ocr,
                enable_formula=enable_formula,
                enable_table=enable_table,
                page_ranges=page_ranges,
                poll_interval=poll_interval,
                timeout=timeout,
            )
        except Exception as exc:
            _raise_api_error(exc)

    return ParseDocumentResponse(sections=sections)


@app.post("/bid-documents/analyze", response_model=AnalyzeDocumentResponse)
def analyze_document(request: ParseDocumentRequest) -> AnalyzeDocumentResponse:
    try:
        result = analyze_bid_document(
            document=request.document,
            output_dir=request.output_dir,
            parse_method=request.parse_method,
            model_version=request.model_version,
            llm_vendor=request.llm_vendor,
            llm_model=request.llm_model,
            stream_output=request.stream_output,
            language=request.language,
            is_ocr=request.is_ocr,
            enable_formula=request.enable_formula,
            enable_table=request.enable_table,
            page_ranges=request.page_ranges,
            poll_interval=request.poll_interval,
            timeout=request.timeout,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return AnalyzeDocumentResponse(**result.model_dump())


@app.post("/bid-documents/analyze-content", response_model=AnalyzeDocumentResponse)
def analyze_edited_content(request: AnalyzeContentRequest) -> AnalyzeDocumentResponse:
    try:
        sections = split_bid_markdown_sections(request.file_content)
        result = _analyze_sections(
            sections=sections,
            llm_vendor=request.llm_vendor,
            llm_model=request.llm_model,
            stream_output=request.stream_output,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return AnalyzeDocumentResponse(**result.model_dump())


@app.post("/bid-documents/upload-analyze", response_model=AnalyzeDocumentResponse)
def upload_and_analyze_document(
    file: UploadFile = File(...),
    output_dir: Optional[str] = Form(default=None),
    parse_method: str = Form(default="mineru_vlm"),
    model_version: str = Form(default="vlm"),
    llm_vendor: str = Form(default="siliconflow"),
    llm_model: Optional[str] = Form(default=None),
    stream_output: bool = Form(default=True),
    language: str = Form(default="ch"),
    is_ocr: Optional[bool] = Form(default=None),
    enable_formula: bool = Form(default=True),
    enable_table: bool = Form(default=True),
    page_ranges: Optional[str] = Form(default=None),
    poll_interval: int = Form(default=5),
    timeout: int = Form(default=600),
) -> AnalyzeDocumentResponse:
    suffix = Path(file.filename or "document").suffix
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / f"upload{suffix}"
        with temp_path.open("wb") as file_obj:
            file_obj.write(file.file.read())

        try:
            result = analyze_bid_document(
                document=str(temp_path),
                output_dir=output_dir,
                parse_method=parse_method,
                model_version=model_version,
                llm_vendor=llm_vendor,
                llm_model=llm_model,
                stream_output=stream_output,
                language=language,
                is_ocr=is_ocr,
                enable_formula=enable_formula,
                enable_table=enable_table,
                page_ranges=page_ranges,
                poll_interval=poll_interval,
                timeout=timeout,
            )
        except Exception as exc:
            _raise_api_error(exc)

    return AnalyzeDocumentResponse(**result.model_dump())


@app.post("/bid-documents/upload-analyze-stream")
async def upload_and_analyze_document_stream(
    file: UploadFile = File(...),
    output_dir: Optional[str] = Form(default=None),
    parse_method: str = Form(default="mineru_vlm"),
    model_version: str = Form(default="vlm"),
    llm_vendor: str = Form(default="siliconflow"),
    llm_model: Optional[str] = Form(default=None),
    language: str = Form(default="ch"),
    is_ocr: Optional[bool] = Form(default=None),
    enable_formula: bool = Form(default=True),
    enable_table: bool = Form(default=True),
    page_ranges: Optional[str] = Form(default=None),
    poll_interval: int = Form(default=5),
    timeout: int = Form(default=600),
) -> StreamingResponse:
    filename = file.filename or "document"
    suffix = Path(filename).suffix
    file_bytes = await file.read()

    async def event_generator() -> AsyncIterator[str]:
        results = {
            "project_overview": "",
            "technical_scoring_requirements": "",
            "qualification_compliance_requirements": "",
            "price_scoring_requirements": "",
        }
        try:
            yield _stream_event("status", message="文件已上传，正在解析招标文件...")
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"upload{suffix}"
                temp_path.write_bytes(file_bytes)
                sections = parse_bid_document(
                    document=str(temp_path),
                    output_dir=output_dir,
                    parse_method=parse_method,
                    model_version=model_version,
                    language=language,
                    is_ocr=is_ocr,
                    enable_formula=enable_formula,
                    enable_table=enable_table,
                    page_ranges=page_ranges,
                    poll_interval=poll_interval,
                    timeout=timeout,
                )

            yield _stream_event(
                "parsed",
                message=f"文件解析完成，共识别 {len(sections)} 个章节，开始调用大模型...",
                sections=[section.model_dump() for section in sections],
            )

            resolved_model = None
            resolved_base_url = None
            if llm_model:
                resolved_model, resolved_base_url = apply_llm_env_selection(
                    vendor=llm_vendor,
                    model_name=llm_model,
                )
            llm = LLM_Invoke(model=resolved_model, base_url=resolved_base_url)

            jobs = [
                (
                    "project_overview",
                    "项目概述",
                    build_project_overview_messages_from_sections(sections),
                ),
                (
                    "technical_scoring_requirements",
                    "技术要求",
                    build_technical_scoring_messages_from_sections(sections),
                ),
                (
                    "qualification_compliance_requirements",
                    "资格和符合性审查",
                    build_qualification_compliance_messages_from_sections(sections),
                ),
                (
                    "price_scoring_requirements",
                    "评分要求",
                    build_price_scoring_messages_from_sections(sections),
                ),
            ]

            yield _stream_event("status", message="正在并行提取四个分析模块...")
            parallel_failed = False
            queue: asyncio.Queue[dict] = asyncio.Queue()

            async def run_stream_job(field: str, label: str, messages: list) -> None:
                try:
                    await queue.put(
                        {
                            "type": "status",
                            "field": field,
                            "message": f"正在提取{label}...",
                        }
                    )
                    async for chunk in llm.astream(messages):
                        results[field] += chunk
                        await queue.put(
                            {
                                "type": "chunk",
                                "field": field,
                                "content": chunk,
                            }
                        )
                    await queue.put(
                        {
                            "type": "field_done",
                            "field": field,
                            "message": f"{label}提取完成",
                            "content": results[field],
                        }
                    )
                except Exception as exc:
                    await queue.put(
                        {
                            "type": "parallel_error",
                            "field": field,
                            "message": str(exc) or exc.__class__.__name__,
                        }
                    )

            tasks = [
                asyncio.create_task(run_stream_job(field, label, messages))
                for field, label, messages in jobs
            ]
            pending_count = len(tasks)
            while pending_count:
                event = await queue.get()
                if event["type"] == "parallel_error":
                    parallel_failed = True
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    yield _stream_event(
                        "status",
                        message="并行提取失败，正在自动切换为串行提取...",
                    )
                    break

                if event["type"] == "field_done":
                    pending_count -= 1

                yield _stream_event(str(event.pop("type")), **event)

            if parallel_failed:
                for field in results:
                    results[field] = ""
                for field, label, messages in jobs:
                    yield _stream_event("status", field=field, message=f"正在串行提取{label}...")
                    async for chunk in llm.astream(messages):
                        results[field] += chunk
                        yield _stream_event("chunk", field=field, content=chunk)
                    yield _stream_event(
                        "field_done",
                        field=field,
                        message=f"{label}提取完成",
                        content=results[field],
                    )

            yield _stream_event("done", message="全部分析完成", result=results)
        except Exception as exc:
            yield _stream_event(
                "error",
                message=str(exc) or exc.__class__.__name__,
                hint="优先检查后端日志、MinerU API、大模型 API Key、网络代理和模型名称映射。",
            )

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson; charset=utf-8",
    )


@app.post("/bid-documents/analyze-content-stream")
async def analyze_edited_content_stream(request: AnalyzeContentRequest) -> StreamingResponse:
    sections = split_bid_markdown_sections(request.file_content)

    async def event_generator() -> AsyncIterator[str]:
        results = {
            "project_overview": "",
            "technical_scoring_requirements": "",
            "qualification_compliance_requirements": "",
            "price_scoring_requirements": "",
        }
        try:
            yield _stream_event(
                "parsed",
                message=f"已接收修改后的解析内容，共 {len(sections)} 个章节，开始调用大模型...",
                sections=[section.model_dump() for section in sections],
            )
            llm = _build_llm(
                llm_vendor=request.llm_vendor,
                llm_model=request.llm_model,
            )
            jobs = _build_analysis_jobs(sections)
            yield _stream_event("status", message="正在并行提取四个分析模块...")
            parallel_failed = False
            queue: asyncio.Queue[dict] = asyncio.Queue()

            async def run_stream_job(field: str, label: str, messages: list) -> None:
                try:
                    await queue.put(
                        {
                            "type": "status",
                            "field": field,
                            "message": f"正在提取{label}...",
                        }
                    )
                    async for chunk in llm.astream(messages):
                        results[field] += chunk
                        await queue.put(
                            {
                                "type": "chunk",
                                "field": field,
                                "content": chunk,
                            }
                        )
                    await queue.put(
                        {
                            "type": "field_done",
                            "field": field,
                            "message": f"{label}提取完成",
                            "content": results[field],
                        }
                    )
                except Exception as exc:
                    await queue.put(
                        {
                            "type": "parallel_error",
                            "field": field,
                            "message": str(exc) or exc.__class__.__name__,
                        }
                    )

            tasks = [
                asyncio.create_task(run_stream_job(field, label, messages))
                for field, label, messages in jobs
            ]
            pending_count = len(tasks)
            while pending_count:
                event = await queue.get()
                if event["type"] == "parallel_error":
                    parallel_failed = True
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    yield _stream_event(
                        "status",
                        message="并行提取失败，正在自动切换为串行提取...",
                    )
                    break
                if event["type"] == "field_done":
                    pending_count -= 1
                yield _stream_event(str(event.pop("type")), **event)

            if parallel_failed:
                for field in results:
                    results[field] = ""
                for field, label, messages in jobs:
                    yield _stream_event("status", field=field, message=f"正在串行提取{label}...")
                    async for chunk in llm.astream(messages):
                        results[field] += chunk
                        yield _stream_event("chunk", field=field, content=chunk)
                    yield _stream_event(
                        "field_done",
                        field=field,
                        message=f"{label}提取完成",
                        content=results[field],
                    )

            yield _stream_event("done", message="修改内容分析完成", result=results)
        except Exception as exc:
            yield _stream_event(
                "error",
                message=str(exc) or exc.__class__.__name__,
                hint="检查修改后的文本是否为空，以及大模型 API Key、网络代理和模型名称映射。",
            )

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson; charset=utf-8",
    )
