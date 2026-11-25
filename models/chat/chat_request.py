"""对话接收消息、可选参考附件和OSS模板标识。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ChatRequest(BaseModel):
    """接收消息及可选模板标识；文件通过multipart单独上传。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=10000, description="用户问题，1–10000字符；用于需求分析和资料整理。")
    template_key: Annotated[str, StringConstraints(strip_whitespace=False)] | None = Field(
        default=None, min_length=1, max_length=1024,
        description="从模板列表object_key原样回填，如公司模板.pptx或business/模板.pptx；不是URL，不做URL编码。默认null不读取模板；指定时从服务端配置桶下载并解析PPTX；模板内容暂不参与网页资料分析。",
    )


class ChatAttachmentInput(BaseModel):
    """HTTP接收后形成的内部附件，不从JSON接口直接接受此结构。"""

    model_config = ConfigDict(frozen=True, extra="forbid")
    file_name: str = Field(description="通过名称检查、已去除客户端目录的文件名。")
    format: Literal["txt", "md", "pdf", "doc", "docx", "xlsx", "pptx"] = Field(description="扩展名与声明MIME初检后的规范化格式；实际字节仍需内容校验。")
    content: bytes = Field(repr=False, exclude=True, description="接收层取得的文件字节；供资料工作流使用，不进入JSON或日志，检查点仅在服务进程内保留。")


class ChatSubmission(ChatRequest):
    """接收层内部结果：消息加可选附件；不是对外JSON请求契约。"""

    attachment: ChatAttachmentInput | None = Field(default=None, description="接收层从multipart文件创建；JSON请求仅接受message/template_key，不能伪造附件对象。")
