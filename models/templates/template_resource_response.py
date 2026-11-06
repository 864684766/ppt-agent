"""模板资源列表公开数据；不包含凭据、签名链接或模板正文。"""

from datetime import datetime
from pydantic import BaseModel, Field


class TemplateResourceItem(BaseModel):
    """桶中的一个PPTX对象；尚未验证其实际内容、版式或兼容性。"""

    object_key: str = Field(description="桶内完整对象标识，如business/蓝色模板.pptx；后续选择模板应保留完整值，不能只用文件名。")
    file_name: str = Field(description="对象标识最后一段，供列表展示；不同目录允许重名，不是唯一ID。")
    size_bytes: int = Field(ge=0, description="S3返回的对象大小，单位字节；不是页数或读取内容长度。")
    last_modified: datetime | None = Field(default=None, description="S3返回的最后修改时间（通常为UTC），缺失为null；不是本系统上传时间。")


class TemplateResourceListResponse(BaseModel):
    """一页对象扫描中的PPTX候选；空items不一定代表桶中没有PPTX。"""

    bucket: str = Field(description="宿主配置的模板桶名，不由客户端任意选择。")
    items: list[TemplateResourceItem] = Field(description="本页扫描后按.pptx后缀筛选出的候选，不证明文件可打开；不含文件夹或其他格式。")
    returned_count: int = Field(ge=0, description="本页实际返回的PPTX数量，等于items长度；不是桶中模板总数。")
    scanned_count: int = Field(ge=0, description="S3本页扫描到的全部对象数量，包含其他格式；最多max_keys个。")
    is_truncated: bool = Field(description="S3是否还有下一页对象；true时即使items为空也应继续翻页。")
    next_continuation_token: str | None = Field(default=None, description="下一页不透明游标，原样作为continuation_token传回；末页null，不解析或自行生成。")


class TemplateResourceErrorDetail(BaseModel):
    """公开安全错误，禁止返回SDK原始异常。"""

    code: str = Field(description="稳定分类，如storage_access_denied、storage_unavailable、storage_configuration_invalid。")
    message: str = Field(description="面向使用者的中文安全提示，不含凭据或服务端原文。")


class TemplateResourceErrorResponse(BaseModel):
    """响应开始前失败的JSON错误。"""

    detail: TemplateResourceErrorDetail = Field(description="错误分类与提示。")
