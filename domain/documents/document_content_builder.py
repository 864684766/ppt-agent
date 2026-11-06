"""统一控制正文输出和遍历规模，供各格式读取器复用。"""

from typing import Literal

from domain.documents.document_reader_contract import DocumentReadError
from models.documents.document_content import DocumentBlock, DocumentContent, DocumentReadLimits


class DocumentContentBuilder:
    """每次read创建一个实例；非全局Store，完成后返回不可变内容快照。"""

    def __init__(self, limits: DocumentReadLimits) -> None:
        self._limits = limits
        self._blocks: list[DocumentBlock] = []
        self._characters = 0
        self._units = 0
        self._cells = 0

    def count_cells(self, count: int) -> None:
        """在读取一行前检查单元格量，空单元格也计入资源上限。"""
        self._cells += count
        if self._cells > self._limits.max_cells:
            raise DocumentReadError("document_limit_exceeded", "表格单元格数量超过DOCUMENT_MAX_CELLS限制。")

    def add(
        self, *, text: str, kind: Literal["text", "page", "paragraph", "table_row", "sheet_row", "slide_text"],
        location: str, page: int | None = None, sheet_name: str | None = None,
        row_number: int | None = None, cells: tuple[str, ...] = (),
    ) -> None:
        """检查一个单元并收集非空正文；调用方显式传kind/location等位置字段。

        即使text为空也计数，防止扫描巨量空行。没有文字则不创建空内容块。
        不截断超限文本，避免用户误以为已获得完整读取结果。
        """
        self._units += 1
        if self._units > self._limits.max_blocks:
            raise DocumentReadError("document_limit_exceeded", "读取单元数量超过DOCUMENT_MAX_BLOCKS限制。")
        if not text.strip():
            return
        self._characters += len(text)
        if self._characters > self._limits.max_characters:
            raise DocumentReadError("document_limit_exceeded", "读取文字超过DOCUMENT_MAX_CHARACTERS限制。")
        # 只有非空正文分配编号；例如b000001只是本次读取的第一个块，
        # 不能用它从另一个请求找回文档，也不能将其当作全局来源ID。
        self._blocks.append(DocumentBlock(
            block_id=f"b{len(self._blocks) + 1:06d}",
            text=text, kind=kind, location=location, page=page,
            sheet_name=sheet_name, row_number=row_number, cells=cells,
        ))

    def finish(self, *, page_count: int | None = None, pages_without_text: tuple[int, ...] = (), warnings: tuple[str, ...] = ()) -> DocumentContent:
        """创建结果；page_count、无文字页和warnings由实际读取器提供。"""
        if not self._blocks:
            warnings = (*warnings, "未提取到可读正文；请检查空白、图片内容或读取器的能力范围。")
        return DocumentContent(blocks=tuple(self._blocks), page_count=page_count, pages_without_text=pages_without_text, warnings=warnings)
