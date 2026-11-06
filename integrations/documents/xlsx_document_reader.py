"""使用openpyxl只读工作表行，保留原始公式，不执行Excel计算。"""

from datetime import date, datetime, time
from io import BytesIO

from openpyxl import load_workbook

from diagnostics.operation_logging import log_operation
from domain.documents.document_content_builder import DocumentContentBuilder
from domain.documents.document_reader_contract import DocumentReadError
from models.documents.document_content import DocumentContent, DocumentReadLimits


class XlsxDocumentReader:
    """按工作簿顺序读取所有工作表（含隐藏表），明确提示而不丢弃隐藏数据。"""

    @log_operation("document.read_xlsx")
    def read(self, *, content: bytes, limits: DocumentReadLimits) -> DocumentContent:
        """返回带表名和行号的行块；空行仍计入遍历规模，不无限扫描空区域。"""
        builder = DocumentContentBuilder(limits)
        workbook = None
        formula_count = 0
        hidden = False
        try:
            with BytesIO(content) as source:
                workbook = load_workbook(source, read_only=True, data_only=False, keep_links=False)
                try:
                    for sheet in workbook.worksheets:
                        hidden = hidden or sheet.sheet_state != "visible"
                        for row_number, row in enumerate(sheet.iter_rows(), start=1):
                            builder.count_cells(len(row))
                            values = []
                            for cell in row:
                                formula_count += cell.data_type == "f"
                                value = cell.value
                                if value is None:
                                    values.append("")
                                elif isinstance(value, (date, datetime, time)):
                                    values.append(value.isoformat())
                                else:
                                    values.append(str(value))
                            cells = tuple(values)
                            builder.add(text="\t".join(cells), kind="sheet_row", location=f"工作表{sheet.title}第{row_number}行", sheet_name=sheet.title, row_number=row_number, cells=cells)
                finally:
                    workbook.close()
        except Exception as error:
            if isinstance(error, DocumentReadError):
                raise
            raise DocumentReadError("document_unreadable", "Excel工作表无法读取，请检查XLSX结构是否完整。") from None
        warnings = ["仅读取工作表单元格；不读取图表图片、批注、样式或执行外部链接。"]
        if formula_count:
            warnings.append("公式以原始公式文本返回，未计算公式或读取其缓存结果。")
        if hidden:
            warnings.append("结果包含隐藏工作表，请结合用途决定是否采用。")
        return builder.finish(warnings=tuple(warnings))
