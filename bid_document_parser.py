# 这个脚本负责把 PDF、Word 等招标文件解析成分章节内容。
# -*- coding: utf-8 -*-
import re
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from MinerU_pdf_parse_tool import mineru_parse_document


class BidDocumentSection(BaseModel):
    index: int = Field(description="Section order in the parsed bid document.")
    title: str = Field(description="Detected section title.")
    level: int = Field(description="Heading level. Smaller numbers are higher level.")
    content: str = Field(description="Section body without the heading line.")
    markdown: str = Field(description="Section heading and body in Markdown.")


MINERU_PARSE_METHODS = {"mineru_vlm", "mineru_pipeline", "mineru_html"}
LOCAL_PARSE_METHODS = {"pdfplumber", "docx2python"}
SUPPORTED_PARSE_METHODS = MINERU_PARSE_METHODS | LOCAL_PARSE_METHODS

MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CHINESE_CHAPTER_RE = re.compile(
    r"^\s*(第[一二三四五六七八九十百千万零〇\d]+[章节篇部分][\s、：:.-]*.+?)\s*$"
)
CHINESE_ORDER_RE = re.compile(r"^\s*([一二三四五六七八九十百千万零〇]+[、.．]\s*.+?)\s*$")
NUMBERED_HEADING_RE = re.compile(r"^\s*((?:\d+[.．、]){1,5}\s*.+?)\s*$")
PAREN_HEADING_RE = re.compile(r"^\s*([（(][一二三四五六七八九十百千万零〇\d]+[）)]\s*.+?)\s*$")


