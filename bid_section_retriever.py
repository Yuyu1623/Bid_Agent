# -*- coding: utf-8 -*-
"""Wide-recall section retrieval before LLM extraction."""
from __future__ import annotations

import os
import re
from typing import Iterable, Sequence

from bid_document_parser import BidDocumentSection


MODULE_PATTERNS: dict[str, Sequence[str]] = {
    "project_overview": (
        r"投标人须知|投标须知|供应商须知|响应人须知|竞标人须知|申请人须知",
        r"项目概况|项目概览|项目简介|项目背景|项目基本情况|采购项目|招标项目",
        r"采购需求|采购内容|招标内容|服务内容|建设内容|项目内容|实施内容",
        r"项目名称|项目编号|包号|标包|采购预算|最高限价|项目预算|项目规模",
        r"招标人|采购人|采购单位|招标代理|采购代理|代理机构",
        r"服务期限|服务期|履约期限|工期|交付期|实施周期",
        r"开标|投标截止|递交截止|报名|获取招标文件|澄清|答疑|保证金",
        r"中小企业|小微企业|专门面向|暗标|盲评|技术暗标",
    ),
    "business_content": (
        r"商务要求|商务条款|商务条件|商务部分|商务响应|商务偏离|商务规格",
        r"合同条款|合同格式|合同主要条款|付款方式|支付方式|结算方式",
        r"履约保证金|投标保证金|质量保证金|保证金|违约责任|验收|售后服务",
        r"报价要求|报价方式|价格要求|价格组成|费用承担|税费|发票",
        r"交付|交货|供货|服务期限|履约期限|服务地点|交货地点|实施地点",
        r"业绩|信誉|财务|人员|团队|资质证书|授权|承诺函",
        r"知识产权|保密|培训|维护|质保|质量保证|服务承诺",
    ),
    "technical_requirements": (
        r"技术要求|技术规格|技术参数|技术标准|技术规范|技术部分|技术响应",
        r"采购需求|服务需求|建设需求|功能需求|业务需求|系统需求|性能要求",
        r"实施方案|技术方案|服务方案|项目方案|总体方案|设计方案",
        r"设备清单|货物清单|参数表|配置要求|功能清单|技术指标",
        r"接口|兼容|安全|性能|可靠性|可用性|扩展性|运维|部署|验收标准",
        r"图表|流程图|架构图|示意图|图片|附图|图纸|表格",
    ),
    "qualification_compliance": (
        r"资格审查|资格性审查|资格要求|资格条件|资格证明|资格文件",
        r"符合性审查|符合性检查|符合性评审|响应性审查|响应性评审",
        r"初步审查|初审|形式审查|实质性响应|无效投标|无效响应",
        r"废标|否决投标|投标无效|响应无效|拒绝投标|重大偏差",
        r"审查表|评审表|资格审查表|符合性审查表|废标条款|否决条款",
        r"营业执照|资质|许可证|授权书|法定代表人|联合体|信用中国|政府采购",
        r"承诺函|声明函|中小企业声明函|财务状况|纳税|社保|业绩",
    ),
    "scoring": (
        r"评分办法|评分标准|评分细则|评审办法|评审标准|评标办法|评标标准",
        r"综合评分|综合评审|评分表|评审表|分值|得分|满分|权重",
        r"商务评分|商务分|商务评审|商务部分评分|商务评价",
        r"技术评分|技术分|技术评审|技术部分评分|技术评价",
        r"价格评分|报价评分|价格分|报价分|价格评审|价格权重",
        r"评分项|评审项|评分因素|评审因素|评价因素|评分内容",
        r"客观分|主观分|加分|扣分|优良中差|横向比较",
    ),
}


MODULE_LABELS = {
    "project_overview": "项目概况候选片段",
    "business_content": "商务内容候选片段",
    "technical_requirements": "技术要求候选片段",
    "qualification_compliance": "资格审查候选片段",
    "scoring": "评分要求候选片段",
}


def retrieve_sections_for_analysis(
    sections: Sequence[BidDocumentSection],
) -> dict[str, list[BidDocumentSection]]:
    """Build per-module candidate contexts with wide keyword recall."""
    return {
        module: retrieve_sections_for_module(module, sections)
        for module in MODULE_PATTERNS
    }


