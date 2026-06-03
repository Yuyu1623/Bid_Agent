# 这个脚本负责提供招标文件解析和分析的 FastAPI 后端接口。
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bid_analysis_service import BidAnalysisResult, analyze_bid_document
from bid_document_parser import BidDocumentSection, parse_bid_document


app = FastAPI(title="Plan-and-Solve Bid Document Parser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseDocumentRequest(BaseModel):
    document: str = Field(description="Local file path or remote document URL.")
    output_dir: Optional[str] = Field(default=None)
    parse_method: str = Field(default="mineru_vlm")
    model_version: str = Field(default="vlm")
    llm_vendor: str = Field(default="siliconflow")
    llm_model: Optional[str] = Field(default=None)
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


@app.post("/bid-documents/parse", response_model=ParseDocumentResponse)
def parse_document(request: ParseDocumentRequest) -> ParseDocumentResponse:
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

    return ParseDocumentResponse(sections=sections)


@app.post("/bid-documents/analyze", response_model=AnalyzeDocumentResponse)
def analyze_document(request: ParseDocumentRequest) -> AnalyzeDocumentResponse:
    result = analyze_bid_document(
        document=request.document,
        output_dir=request.output_dir,
        parse_method=request.parse_method,
        model_version=request.model_version,
        llm_vendor=request.llm_vendor,
        llm_model=request.llm_model,
        language=request.language,
        is_ocr=request.is_ocr,
        enable_formula=request.enable_formula,
        enable_table=request.enable_table,
        page_ranges=request.page_ranges,
        poll_interval=request.poll_interval,
        timeout=request.timeout,
    )
    return AnalyzeDocumentResponse(**result.model_dump())


@app.post("/bid-documents/upload-analyze", response_model=AnalyzeDocumentResponse)
def upload_and_analyze_document(
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
) -> AnalyzeDocumentResponse:
    suffix = Path(file.filename or "document").suffix
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / f"upload{suffix}"
        with temp_path.open("wb") as file_obj:
            file_obj.write(file.file.read())

        result = analyze_bid_document(
            document=str(temp_path),
            output_dir=output_dir,
            parse_method=parse_method,
            model_version=model_version,
            llm_vendor=llm_vendor,
            llm_model=llm_model,
            language=language,
            is_ocr=is_ocr,
            enable_formula=enable_formula,
            enable_table=enable_table,
            page_ranges=page_ranges,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    return AnalyzeDocumentResponse(**result.model_dump())