def parse_bid_document(
    document: str,
    output_dir: Optional[str] = None,
    parse_method: str = "mineru_vlm",
    model_version: Optional[str] = None,
    language: str = "ch",
    is_ocr: Optional[bool] = None,
    enable_formula: bool = True,
    enable_table: bool = True,
    page_ranges: Optional[str] = None,
    poll_interval: int = 5,
    timeout: int = 600,
) -> List[BidDocumentSection]:
    """Parse a bid document and split it into section objects."""
    markdown = parse_document_to_markdown(
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
    return split_bid_markdown_sections(markdown)


def parse_document_to_markdown(
    document: str,
    output_dir: Optional[str] = None,
    parse_method: str = "mineru_vlm",
    model_version: Optional[str] = None,
    language: str = "ch",
    is_ocr: Optional[bool] = None,
    enable_formula: bool = True,
    enable_table: bool = True,
    page_ranges: Optional[str] = None,
    poll_interval: int = 5,
    timeout: int = 600,
) -> str:
    """Parse a local/remote document to Markdown with MinerU or a local parser."""
    parse_method = parse_method or "mineru_vlm"
    if parse_method not in SUPPORTED_PARSE_METHODS:
        supported = ", ".join(sorted(SUPPORTED_PARSE_METHODS))
        raise ValueError(f"Unsupported parse_method: {parse_method}. Supported: {supported}")

    if parse_method in MINERU_PARSE_METHODS:
        mineru_model_version, mineru_is_ocr = _resolve_mineru_method(
            parse_method=parse_method,
            model_version=model_version,
            is_ocr=is_ocr,
        )
        mineru_enable_formula = enable_formula if mineru_model_version != "MinerU-HTML" else False
        mineru_enable_table = enable_table if mineru_model_version != "MinerU-HTML" else False
        return mineru_parse_document(
            document=document,
            output_dir=output_dir,
            model_version=mineru_model_version,
            language=language,
            is_ocr=mineru_is_ocr,
            enable_formula=mineru_enable_formula,
            enable_table=mineru_enable_table,
            page_ranges=page_ranges,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    if parse_method == "pdfplumber":
        return _parse_pdf_with_pdfplumber(document=document, page_ranges=page_ranges)
    if parse_method == "docx2python":
        return _parse_docx_with_docx2python(document=document)

    raise ValueError(f"Unsupported parse_method: {parse_method}")


def parse_bid_document_as_list(
    document: str,
    output_dir: Optional[str] = None,
    parse_method: str = "mineru_vlm",
    model_version: Optional[str] = None,
    language: str = "ch",
    is_ocr: Optional[bool] = None,
    enable_formula: bool = True,
    enable_table: bool = True,
    page_ranges: Optional[str] = None,
    poll_interval: int = 5,
    timeout: int = 600,
) -> List[dict]:
    """Parse a bid document and return plain dicts for JSON/API responses."""
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
    return [section.model_dump() for section in sections]


def split_bid_markdown_sections(markdown: str) -> List[BidDocumentSection]:
    """Split Markdown into chapter/section chunks."""
    lines = markdown.splitlines()
    heading_positions = []

    for line_number, line in enumerate(lines):
        heading = _detect_heading(line)
        if heading:
            level, title = heading
            heading_positions.append((line_number, level, title))

    if not heading_positions:
        content = markdown.strip()
        return [
            BidDocumentSection(
                index=1,
                title="全文",
                level=1,
                content=content,
                markdown=content,
            )
        ]

    sections: List[BidDocumentSection] = []
    preface = "\n".join(lines[: heading_positions[0][0]]).strip()
    if preface:
        sections.append(
            BidDocumentSection(
                index=1,
                title="前言",
                level=1,
                content=preface,
                markdown=preface,
            )
        )

    for idx, (start_line, level, title) in enumerate(heading_positions):
        end_line = (
            heading_positions[idx + 1][0]
            if idx + 1 < len(heading_positions)
            else len(lines)
        )
        chunk_lines = lines[start_line:end_line]
        markdown_chunk = "\n".join(chunk_lines).strip()
        content = "\n".join(chunk_lines[1:]).strip()
        sections.append(
            BidDocumentSection(
                index=len(sections) + 1,
                title=title.strip(),
                level=level,
                content=content,
                markdown=markdown_chunk,
            )
        )

    return sections


def _resolve_mineru_method(
    parse_method: str,
    model_version: Optional[str],
    is_ocr: Optional[bool],
) -> tuple[str, bool]:
    if parse_method == "mineru_pipeline":
        return model_version or "pipeline", bool(is_ocr) if is_ocr is not None else False
    if parse_method == "mineru_html":
        return "MinerU-HTML", False
    return model_version or "vlm", bool(is_ocr) if is_ocr is not None else False


def _parse_pdf_with_pdfplumber(document: str, page_ranges: Optional[str]) -> str:
    path = Path(document).expanduser().resolve()
    if path.suffix.lower() != ".pdf":
        raise ValueError("pdfplumber only supports local PDF files.")
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("Please install pdfplumber before using parse_method=pdfplumber.") from exc

    selected_pages = _parse_page_ranges(page_ranges)
    page_texts = []
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            if selected_pages and page_index not in selected_pages:
                continue
            text = page.extract_text() or ""
            page_texts.append(f"## 第 {page_index} 页\n{text.strip()}")
    return "\n\n".join(page_texts).strip()


def _parse_docx_with_docx2python(document: str) -> str:
    path = Path(document).expanduser().resolve()
    if path.suffix.lower() not in {".docx", ".doc"}:
        raise ValueError("docx2python only supports local Word files.")
    if not path.exists():
        raise FileNotFoundError(f"Word file not found: {path}")

    try:
        from docx2python import docx2python
    except ImportError as exc:
        raise RuntimeError("Please install docx2python before using parse_method=docx2python.") from exc

    with docx2python(path) as docx_content:
        return docx_content.text.strip()


def _parse_page_ranges(page_ranges: Optional[str]) -> set[int]:
    if not page_ranges:
        return set()

    pages: set[int] = set()
    for item in page_ranges.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start, end = item.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(item))
    return pages


def _detect_heading(line: str) -> Optional[tuple[int, str]]:
    stripped = line.strip()
    if not stripped:
        return None

    markdown_match = MARKDOWN_HEADING_RE.match(stripped)
    if markdown_match:
        return len(markdown_match.group(1)), markdown_match.group(2).strip()

    for pattern, level in (
        (CHINESE_CHAPTER_RE, 1),
        (CHINESE_ORDER_RE, 2),
        (NUMBERED_HEADING_RE, 2),
        (PAREN_HEADING_RE, 3),
    ):
        match = pattern.match(stripped)
        if match and _looks_like_heading(stripped):
            return level, match.group(1).strip()

    return None


def _looks_like_heading(text: str) -> bool:
    if len(text) > 80:
        return False
    if text.endswith(("。", "，", ",", "；", ";")):
        return False
    return True
