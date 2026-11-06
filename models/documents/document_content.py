"""读取器统一输出：正文、可验证位置及限制，不包含文件句柄或模型对象。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentBlock(BaseModel):
    """一个可引用的内容块；无可靠页码时使用None，不根据排版猜页码。"""

    model_config = ConfigDict(frozen=True, extra="forbid")
    block_id: str = Field(min_length=1, description="本次读取内的块编号，如b000001；不是跨版本稳定编号或全局source_id。")
    kind: Literal["text", "page", "paragraph", "table_row", "sheet_row", "slide_text"] = Field(description="块类型：纯文本、PDF页、Word段落、表格行、Excel行或PPT文字。")
    text: str = Field(min_length=1, description="原生提取或本地OCR识别的文字，OCR可能错漏；表格行使用制表符分隔单元格；不含大语言模型补写。")
    location: str = Field(min_length=1, description="原文位置说明，如第2页、正文第3段、工作表销售第5行；不是猜测的Word页码。")
    page: int | None = Field(default=None, ge=1, description="PDF页码或PPT幻灯片序号，从1开始；Word/Excel/普通文本为null。")
    sheet_name: str | None = Field(default=None, description="Excel原工作表名称，其他格式为null。")
    row_number: int | None = Field(default=None, ge=1, description="原表格或工作表行号，从1开始；非行数据为null。")
    cells: tuple[str, ...] = Field(default=(), description="表格行的单元格文本，按列顺序保留空单元格；非表格块为空列表。公式保留公式文本，不计算。")


class DocumentContent(BaseModel):
    """读取完成的内容及限制；无文字页面不会被伪装成已有OCR结果。"""

    model_config = ConfigDict(frozen=True, extra="forbid")
    blocks: tuple[DocumentBlock, ...] = Field(description="按读取顺序返回的正文块；可能为空，须结合warnings判断。")
    page_count: int | None = Field(default=None, ge=0, description="PDF总页数或PPT实际页数；Word/Excel无法可靠得出页数时为null。")
    pages_without_text: tuple[int, ...] = Field(default=(), description="本次读取后仍无文字的PDF/PPT页序号；PDF启用OCR时为OCR后仍无文字，PPT仅原生提取；不等于已确认扫描件。")
    warnings: tuple[str, ...] = Field(default=(), description="固定限制与读取提示；不是正文或模型推理，不代表全文所有元素均已提取。")


class DocumentReadLimits(BaseModel):
    """宿主注入的单文件读取上限；不在读取器中访问Settings。"""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_characters: int = Field(default=200000, ge=1, le=2000000, description="所有块text字符数之和上限，不是字节数；超限失败，不截断。")
    max_blocks: int = Field(default=5000, ge=1, le=20000, description="检查的段落/行/页等单元数上限，包含空单元。")
    max_cells: int = Field(default=100000, ge=1, le=1000000, description="累计访问的表格单元格数上限，包含空单元格。")
