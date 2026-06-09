# 这个脚本负责提供招标文件解析和分析的 FastAPI 后端接口。
import asyncio
import json
import os
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import AsyncIterator, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from bid_analysis_prompts import (
    build_business_content_messages_from_sections,
    build_business_scoring_messages_from_sections,
    build_project_overview_messages_from_sections,
    build_qualification_compliance_messages_from_sections,
    build_technical_scoring_messages_from_sections,
)
from bid_analysis_service import BidAnalysisResult, analyze_bid_document
from content_review_agent import build_content_review
from bid_document_parser import BidDocumentSection, parse_bid_document, split_bid_markdown_sections
from bid_image_analysis import analyze_document_images, format_image_analysis_markdown
from bid_parse_strategy import (
    build_parse_quality_report,
    count_docx_images,
    inspect_document_profile,
    resolve_parse_method,
)
from bid_section_retriever import retrieve_sections_for_analysis
from bid_database import (
    DB_PATH,
    KNOWLEDGE_TYPES,
    delete_knowledge_entry,
    delete_project,
    delete_project_record,
    export_knowledge_store,
    import_knowledge_store,
    init_database,
    get_project_detail,
    list_knowledge_entries,
    list_database_tables,
    list_projects,
    save_analysis_result,
    update_record_confirmed_status,
    upsert_knowledge_entry,
)
from extraction_cleaner import clean_analysis_dict, clean_repeated_extraction_text
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

BACKEND_BUILD = "2026-06-09-extraction-dedupe-v1"


@app.on_event("startup")
def _startup_init_database() -> None:
    init_database()


def _raise_api_error(exc: Exception) -> None:
    error_type, message, hint = _classify_exception(exc)
    raise HTTPException(
        status_code=500,
        detail={
            "type": error_type,
            "message": message,
            "hint": hint,
        },
    ) from exc


def _classify_exception(exc: Exception, stage: str = "") -> tuple[str, str, str]:
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
    elif "errno 22" in lowered or "invalid argument" in lowered:
        error_type = "大模型运行环境异常"
    else:
        error_type = "后端处理失败"
    if stage:
        error_type = f"{stage}：{error_type}"
    hint = (
        "如果是 MinerU 或大模型调用失败，优先检查网络、代理、API Key、模型名称和超时时间。"
        "如果是本地解析方式失败，检查文件格式和依赖包是否安装。"
    )
    return error_type, message, hint


def _stream_event(event_type: str, **payload: object) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


def _exception_traceback_tail(exc: Exception, limit: int = 8) -> str:
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return "".join(lines[-limit:]).strip()


def _build_analysis_jobs(sections: List[BidDocumentSection]) -> list[tuple[str, str, list]]:
    retrieved_sections = retrieve_sections_for_analysis(sections)
    return [
        (
            "project_overview",
            "项目概述",
            build_project_overview_messages_from_sections(retrieved_sections["project_overview"]),
        ),
        (
            "business_content",
            "商务内容",
            build_business_content_messages_from_sections(retrieved_sections["business_content"]),
        ),
        (
            "technical_scoring_requirements",
            "技术要求",
            build_technical_scoring_messages_from_sections(
                retrieved_sections["technical_requirements"]
            ),
        ),
        (
            "qualification_compliance_requirements",
            "资格和符合性审查",
            build_qualification_compliance_messages_from_sections(
                retrieved_sections["qualification_compliance"]
            ),
        ),
        (
            "price_scoring_requirements",
            "评分要求",
            build_business_scoring_messages_from_sections(retrieved_sections["scoring"]),
        ),
    ]


def _build_llm(
    llm_vendor: str,
    llm_model: Optional[str],
    enable_deep_thinking: bool = False,
) -> LLM_Invoke:
    resolved_model = None
    resolved_base_url = None
    if llm_model:
        resolved_model, resolved_base_url = apply_llm_env_selection(
            vendor=llm_vendor,
            model_name=llm_model,
        )
    return LLM_Invoke(
        model=resolved_model,
        base_url=resolved_base_url,
        enable_deep_thinking=enable_deep_thinking,
    )


