"""读取实际幻灯片的文字和表格；不把母版提示文字混入业务正文。"""

from io import BytesIO

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from diagnostics.operation_logging import log_operation
from domain.documents.document_content_builder import DocumentContentBuilder
from domain.documents.document_reader_contract import DocumentReadError
from models.documents.document_content import DocumentContent, DocumentReadLimits


class PptxDocumentReader:
    """PPTX内容读取与模板结构检查是不同能力；不渲染、不识别图片或修改模板。"""

    @log_operation("document.read_pptx")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """递归读取组合内文字；按形状存储顺序返回，不宣称等于视觉阅读顺序。"""
        builder = DocumentContentBuilder(limits)
        missing = []
        try:
            with BytesIO(content) as source:
                presentation = Presentation(source)
                count = len(presentation.slides)
                if count > limits.max_blocks:
                    raise DocumentReadError("document_limit_exceeded", "PPT页数超过DOCUMENT_MAX_BLOCKS限制。")
                for page_number, slide in enumerate(presentation.slides, start=1):
                    visible_text = False
                    # 空页也计入遍历量；下方形状和表格行另计，限制总工作量。
                    builder.add(text="", kind="slide_text", location=f"第{page_number}页", page=page_number)
                    for index, shape in enumerate(slide.shapes, start=1):
                        visible_text = self._read_shape(builder, shape, page_number, f"形状{index}") or visible_text
                    if not visible_text:
                        missing.append(page_number)
        except Exception as error:
            if isinstance(error, DocumentReadError):
                raise
            raise DocumentReadError("document_unreadable", "PPT实际页面无法读取，请检查PPTX结构是否完整。") from None
        return builder.finish(page_count=count, pages_without_text=tuple(missing), warnings=("仅读取实际幻灯片的文字/表格（含组合）；未读取备注、图片OCR、图表数据、SmartArt或分析母版/模板角色。",))

    def _read_shape(self, builder: DocumentContentBuilder, shape, page: int, position: str) -> bool:
        """位置用于定位原形状；递归组合不猜绝对坐标，也不读取母版默认文字。"""
        location = f"第{page}页/{position}"
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            builder.add(text="", kind="slide_text", location=location, page=page)
            found = False
            for index, child in enumerate(shape.shapes, start=1):
                found = self._read_shape(builder, child, page, f"{position}/子形状{index}") or found
            return found
        if shape.has_table:
            found = False
            for row_number, row in enumerate(shape.table.rows, start=1):
                builder.count_cells(len(row.cells))
                cells = tuple(cell.text for cell in row.cells)
                text = "\t".join(cells)
                builder.add(text=text, kind="table_row", location=f"{location}/第{row_number}行", page=page, row_number=row_number, cells=cells)
                found = found or bool(text.strip())
            return found
        text = shape.text if shape.has_text_frame else ""
        builder.add(text=text, kind="slide_text", location=location, page=page)
        return bool(text.strip())
