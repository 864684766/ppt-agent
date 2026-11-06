"""当前对话统一JSON：分别返回上传参考附件与选中OSS模板的读取结果，无文件时仅确认消息。"""

from typing import Literal

from pydantic import BaseModel, Field

from models.documents.document_content import DocumentContent


class ChatAttachmentResponse(BaseModel):
    """附件元数据与读取内容，不返回文件字节或不可查询的文件编号。"""

    file_name: str = Field(description="去除客户端目录的文件名，可作为本次响应的来源名称。")
    format: Literal["txt", "md", "pdf", "docx", "xlsx", "pptx"] = Field(description="通过校验后实际分派给读取器的格式。")
    size_bytes: int = Field(gt=0, description="原附件实际字节数，不是解析文字长度。")
    content: DocumentContent = Field(description="正文块、位置、页数及读取限制；无正文须结合warnings和pages_without_text判断。")


class ChatTemplateResponse(ChatAttachmentResponse):
    """OSS模板的真实下载及解析结果；与用户上传的参考附件分别返回。"""

    object_key: str = Field(description="实际读取的桶内完整对象标识，与请求template_key一致；不是公开URL。")


class ChatReadResponse(BaseModel):
    """不调用模型；分别返回上传附件和OSS模板的实际读取结果。"""

    message: str = Field(description="本次用户问题，回显供核对；未交模型分析。")
    template_key: str | None = Field(default=None, description="本次请求的OSS模板对象标识；未指定时null，读取失败整个请求返回错误，不伪造成功。")
    status: Literal["attachment_read", "template_read", "files_read", "message_received"] = Field(
        default="message_received", description="attachment_read仅上传附件已读；template_read仅OSS模板已读；files_read两者都已读；message_received未指定任何文件。均不表示OCR/AI分析完成。",
    )
    model_called: Literal[False] = Field(default=False, description="固定false，当前整个对话接口都不会创建或调用模型。")
    retained: Literal[False] = Field(default=False, description="固定false，不提供附件/正文的跨请求缓存或后续取回接口。")
    attachment: ChatAttachmentResponse | None = Field(default=None, description="单个附件及其读取内容；没有上传时null，每次最多一个。")

    template: ChatTemplateResponse | None = Field(default=None, description="OSS模板下载和PPTX文字解析结果；未指定template_key时null，不是生成后的PPT。")


class ChatErrorDetail(BaseModel):
    """API选择的公开错误，不回显上传正文或解析器异常。"""

    code: str = Field(description="固定错误分类，如invalid_fields、invalid_file、document_unreadable或document_limit_exceeded。")
    message: str = Field(description="可供用户理解的安全中文提示。")


class ChatErrorResponse(BaseModel):
    """请求接收、上传附件或OSS模板下载/解析失败时使用；当前没有SSE或AI调用。"""

    detail: ChatErrorDetail = Field(description="错误分类及提示；HTTP状态说明请求失败性质。")