def _build_content_review_llm_messages(
    source_text: str,
    extracted: dict,
    regex_report: str,
) -> list[dict[str, str]]:
    source_text = (source_text or "")[:60000]
    extracted_text = json.dumps(extracted or {}, ensure_ascii=False, indent=2)[:30000]
    regex_report = (regex_report or "")[:20000]
    return [
        {
            "role": "system",
            "content": (
                "你是严谨的招投标内容审查专家。请基于原文、已提取结果和正则审查报告，"
                "复核信息是否完整、准确、一致，并指出响应偏离、废标风险和需要人工核对的事项。"
                "不要重新生成五大模块内容，只输出审查意见。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请按以下 Markdown 结构输出：\n\n"
                "### 复核结论\n"
                "- 结论：\n"
                "- 主要风险：\n\n"
                "### 高风险问题\n"
                "| 模块 | 问题 | 原因 | 建议 |\n"
                "| --- | --- | --- | --- |\n\n"
                "### 需要人工核对\n"
                "| 模块 | 核对点 | 核对依据 |\n"
                "| --- | --- | --- |\n\n"
                "### 补充建议\n"
                "- \n\n"
                f"【正则审查报告】\n{regex_report}\n\n"
                f"【已提取结果】\n{extracted_text}\n\n"
                f"【原始解析文本】\n{source_text}"
            ),
        },
    ]


def _sections_to_markdown_for_review(sections: List[BidDocumentSection]) -> str:
    return "\n\n".join(
        section.markdown or section.content or ""
        for section in sections
        if section.markdown or section.content
    )


def _analyze_sections(
    sections: List[BidDocumentSection],
    llm_vendor: str,
    llm_model: Optional[str],
    stream_output: bool,
    enable_deep_thinking: bool = False,
) -> BidAnalysisResult:
    llm = _build_llm(
        llm_vendor=llm_vendor,
        llm_model=llm_model,
        enable_deep_thinking=enable_deep_thinking,
    )
    jobs = _build_analysis_jobs(sections)
    messages_batch = [messages for _, _, messages in jobs]
    try:
        (
            project_overview,
            business_content,
            technical_scoring_requirements,
            qualification_compliance_requirements,
            price_scoring_requirements,
        ) = llm.think_many_sync(messages_batch, stream=stream_output)
    except Exception:
        project_overview = llm.think(messages_batch[0], stream=stream_output)
        business_content = llm.think(messages_batch[1], stream=stream_output)
        technical_scoring_requirements = llm.think(messages_batch[2], stream=stream_output)
        qualification_compliance_requirements = llm.think(
            messages_batch[3],
            stream=stream_output,
        )
        price_scoring_requirements = llm.think(messages_batch[4], stream=stream_output)

    result = BidAnalysisResult(
        sections=sections,
        project_overview=clean_repeated_extraction_text(project_overview),
        business_content=clean_repeated_extraction_text(business_content),
        technical_scoring_requirements=clean_repeated_extraction_text(technical_scoring_requirements),
        qualification_compliance_requirements=clean_repeated_extraction_text(qualification_compliance_requirements),
        price_scoring_requirements=clean_repeated_extraction_text(price_scoring_requirements),
        content_review_markdown="内容审查尚未执行，请在前端点击“执行审查”。",
        content_review_report={},
    )
    try:
        save_analysis_result(
            sections=[section.model_dump() for section in sections],
            analysis=result.model_dump(),
            file_name="analyzed_content.md",
            document_type="招标文件",
            parse_method="structured_analysis",
        )
    except Exception:
        pass
    return result


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "build": BACKEND_BUILD,
        "features": {
            "module_level_llm_errors": True,
            "stream_fallback_non_stream": True,
            "runtime_env_write_disabled": True,
            "wide_retrieval_before_llm": True,
            "sqlite_knowledge_demo": True,
            "project_library": True,
            "extraction_dedupe": True,
        },
        "backend_file": __file__,
        "backend_dir": str(Path(__file__).resolve().parent),
    }


