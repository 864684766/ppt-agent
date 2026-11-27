"""对话接口的网页研究和可选文件解析结果。"""

from typing import Literal

from pydantic import BaseModel, Field

from models.documents.document_content import DocumentContent
from models.materials.material_summary import MaterialSummaryContent, MaterialInputPoint
from models.materials.request_analysis import RequestAnalysisResult
from models.outlines.presentation_outline import PresentationOutline


class ChatAttachmentResponse(BaseModel):
    """附件元数据与读取内容，不返回文件字节或不可查询的文件编号。"""

    file_name: str = Field(description="去除客户端目录的文件名，可作为本次响应的来源名称。")
    format: Literal["txt", "md", "pdf", "doc", "docx", "xlsx", "pptx"] = Field(description="通过校验后实际分派给读取器的格式。")
    size_bytes: int = Field(gt=0, description="原附件实际字节数，不是解析文字长度。")
    content: DocumentContent = Field(description="正文块、位置、页数及读取限制；无正文须结合warnings和pages_without_text判断。")


class ChatTemplateResponse(ChatAttachmentResponse):
    """OSS模板的真实下载及解析结果；与用户上传的参考附件分别返回。"""

    object_key: str = Field(description="实际读取的桶内完整对象标识，与请求template_key一致；不是公开URL。")


class ChatResearchSource(BaseModel):
    """一个已读取网页的公开来源信息，不包含网页正文。"""

    candidate_id: str = Field(description="本次网页候选编号，用于关联整理要点；不是资料库source_id。")
    title: str = Field(description="网页标题，可能为空。")
    url: str = Field(description="读取后最终网页地址，可能与请求地址因跳转不同。")
    truncated: bool = Field(description="本次提取正文是否被字符上限截断；不代表网页本身完整。")


class ChatQuestion(BaseModel):
    """等待用户决定的问题；回答接口将在后续任务实现。"""

    question_id: str = Field(description="当前问题编号；未来回答时须与任务对应。")
    question: str = Field(description="可展示的问题。")
    reason: str = Field(description="询问原因及已知资料缺口。")
    options: list[str] = Field(description="可选代码：provide_materials补充资料、use_current使用现有资料、end_conversation结束。")
    allow_free_text: bool = Field(description="是否允许自由文字回答；澄清需求时通常为true。")


class ChatReadResponse(BaseModel):
    """一轮资料收集与可选分页大纲。"""

    task_id: str = Field(description="本轮资料任务编号；可在当前服务进程内作为下一轮的previous_task_id使用。")
    previous_task_id: str | None = Field(default=None, description="本轮继承的上一轮任务编号；首轮为null。")
    message: str = Field(description="用户提交的原始问题。")
    template_key: str | None = Field(default=None, description="本次选择的OSS模板对象标识；未选择时为null。")
    status: Literal["completed", "awaiting_user", "interrupted"] = Field(description="completed已生成大纲；awaiting_user等待用户；interrupted处理未完成。")
    notice: str = Field(description="资料工作流状态说明。")
    analysis: RequestAnalysisResult | None = Field(description="需求分析结果；图故障前未产生时为null。")
    summary: MaterialSummaryContent | None = Field(description="跨来源汇总要点和内容问题；未完成时为null。")
    outline: PresentationOutline | None = Field(description="分页PPT大纲；中断时可能包含由已有要点编排的草稿，未产出时为null。")
    outline_error: Literal["model_timeout", "model_connection", "output_too_long", "generation_failed"] | None = Field(description="模型汇总或大纲生成失败分类；返回程序编排的草稿时仍保留失败分类。")
    summary_inputs: list[MaterialInputPoint] = Field(description="汇总输入要点及网页或文件块来源，供point_ids反查。")
    sources: list[ChatResearchSource] = Field(description="已读取网页的标题、地址与截断状态；没有网页时为空。")
    file_sources: dict[str, str] = Field(default_factory=dict, description="文件来源编号到文件名的映射，包含本轮与沿用的文件；用于结合block_ids定位引用。")
    report: dict | None = Field(description="网页、文件阶段报告及有效来源数量和内容问题；需求分析阶段结束时可能为null。")
    waiting_question: ChatQuestion | None = Field(description="需要澄清或补充资料时的问题；其他情况为null。")
    attachment_analyzed: bool = Field(description="文件提炼已完成时为true；存在附件不代表一定分析完成。")
    attachment_file_name: str | None = Field(description="本次上传文件名，未上传时为null；跨轮引用使用file_sources。")
    template: ChatTemplateResponse | None = Field(default=None, description="选中OSS模板的解析结果；未选择时为null。")


class ChatErrorDetail(BaseModel):
    """API选择的公开错误，不回显上传正文或解析器异常。"""

    code: str = Field(description="固定错误分类，如invalid_fields、invalid_file、document_unreadable或document_limit_exceeded。")
    message: str = Field(description="可供用户理解的安全中文提示。")


class ChatErrorResponse(BaseModel):
    """请求接收、文件读取或网页研究失败时的安全错误。"""

    detail: ChatErrorDetail = Field(description="错误分类及提示；HTTP状态说明请求失败性质。")
