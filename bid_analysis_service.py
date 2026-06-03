''' 招标文件分析服务，包含解析招标文件、构建提示词、调用LLM进行分析的函数。'''
# -*- coding: utf-8 -*-
from typing import List, Optional

from pydantic import BaseModel, Field

from bid_analysis_prompts import (
    extract_price_scoring_requirements_from_sections,
    extract_project_overview_from_sections,
    extract_qualification_compliance_requirements_from_sections,
    extract_technical_scoring_requirements_from_sections,
)
from bid_document_parser import BidDocumentSection, parse_bid_document
from llm_client import LLM_Invoke
from llm_model_config import apply_llm_env_selection


class BidAnalysisResult(BaseModel):
    sections: List[BidDocumentSection] = Field(description="MinerU parsed sections.")
    project_overview: str = Field(description="LLM extracted project overview.")
    technical_scoring_requirements: str = Field(
        description="LLM extracted technical scoring requirements."
    )
    qualification_compliance_requirements: str = Field(
        description="LLM extracted qualification and compliance review requirements."
    )
    price_scoring_requirements: str = Field(
        description="LLM extracted price scoring requirements."
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
    llm_client: Optional[LLM_Invoke] = None,
) -> BidAnalysisResult:
    """Parse a bid document, pack parsed content with prompts, then ask the LLM."""
    sections = parse_bid_document(
        document=document,
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
    resolved_model = None
    resolved_base_url = None
    if llm_model:
        resolved_model, resolved_base_url = apply_llm_env_selection(
            vendor=llm_vendor,
            model_name=llm_model,
        )
    llm = llm_client or LLM_Invoke(model=resolved_model, base_url=resolved_base_url)

    project_overview = extract_project_overview_from_sections(sections, llm)
    technical_scoring_requirements = extract_technical_scoring_requirements_from_sections(
        sections,
        llm,
    )
    qualification_compliance_requirements = (
        extract_qualification_compliance_requirements_from_sections(
            sections,
            llm,
        )
    )
    price_scoring_requirements = extract_price_scoring_requirements_from_sections(
        sections,
        llm,
    )

    return BidAnalysisResult(
        sections=sections,
        project_overview=project_overview,
        technical_scoring_requirements=technical_scoring_requirements,
        qualification_compliance_requirements=qualification_compliance_requirements,
        price_scoring_requirements=price_scoring_requirements,
    )
# 这个脚本负责把文件解析结果交给大模型，并汇总招标分析结果。