class ParseDocumentRequest(BaseModel):
    document: str = Field(description="Local file path or remote document URL.")
    output_dir: Optional[str] = Field(default=None)
    parse_method: str = Field(default="mineru_vlm")
    model_version: str = Field(default="vlm")
    llm_vendor: str = Field(default="siliconflow")
    llm_model: Optional[str] = Field(default=None)
    stream_output: bool = Field(default=True)
    enable_deep_thinking: bool = Field(default=False)
    language: str = Field(default="ch")
    is_ocr: Optional[bool] = Field(default=None)
    enable_formula: bool = Field(default=True)
    enable_table: bool = Field(default=True)
    page_ranges: Optional[str] = Field(default=None)
    poll_interval: int = Field(default=5, ge=1)
    timeout: int = Field(default=600, ge=30)


class ParseDocumentResponse(BaseModel):
    sections: List[BidDocumentSection]
    parse_method_used: str = ""
    parse_method_recommended: str = ""
    parse_quality: dict = Field(default_factory=dict)


class AnalyzeDocumentResponse(BidAnalysisResult):
    pass


class AnalyzeContentRequest(BaseModel):
    file_content: str = Field(description="Edited parsed Markdown/text content.")
    llm_vendor: str = Field(default="siliconflow")
    llm_model: Optional[str] = Field(default=None)
    stream_output: bool = Field(default=True)
    enable_deep_thinking: bool = Field(default=False)


class ContentReviewRequest(BaseModel):
    sections: List[BidDocumentSection] = Field(default_factory=list)
    file_content: str = Field(default="")
    extracted: dict = Field(default_factory=dict)
    llm_vendor: str = Field(default="siliconflow")
    llm_model: Optional[str] = Field(default=None)
    enable_deep_thinking: bool = Field(default=False)


class ContentReviewResponse(BaseModel):
    content_review_markdown: str = ""
    content_review_report: dict = Field(default_factory=dict)


class KnowledgeEntryRequest(BaseModel):
    id: Optional[str] = None
    type: str = Field(default="company")
    title: str
    tags: str = ""
    date: str = ""
    files: str = ""
    content: str = ""
    notes: str = ""
    createdAt: Optional[str] = None


class KnowledgeEntryResponse(BaseModel):
    entry: dict


class KnowledgeListResponse(BaseModel):
    entries: List[dict]


class KnowledgeImportRequest(BaseModel):
    store: dict = Field(default_factory=dict)


class KnowledgeImportResponse(BaseModel):
    imported_count: int


class ConfirmRecordRequest(BaseModel):
    status: str = Field(default="已确认")


@app.get("/knowledge/types")
def get_knowledge_types() -> dict:
    return {
        "types": [
            {"id": key, "title": value}
            for key, value in KNOWLEDGE_TYPES.items()
        ]
    }


@app.get("/database/tables")
def get_database_tables() -> dict:
    try:
        tables = list_database_tables()
    except Exception as exc:
        _raise_api_error(exc)
    return {"database_path": str(DB_PATH), "tables": tables}


@app.get("/projects")
def get_projects(q: Optional[str] = None) -> dict:
    try:
        projects = list_projects(query=q)
    except Exception as exc:
        _raise_api_error(exc)
    return {"projects": projects}


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    try:
        detail = get_project_detail(project_id)
    except Exception as exc:
        _raise_api_error(exc)
    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")
    return detail


@app.post("/projects/records/{table_name}/{record_id}/confirm")
def confirm_project_record(table_name: str, record_id: str, request: ConfirmRecordRequest) -> dict:
    try:
        record = update_record_confirmed_status(table_name, record_id, request.status)
    except Exception as exc:
        _raise_api_error(exc)
    return {"record": record}


@app.delete("/projects/{project_id}")
def remove_project(project_id: str) -> dict:
    try:
        result = delete_project(project_id)
    except Exception as exc:
        _raise_api_error(exc)
    return result


@app.delete("/projects/records/{table_name}/{record_id}")
def remove_project_record(table_name: str, record_id: str) -> dict:
    try:
        result = delete_project_record(table_name, record_id)
    except Exception as exc:
        _raise_api_error(exc)
    return result


