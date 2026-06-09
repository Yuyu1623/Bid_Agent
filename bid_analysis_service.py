''' 招标文件分析服务，包含解析招标文件、构建提示词、调用LLM进行分析的函数。'''
# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from bid_analysis_prompts import (
    build_business_content_messages_from_sections,
    build_business_scoring_messages_from_sections,
    build_project_overview_messages_from_sections,
    build_qualification_compliance_messages_from_sections,
    build_technical_scoring_messages_from_sections,
)
from bid_document_parser import BidDocumentSection, parse_bid_document
from bid_image_analysis import analyze_document_images, format_image_analysis_markdown
from bid_parse_strategy import (
    build_parse_quality_report,
    count_docx_images,
    inspect_document_profile,
    resolve_parse_method,
)
from bid_section_retriever import retrieve_sections_for_analysis
from bid_database import save_analysis_result
from extraction_cleaner import clean_repeated_extraction_text
from llm_client import LLM_Invoke
from llm_model_config import apply_llm_env_selection


class BidAnalysisResult(BaseModel):
    sections: List[BidDocumentSection] = Field(description="MinerU parsed sections.")
    project_overview: str = Field(description="LLM extracted project overview.")
    business_content: str = Field(default="", description="LLM extracted business content.")
    technical_scoring_requirements: str = Field(
        description="LLM extracted technical scoring requirements."
    )
    qualification_compliance_requirements: str = Field(
        description="LLM extracted qualification and compliance review requirements."
    )
    price_scoring_requirements: str = Field(
        description="LLM extracted price scoring requirements."
    )
    image_analysis_markdown: str = Field(
        default="",
        description="OCR and LLM notes for images extracted from the bid document.",
    )
    image_analysis_items: List[dict] = Field(
        default_factory=list,
        description="Image preview, OCR text, and LLM notes for extracted images.",
    )
    parse_method_used: str = Field(default="", description="Actual parser used.")
    parse_method_recommended: str = Field(default="", description="Recommended parser.")
    parse_quality: dict = Field(default_factory=dict, description="Parse quality metrics.")
    content_review_markdown: str = Field(
        default="",
        description="Regex-based completeness and accuracy review report.",
    )
    content_review_report: dict = Field(
        default_factory=dict,
        description="Structured regex-based content review report.",
    )


def analyze_bid_document(
    document: str,
    output_dir: Optional[str] = None,
    model_version: str = "vlm",
    language: str = "ch",
    is_ocr: bool = False,
    enable_formula: bool = True,
    enable_table: bool = True,
    page_ranges: Optional[str] = None,
    poll_interval: int = 5,
    timeout: int = 600,
    parse_method: str = "mineru_vlm",
    llm_vendor: str = "siliconflow",
    llm_model: Optional[str] = None,
    stream_output: bool = True,
    enable_deep_thinking: bool = False,
    llm_client: Optional[LLM_Invoke] = None,
) -> BidAnalysisResult:
    """Parse a bid document, pack parsed content with prompts, then ask the LLM."""
    preflight_profile = inspect_document_profile(document)
    parse_method_used, _ = resolve_parse_method(document, parse_method)
    parse_method_recommended = preflight_profile.get("recommended_parse_method", parse_method_used)
    sections = parse_bid_document(
        document=document,
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
    resolved_model = None
    resolved_base_url = None
    if llm_model:
        resolved_model, resolved_base_url = apply_llm_env_selection(
            vendor=llm_vendor,
            model_name=llm_model,
        )
    llm = llm_client or LLM_Invoke(
        model=resolved_model,
        base_url=resolved_base_url,
        enable_deep_thinking=enable_deep_thinking,
    )

    retrieved_sections = retrieve_sections_for_analysis(sections)
    messages_batch = [
        build_project_overview_messages_from_sections(retrieved_sections["project_overview"]),
        build_business_content_messages_from_sections(retrieved_sections["business_content"]),
        build_technical_scoring_messages_from_sections(retrieved_sections["technical_requirements"]),
        build_qualification_compliance_messages_from_sections(
            retrieved_sections["qualification_compliance"]
        ),
        build_business_scoring_messages_from_sections(retrieved_sections["scoring"]),
    ]
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

    image_analysis_markdown = ""
    image_analysis_items = []
    try:
        image_items = asyncio.run(
            analyze_document_images(
                document=document,
                llm=llm,
                parse_method=parse_method_used,
                model_version=model_version,
                language=language,
                is_ocr=is_ocr,
                enable_formula=enable_formula,
                enable_table=enable_table,
                page_ranges=page_ranges,
            )
        )
        image_analysis_markdown = format_image_analysis_markdown(image_items)
        image_analysis_items = [item.model_dump() for item in image_items]
    except Exception as exc:
        image_analysis_markdown = f"图片解析失败：{exc}"

    image_count = len(image_analysis_items) or count_docx_images(Path(document))
    image_ocr_chars = sum(len(str(item.get("ocr_text", ""))) for item in image_analysis_items)
    parse_quality = build_parse_quality_report(
        sections=sections,
        parse_method_used=parse_method_used,
        parse_method_recommended=parse_method_recommended,
        image_count=image_count,
        image_ocr_chars=image_ocr_chars,
        preflight_profile=preflight_profile,
    )
    result = BidAnalysisResult(
        sections=sections,
        project_overview=clean_repeated_extraction_text(project_overview),
        business_content=clean_repeated_extraction_text(business_content),
        technical_scoring_requirements=clean_repeated_extraction_text(technical_scoring_requirements),
        qualification_compliance_requirements=clean_repeated_extraction_text(qualification_compliance_requirements),
        price_scoring_requirements=clean_repeated_extraction_text(price_scoring_requirements),
        image_analysis_markdown=image_analysis_markdown,
        image_analysis_items=image_analysis_items,
        parse_method_used=parse_method_used,
        parse_method_recommended=parse_method_recommended,
        parse_quality=parse_quality,
        content_review_markdown="内容审查尚未执行，请在前端点击“执行审查”。",
        content_review_report={},
    )
    try:
        save_analysis_result(
            sections=[section.model_dump() for section in sections],
            analysis=result.model_dump(),
            file_name=Path(document).name,
            document_type="招标文件",
            parse_method=parse_method_used,
        )
    except Exception:
        pass
    return result
# 这个脚本负责把文件解析结果交给大模型，并汇总招标分析结果。
