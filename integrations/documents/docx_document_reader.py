"""使用python-docx按正文顺序读取段落和表格，不猜测Word排版页码。"""

from io import BytesIO

from docx import Document
from docx.table import Table

from diagnostics.operation_logging import log_operation
from domain.documents.document_content_builder import DocumentContentBuilder
from domain.documents.document_reader_contract import DocumentReadError
from models.documents.document_content import DocumentContent, DocumentReadLimits


class DocxDocumentReader:
    """不需要本机安装Word；传入内存字节，返回正文段落与顶层表格行。"""

    @log_operation("document.read_docx")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """保留段落/表格位置；页眉页脚、图片OCR、批注及嵌套表格暂不展开。"""
        builder = DocumentContentBuilder(limits)
        try:
            with BytesIO(content) as source:
                document = Document(source)
                paragraph_number = 0
                table_number = 0
                # iter_inner_content保留段落和表格的交错顺序，不能先读完所有段落再读表格。
                for item in document.iter_inner_content():
                    if isinstance(item, Table):
                        table_number += 1
                        for row_number, row in enumerate(item.rows, start=1):
                            builder.count_cells(len(row.cells))
                            cells = tuple(cell.text for cell in row.cells)
                            builder.add(text="\t".join(cells), kind="table_row", location=f"正文表格{table_number}第{row_number}行", row_number=row_number, cells=cells)
                    else:
                        paragraph_number += 1
                        builder.add(text=item.text, kind="paragraph", location=f"正文第{paragraph_number}段")
        except Exception as error:
            if isinstance(error, DocumentReadError):
                raise
            raise DocumentReadError("document_unreadable", "Word正文无法读取，请检查DOCX结构是否完整。") from None
        return builder.finish(warnings=("仅读取正文段落和顶层表格；不提供Word页码，未展开页眉页脚、批注、图片及嵌套表格。",))
