"""文件提炼的内部模型；块编号只在本次文档解析结果内有效。"""

from typing import Literal

from pydantic import BaseModel, Field


class FileExtractionPoint(BaseModel):
    """一条针对问题的要点和可追溯的文件正文位置。"""

    content: str = Field(min_length=1, description="仅依据文件正文提炼的相关要点。")
    block_ids: list[str] = Field(min_length=1, description="支持该要点的正文块编号，必须来自本批输入。")


class FileExtractionBatch(BaseModel):
    """模型对一个正文批次的输出；空列表表示该批未提炼出相关要点。"""

    points: list[FileExtractionPoint] = Field(description="本批有关要点；没有时为空数组。")


class FileProcessingReport(BaseModel):
    """文件处理的客观报告，供上层判断；不是模型生成的资料内容。"""

    stage: Literal["validation", "reading", "extraction"] = Field(description="处理阶段：文件校验、读取或正文提炼。")
    code: str = Field(min_length=1, description="固定错误分类或 completed；不包含异常原文。")
    message: str = Field(min_length=1, description="供调用方理解的安全中文说明。")
    has_usable_content: bool = Field(description="是否已提炼出相关要点；不代表文件处理完成或事实已核验。")
    warnings: list[str] = Field(default_factory=list, description="文件读取限制或警告；没有时为空。")
    pages_without_text: list[int] = Field(default_factory=list, description="读取后仍无文字的页码；未成功读取时为空，并不代表页面均有文字。")


class FileExtraction(BaseModel):
    """单文件提炼结果；status 标明是否处理了全部解析正文。"""

    file_name: str = Field(min_length=1, description="调用方提供的文件名，仅用于本次区分来源，不是已登记的source_id。")
    points: list[FileExtractionPoint] = Field(description="各批次的相关要点；可能存在跨批重复，后续汇总时处理。")
    warnings: list[str] = Field(description="文件读取器返回的限制提示，不是模型结论。")
    pages_without_text: list[int] = Field(description="读取后仍无文字的页号，表示这些页未参与文字提炼。")
    status: Literal["completed", "interrupted", "failed"] = Field(description="completed已处理全部正文；interrupted提炼中断；failed文件未成功读取。")
    processed_characters: int = Field(ge=0, description="已成功处理的正文字符数，不是token数。")
    total_characters: int = Field(ge=0, description="读取器返回的正文字符总数，不含未读出的内容。")
    failure_reason: Literal["output_limit", "model_connection", "model_timeout", "model_output_invalid", "file_validation", "file_read", "processing_failed"] | None = Field(default=None, description="失败或中断原因；processing_failed为未分类的处理故障，成功时为null。")
    resume_id: str | None = Field(default=None, description="中断后本Agent实例中的恢复编号；完成时为null，进程重启后失效。")
    report: FileProcessingReport | None = Field(default=None, description="文件校验、读取和提炼的处理报告；旧调用方构造的样本可能为null。")
