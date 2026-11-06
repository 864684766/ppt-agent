"""PDF OCR接线验证；不是HTTP接口测试，不调用大语言模型。

test_read_scanned_pdf是真实本地OCR验证，生成无文字层PDF，不伪造识别结果。
其余测试用小型替身检查路由和错误传播，不重复测试第三方识别算法。
"""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
import pytest

from config.settings import PROJECT_ROOT
from domain.documents.document_reader_contract import DocumentReadError
from domain.ocr.image_text_recognizer_contract import OcrError
from integrations.documents.pdf_document_reader import PdfDocumentReader
from integrations.ocr.rapidocr_text_recognizer import RapidOcrTextRecognizer
from integrations.templates.pdfium_page_renderer import PdfiumPageRenderer
from models.documents.document_content import DocumentReadLimits
from models.ocr.ocr_result import OcrResult, OcrTextRegion
from models.templates.pdf_page_image import PdfPageImage, PdfRenderResult


def image_only_pdf() -> bytes:
    """生成两页PDF：第一页只有文字图片，第二页空白；原生提取均无文字。"""
    with Image.new("RGB", (900, 250), "white") as page:
        ImageDraw.Draw(page).text(
            (40, 65), "PDF OCR TEST 12345", fill="black", font=ImageFont.load_default(size=48),
        )
        with Image.new("RGB", (900, 250), "white") as blank, BytesIO() as buffer:
            page.save(buffer, format="PDF", save_all=True, append_images=[blank], resolution=144)
            return buffer.getvalue()


def test_read_scanned_pdf() -> None:
    """真实扫描件回退OCR，核对文字、原页码及空白页位置，供断点查看。"""
    reader = PdfDocumentReader(
        recognizer=RapidOcrTextRecognizer(model_directory=PROJECT_ROOT / "ocr-models"),
        renderer=PdfiumPageRenderer(),
    )
    result = reader.read(content=image_only_pdf(), limits=DocumentReadLimits())
    print("\n【PDF OCR读取结果】", result.model_dump_json(indent=2), flush=True)
    assert result.page_count == 2 and result.pages_without_text == (2,)
    assert len(result.blocks) == 1 and result.blocks[0].page == 1
    assert "PDFOCRTEST12345" in "".join(result.blocks[0].text.split()).upper()


def native_text_pdf() -> bytes:
    """构造包含Hello PDF文字层的最小PDF，无额外生成库或外部文件依赖。

    PDF对象偏移表根据实际字节计算，不能固定写死，否则解析器可能修复或拒绝。
    """
    stream = b"BT /F1 24 Tf 50 100 Td (Hello PDF) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(content)


def test_native_pdf_does_not_call_ocr() -> None:
    """文字层存在时不能初始化或调用OCR，即使未准备模型也应正常读取。"""
    class UnusedRecognizer:
        def recognize(self, *, image_bytes):
            raise AssertionError("有文字层页面不应调用OCR")

    class UnusedRenderer:
        def render(self, **kwargs):
            raise AssertionError("有文字层页面不应渲染")

    result = PdfDocumentReader(recognizer=UnusedRecognizer(), renderer=UnusedRenderer()).read(
        content=native_text_pdf(), limits=DocumentReadLimits(),
    )
    assert result.blocks[0].text == "Hello PDF" and result.blocks[0].page == 1
    assert result.warnings == ()


def test_ocr_obeys_content_limit_and_propagates_failure() -> None:
    """仅验证本项目组合逻辑：OCR文字超限、识别失败均不能伪装部分成功。"""
    class Renderer:
        def render(self, *, pdf_bytes, pages, dpi):
            return PdfRenderResult(
                pdf_sha256="test", total_pages=2, dpi=dpi,
                images=(PdfPageImage(page_number=pages[0], width_px=10, height_px=10, png_bytes=b"test"),),
            )

    class Recognizer:
        def recognize(self, *, image_bytes):
            return OcrResult(width_px=10, height_px=10, regions=(
                OcrTextRegion(text="too long", polygon_px=((0., 0.), (9., 0.), (9., 9.), (0., 9.)), confidence=0.9),
            ))

    class FailedRecognizer:
        def recognize(self, *, image_bytes):
            raise OcrError("本地OCR失败")

    reader = PdfDocumentReader(recognizer=Recognizer(), renderer=Renderer())
    with pytest.raises(DocumentReadError) as failure:
        reader.read(content=image_only_pdf(), limits=DocumentReadLimits(max_characters=3))
    assert failure.value.code == "document_limit_exceeded"
    reader = PdfDocumentReader(recognizer=FailedRecognizer(), renderer=Renderer())
    with pytest.raises(DocumentReadError) as failure:
        reader.read(content=image_only_pdf(), limits=DocumentReadLimits())
    assert failure.value.code == "document_ocr_failed"
