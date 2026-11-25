"""对话接口的网页研究和可选文件解析结果。"""

from typing import Literal

from pydantic import BaseModel, Field

from models.documents.document_content import DocumentContent
from models.web.research_report import ResearchReport
from models.web.web_research_summary import WebResearchSummary, WebSummaryPoint


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


class ChatPageExtraction(BaseModel):
    """一篇网页的单页要点；汇总未完成时可查看已提炼内容。"""

    candidate_id: str = Field(description="网页候选编号。")
    title: str = Field(description="网页标题。")
    url: str = Field(description="最终网页地址。")
    truncated: bool = Field(description="单页模型读取的正文是否被截断。")
    points: list[WebSummaryPoint] = Field(description="仅依据本页正文提炼的要点；无要点为空列表。")


class ChatQuestion(BaseModel):
    """等待用户决定的问题；回答接口将在后续任务实现。"""

    question_id: str = Field(description="当前问题编号；未来回答时须与任务对应。")
    question: str = Field(description="可展示的问题。")
    reason: str = Field(description="询问原因及已知资料缺口。")
    options: list[str] = Field(description="可选代码：provide_materials补充资料、use_current使用现有资料、end_conversation结束。")
    allow_free_text: bool = Field(description="是否允许自由文字回答；本阶段的选择题为false。")


class ChatResearchResult(BaseModel):
    """网页资料研究的公开结果，不表示已生成大纲或核实事实。"""

    summary: WebResearchSummary | None = Field(description="最后一次成功的网页要点汇总；尚无汇总时为null，汇总中断时可能不含最新要点。")
    sources: list[ChatResearchSource] = Field(description="已读取网页的来源信息，可用候选编号关联要点。")
    page_extractions: list[ChatPageExtraction] = Field(description="逐页提炼结果；保留来源及截断状态。")
    report: ResearchReport = Field(description="资料检查报告；包含数量、问题和停止原因，不包含内部搜索反馈。")
    waiting_question: ChatQuestion | None = Field(description="资料不足时的问题；正常完成或执行中断时为null。")


class ChatReadResponse(BaseModel):
    """返回网页研究和可选文件读取结果；暂不整合附件内容。"""

    task_id: str = Field(description="本次网页研究任务编号；暂停状态仅存在当前服务进程内。")
    message: str = Field(description="用户问题；已用于网页资料研究。")
    template_key: str | None = Field(default=None, description="本次选择的OSS模板对象标识；未选择时为null。")
    status: Literal["completed", "awaiting_user", "interrupted"] = Field(description="completed资料达到当前收集条件；awaiting_user等待选择；interrupted模型检查未完成。")
    notice: str = Field(description="本次网页资料研究状态说明。")
    model_called: Literal[True] = Field(default=True, description="网页资料流程已调用模型；不代表附件已交给模型。")
    retained: Literal[False] = Field(default=False, description="上传附件及模板文件字节不跨请求保存；网页工作流检查点暂保存在服务进程内。")
    attachment_analyzed: Literal[False] = Field(default=False, description="当前阶段附件仅完成解析，尚未参与模型分析或与网页资料整合。")
    attachment: ChatAttachmentResponse | None = Field(default=None, description="上传附件的解析结果；未上传时为null。")
    template: ChatTemplateResponse | None = Field(default=None, description="选中OSS模板的解析结果；未选择时为null。")
    research: ChatResearchResult = Field(description="网页要点、来源、检查报告和待回答问题。")


class ChatErrorDetail(BaseModel):
    """API选择的公开错误，不回显上传正文或解析器异常。"""

    code: str = Field(description="固定错误分类，如invalid_fields、invalid_file、document_unreadable或document_limit_exceeded。")
    message: str = Field(description="可供用户理解的安全中文提示。")


class ChatErrorResponse(BaseModel):
    """请求接收、文件读取或网页研究失败时的安全错误。"""

    detail: ChatErrorDetail = Field(description="错误分类及提示；HTTP状态说明请求失败性质。")