@app.get("/knowledge/entries", response_model=KnowledgeListResponse)
def get_knowledge_entries(
    type: Optional[str] = None,
    q: Optional[str] = None,
) -> KnowledgeListResponse:
    try:
        entries = list_knowledge_entries(entry_type=type, query=q)
    except Exception as exc:
        _raise_api_error(exc)
    return KnowledgeListResponse(entries=entries)


@app.post("/knowledge/entries", response_model=KnowledgeEntryResponse)
def save_knowledge_entry(request: KnowledgeEntryRequest) -> KnowledgeEntryResponse:
    try:
        entry = upsert_knowledge_entry(request.model_dump())
    except Exception as exc:
        _raise_api_error(exc)
    return KnowledgeEntryResponse(entry=entry)


@app.delete("/knowledge/entries/{entry_id}")
def remove_knowledge_entry(entry_id: str) -> dict:
    try:
        deleted = delete_knowledge_entry(entry_id)
    except Exception as exc:
        _raise_api_error(exc)
    return {"deleted": deleted}


@app.get("/knowledge/export")
def export_knowledge() -> dict:
    try:
        store = export_knowledge_store()
    except Exception as exc:
        _raise_api_error(exc)
    return {"store": store, "db_path": str(DB_PATH)}


@app.post("/knowledge/import", response_model=KnowledgeImportResponse)
def import_knowledge(request: KnowledgeImportRequest) -> KnowledgeImportResponse:
    try:
        count = import_knowledge_store(request.store)
    except Exception as exc:
        _raise_api_error(exc)
    return KnowledgeImportResponse(imported_count=count)