def retrieve_sections_for_module(
    module: str,
    sections: Sequence[BidDocumentSection],
    *,
    context_chars: int | None = None,
    max_chars: int | None = None,
    neighbor_sections: int = 1,
) -> list[BidDocumentSection]:
    """Return focused candidate sections for a module.

    The matching is intentionally broad: any keyword hit can recall a section.
    Large sections are sliced around hits so the LLM does not repeatedly read
    the whole bid document.
    """
    if module not in MODULE_PATTERNS:
        return list(sections)

    context_chars = context_chars or int(os.getenv("BID_RETRIEVAL_CONTEXT_CHARS", "4500"))
    max_chars = max_chars or int(os.getenv("BID_RETRIEVAL_MAX_CHARS", "52000"))
    pattern = re.compile("|".join(f"(?:{item})" for item in MODULE_PATTERNS[module]), re.IGNORECASE)

    section_texts = [_section_markdown(section) for section in sections]
    hit_indices = [idx for idx, text in enumerate(section_texts) if pattern.search(text)]

    if not hit_indices:
        return _fallback_sections(module, sections, max_chars=max_chars)

    selected_indices: list[int] = []
    for idx in hit_indices:
        start = max(0, idx - neighbor_sections)
        end = min(len(sections), idx + neighbor_sections + 1)
        for selected_idx in range(start, end):
            if selected_idx not in selected_indices:
                selected_indices.append(selected_idx)

    output: list[BidDocumentSection] = []
    used_chars = 0
    chunk_index = 1
    for idx in selected_indices:
        section = sections[idx]
        text = section_texts[idx]
        if not text.strip():
            continue

        if idx in hit_indices:
            chunks = _hit_windows(text, pattern, context_chars=context_chars)
        else:
            chunks = [text[: min(len(text), context_chars)]]

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining].rstrip()
            output.append(
                BidDocumentSection(
                    index=chunk_index,
                    title=f"{MODULE_LABELS[module]} - 原章节{section.index}: {section.title}",
                    level=section.level,
                    content=chunk,
                    markdown=f"## {MODULE_LABELS[module]} - 原章节{section.index}: {section.title}\n\n{chunk}",
                )
            )
            chunk_index += 1
            used_chars += len(chunk)
        if used_chars >= max_chars:
            break

    return output or _fallback_sections(module, sections, max_chars=max_chars)


def _section_markdown(section: BidDocumentSection) -> str:
    markdown = (section.markdown or "").strip()
    if markdown:
        return markdown
    title = (section.title or "").strip()
    content = (section.content or "").strip()
    return f"{title}\n\n{content}".strip()


def _hit_windows(text: str, pattern: re.Pattern[str], *, context_chars: int) -> list[str]:
    matches = list(pattern.finditer(text))
    if not matches:
        return [text[: min(len(text), context_chars)]]

    ranges: list[tuple[int, int]] = []
    half_window = max(1000, context_chars // 2)
    for match in matches:
        start = max(0, match.start() - half_window)
        end = min(len(text), match.end() + half_window)
        if ranges and start <= ranges[-1][1] + 500:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((start, end))

    chunks = []
    for start, end in ranges:
        prefix = "" if start == 0 else "... "
        suffix = "" if end >= len(text) else " ..."
        chunks.append(f"{prefix}{text[start:end].strip()}{suffix}")
    return chunks


def _fallback_sections(
    module: str,
    sections: Sequence[BidDocumentSection],
    *,
    max_chars: int,
) -> list[BidDocumentSection]:
    """Conservative fallback: keep the beginning plus scoring-like tail hits."""
    label = MODULE_LABELS.get(module, "候选片段")
    output: list[BidDocumentSection] = []
    used_chars = 0
    for idx, section in enumerate(sections[:8], start=1):
        text = _section_markdown(section).strip()
        if not text:
            continue
        remaining = max_chars - used_chars
        if remaining <= 0:
            break
        chunk = text[: min(len(text), remaining)].rstrip()
        output.append(
            BidDocumentSection(
                index=idx,
                title=f"{label} - 兜底原章节{section.index}: {section.title}",
                level=section.level,
                content=chunk,
                markdown=f"## {label} - 兜底原章节{section.index}: {section.title}\n\n{chunk}",
            )
        )
        used_chars += len(chunk)
    return output or list(sections)