@app.post("/bid-documents/parse", response_model=ParseDocumentResponse)
def parse_document(request: ParseDocumentRequest) -> ParseDocumentResponse:
    try:
        preflight_profile = inspect_document_profile(request.document)
        parse_method_used, _ = resolve_parse_method(request.document, request.parse_method)
        sections = parse_bid_document(
            document=request.document,
            output_dir=request.output_dir,
            parse_method=parse_method_used,
            model_version=request.model_version,
            language=request.language,
            is_ocr=request.is_ocr,
            enable_formula=request.enable_formula,
            enable_table=request.enable_table,
            page_ranges=request.page_ranges,
            poll_interval=request.poll_interval,
            timeout=request.timeout,
        )
        parse_method_recommended = preflight_profile.get(
            "recommended_parse_method",
            parse_method_used,
        )
        parse_quality = build_parse_quality_report(
            sections=sections,
            parse_method_used=parse_method_used,
            parse_method_recommended=parse_method_recommended,
            image_count=int(preflight_profile.get("image_count") or count_docx_images(Path(request.document))),
            preflight_profile=preflight_profile,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return ParseDocumentResponse(
        sections=sections,
        parse_method_used=parse_method_used,
        parse_method_recommended=parse_method_recommended,
        parse_quality=parse_quality,
    )


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
            preflight_profile = inspect_document_profile(str(temp_path))
            parse_method_used, _ = resolve_parse_method(str(temp_path), parse_method)
            sections = parse_bid_document(
                document=str(temp_path),
                output_dir=output_dir,
                parse_method=parse_method_used,
                model_version=model_version,
                language=language,
                is_ocr=is_ocr,
                enable_formula=enable_formula,
                enable_table=enable_table,
                page_ranges=page_ranges,
                poll_interval=poll_interval,
                timeout=timeout,
            )
            parse_method_recommended = preflight_profile.get(
                "recommended_parse_method",
                parse_method_used,
            )
            parse_quality = build_parse_quality_report(
                sections=sections,
                parse_method_used=parse_method_used,
                parse_method_recommended=parse_method_recommended,
                image_count=int(preflight_profile.get("image_count") or count_docx_images(temp_path)),
                preflight_profile=preflight_profile,
            )
        except Exception as exc:
            _raise_api_error(exc)

    return ParseDocumentResponse(
        sections=sections,
        parse_method_used=parse_method_used,
        parse_method_recommended=parse_method_recommended,
        parse_quality=parse_quality,
    )


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
            enable_deep_thinking=request.enable_deep_thinking,
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
            enable_deep_thinking=request.enable_deep_thinking,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return AnalyzeDocumentResponse(**result.model_dump())


@app.post("/bid-documents/content-review", response_model=ContentReviewResponse)
def review_extracted_content(request: ContentReviewRequest) -> ContentReviewResponse:
    try:
        sections = request.sections or split_bid_markdown_sections(request.file_content)
        report = build_content_review(sections=sections, extracted=request.extracted)
        if request.llm_model:
            try:
                llm = _build_llm(
                    llm_vendor=request.llm_vendor,
                    llm_model=request.llm_model,
                    enable_deep_thinking=request.enable_deep_thinking,
                )
                llm_review = llm.think(
                    _build_content_review_llm_messages(
                        source_text=request.file_content or _sections_to_markdown_for_review(sections),
                        extracted=request.extracted,
                        regex_report=report.get("markdown", ""),
                    ),
                    stream=False,
                )
                if llm_review:
                    report["llm_review_markdown"] = llm_review
                    report["markdown"] = "\n\n".join(
                        [
                            report.get("markdown", ""),
                            "## 大模型深度审查",
                            "",
                            llm_review.strip(),
                        ]
                    ).strip()
            except Exception as llm_exc:
                error_type, message, hint = _classify_exception(llm_exc, stage="内容审查大模型复核")
                report["llm_review_error"] = {
                    "type": error_type,
                    "message": message,
                    "hint": hint,
                }
                report["markdown"] = "\n\n".join(
                    [
                        report.get("markdown", ""),
                        "## 大模型深度审查",
                        "",
                        "大模型深度审查失败，但正则审查报告已生成。",
                        "",
                        f"- 错误类型：{error_type}",
                        f"- 错误信息：{message}",
                        f"- 排查建议：{hint}",
                    ]
                ).strip()
    except Exception as exc:
        _raise_api_error(exc)
    return ContentReviewResponse(
        content_review_markdown=report.get("markdown", ""),
        content_review_report=report,
    )


@app.post("/bid-documents/upload-analyze", response_model=AnalyzeDocumentResponse)
def upload_and_analyze_document(
    file: UploadFile = File(...),
    output_dir: Optional[str] = Form(default=None),
    parse_method: str = Form(default="mineru_vlm"),
    model_version: str = Form(default="vlm"),
    llm_vendor: str = Form(default="siliconflow"),
    llm_model: Optional[str] = Form(default=None),
    stream_output: bool = Form(default=True),
    enable_deep_thinking: bool = Form(default=False),
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
            parse_method_used, _ = resolve_parse_method(str(temp_path), parse_method)
            result = analyze_bid_document(
                document=str(temp_path),
                output_dir=output_dir,
                parse_method=parse_method_used,
                model_version=model_version,
                llm_vendor=llm_vendor,
                llm_model=llm_model,
                stream_output=stream_output,
                enable_deep_thinking=enable_deep_thinking,
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
    enable_deep_thinking: bool = Form(default=False),
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
        current_stage = "解析阶段"
        results = {
            "project_overview": "",
            "business_content": "",
            "technical_scoring_requirements": "",
            "qualification_compliance_requirements": "",
            "price_scoring_requirements": "",
        }
        try:
            yield _stream_event("status", message="文件已上传，正在解析招标文件...")
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"upload{suffix}"
                temp_path.write_bytes(file_bytes)
                preflight_profile = inspect_document_profile(str(temp_path))
                parse_method_used, _ = resolve_parse_method(str(temp_path), parse_method)
                parse_method_recommended = preflight_profile.get(
                    "recommended_parse_method",
                    parse_method_used,
                )
                sections = parse_bid_document(
                    document=str(temp_path),
                    output_dir=output_dir,
                    parse_method=parse_method_used,
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
                parse_method_used=parse_method_used,
                parse_method_recommended=parse_method_recommended,
                preflight_profile=preflight_profile,
            )

            current_stage = "大模型阶段"
            resolved_model = None
            resolved_base_url = None
            if llm_model:
                resolved_model, resolved_base_url = apply_llm_env_selection(
                    vendor=llm_vendor,
                    model_name=llm_model,
                )
            llm = LLM_Invoke(
                model=resolved_model,
                base_url=resolved_base_url,
                enable_deep_thinking=enable_deep_thinking,
            )

            async def run_image_analysis():
                with TemporaryDirectory() as image_temp_dir:
                    image_temp_path = Path(image_temp_dir) / f"upload{suffix}"
                    image_temp_path.write_bytes(file_bytes)
                    image_items = await analyze_document_images(
                        document=str(image_temp_path),
                        llm=llm,
                        parse_method=parse_method_used,
                        model_version=model_version,
                        language=language,
                        is_ocr=is_ocr,
                        enable_formula=enable_formula,
                        enable_table=enable_table,
                        page_ranges=page_ranges,
                    )
                    return image_items

            image_task = asyncio.create_task(run_image_analysis())

            jobs = _build_analysis_jobs(sections)

            stream_concurrency = max(1, int(os.getenv("LLM_STREAM_MAX_CONCURRENCY", "1")))
            stream_semaphore = asyncio.Semaphore(stream_concurrency)
            yield _stream_event(
                "status",
                message=f"正在提取五个分析模块（流式并发 {stream_concurrency} 路）...",
            )
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
                    async with stream_semaphore:
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
                        message="流式提取失败，正在自动切换为非流式稳定提取...",
                    )
                    break

                if event["type"] == "field_done":
                    pending_count -= 1

                yield _stream_event(str(event.pop("type")), **event)

            if parallel_failed:
                for field in results:
                    results[field] = ""
                for field, label, messages in jobs:
                    yield _stream_event("status", field=field, message=f"正在稳定提取{label}...")
                    try:
                        results[field] = await llm.athink(messages, stream=False)
                    except Exception as exc:
                        error_type, message, hint = _classify_exception(exc, stage=f"{label}提取")
                        results[field] = "\n".join(
                            [
                                f"{label}提取失败。",
                                f"错误类型：{error_type}",
                                f"错误信息：{message}",
                                f"排查建议：{hint}",
                                "",
                                "后端 traceback 摘要：",
                                _exception_traceback_tail(exc),
                            ]
                        )
                    yield _stream_event(
                        "field_done",
                        field=field,
                        message=f"{label}提取完成" if not results[field].startswith(f"{label}提取失败。") else f"{label}提取失败",
                        content=results[field],
                    )

            results = clean_analysis_dict(results)
            for field, label, _ in jobs:
                if results.get(field):
                    yield _stream_event(
                        "field_done",
                        field=field,
                        message=f"{label}清洗去重完成",
                        content=results[field],
                    )

            current_stage = "图片解析阶段"
            try:
                image_items = await image_task
                image_analysis_markdown = format_image_analysis_markdown(image_items)
                image_analysis_items = [item.model_dump() for item in image_items]
            except Exception as exc:
                image_analysis_markdown = f"图片解析失败：{exc}"
                image_analysis_items = []
            image_count = len(image_analysis_items) or int(preflight_profile.get("image_count") or 0)
            image_ocr_chars = sum(len(str(item.get("ocr_text", ""))) for item in image_analysis_items)
            parse_quality = build_parse_quality_report(
                sections=sections,
                parse_method_used=parse_method_used,
                parse_method_recommended=parse_method_recommended,
                image_count=image_count,
                image_ocr_chars=image_ocr_chars,
                preflight_profile=preflight_profile,
            )
            results["image_analysis_markdown"] = image_analysis_markdown
            results["image_analysis_items"] = image_analysis_items
            results["parse_method_used"] = parse_method_used
            results["parse_method_recommended"] = parse_method_recommended
            results["preflight_profile"] = preflight_profile
            results["parse_quality"] = parse_quality
            results["sections"] = [section.model_dump() for section in sections]
            results["content_review_report"] = {}
            results["content_review_markdown"] = "内容审查尚未执行，请在前端点击“执行审查”。"
            try:
                db_result = save_analysis_result(
                    sections=results["sections"],
                    analysis=results,
                    file_name=filename,
                    document_type="招标文件",
                    parse_method=parse_method_used,
                )
                results["database_save"] = db_result
            except Exception as db_exc:
                results["database_save_error"] = str(db_exc)
            yield _stream_event(
                "image_analysis",
                message="图片解析和备注生成完成",
                content=image_analysis_markdown,
                items=image_analysis_items,
                parse_quality=parse_quality,
            )

            yield _stream_event("done", message="全部分析完成", result=results)
        except Exception as exc:
            error_type, message, hint = _classify_exception(exc, stage=current_stage)
            yield _stream_event(
                "error",
                error_type=error_type,
                message=message,
                hint=hint,
                traceback=_exception_traceback_tail(exc),
            )

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson; charset=utf-8",
    )


@app.post("/bid-documents/analyze-content-stream")
async def analyze_edited_content_stream(request: AnalyzeContentRequest) -> StreamingResponse:
    sections = split_bid_markdown_sections(request.file_content)

    async def event_generator() -> AsyncIterator[str]:
        current_stage = "大模型阶段"
        results = {
            "project_overview": "",
            "business_content": "",
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
                enable_deep_thinking=request.enable_deep_thinking,
            )
            jobs = _build_analysis_jobs(sections)
            stream_concurrency = max(1, int(os.getenv("LLM_STREAM_MAX_CONCURRENCY", "1")))
            stream_semaphore = asyncio.Semaphore(stream_concurrency)
            yield _stream_event(
                "status",
                message=f"正在提取五个分析模块（流式并发 {stream_concurrency} 路）...",
            )
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
                    async with stream_semaphore:
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
                        message="流式提取失败，正在自动切换为非流式稳定提取...",
                    )
                    break
                if event["type"] == "field_done":
                    pending_count -= 1
                yield _stream_event(str(event.pop("type")), **event)

            if parallel_failed:
                for field in results:
                    results[field] = ""
                for field, label, messages in jobs:
                    yield _stream_event("status", field=field, message=f"正在稳定提取{label}...")
                    try:
                        results[field] = await llm.athink(messages, stream=False)
                    except Exception as exc:
                        error_type, message, hint = _classify_exception(exc, stage=f"{label}提取")
                        results[field] = "\n".join(
                            [
                                f"{label}提取失败。",
                                f"错误类型：{error_type}",
                                f"错误信息：{message}",
                                f"排查建议：{hint}",
                                "",
                                "后端 traceback 摘要：",
                                _exception_traceback_tail(exc),
                            ]
                        )
                    yield _stream_event(
                        "field_done",
                        field=field,
                        message=f"{label}提取完成" if not results[field].startswith(f"{label}提取失败。") else f"{label}提取失败",
                        content=results[field],
                    )

            results = clean_analysis_dict(results)
            for field, label, _ in jobs:
                if results.get(field):
                    yield _stream_event(
                        "field_done",
                        field=field,
                        message=f"{label}清洗去重完成",
                        content=results[field],
                    )

            results["sections"] = [section.model_dump() for section in sections]
            results["content_review_report"] = {}
            results["content_review_markdown"] = "内容审查尚未执行，请在前端点击“执行审查”。"
            try:
                db_result = save_analysis_result(
                    sections=results["sections"],
                    analysis=results,
                    file_name="edited_content.md",
                    document_type="招标文件",
                    parse_method="edited_content",
                )
                results["database_save"] = db_result
            except Exception as db_exc:
                results["database_save_error"] = str(db_exc)
            yield _stream_event("done", message="修改内容分析完成", result=results)
        except Exception as exc:
            error_type, message, hint = _classify_exception(exc, stage=current_stage)
            yield _stream_event(
                "error",
                error_type=error_type,
                message=message,
                hint=hint,
                traceback=_exception_traceback_tail(exc),
            )

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson; charset=utf-8",
    )
