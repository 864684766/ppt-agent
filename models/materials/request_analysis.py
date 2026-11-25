"""需求分析内部结果；计划由模型提出，执行前仍须由调用方检查用户授权。"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class RequestAnalysis(BaseModel):
    """资料来源和顺序建议；不是工具调用或已经执行的工作流。"""

    source_mode: Literal["file", "web", "both", "undetermined"] = Field(description="建议使用文件、网页、两者，或尚不能确定。")
    execution_order: Literal["single", "parallel", "file_then_web", "undetermined"] = Field(description="单一来源、两者并行、先文件后网页或尚不能确定。")
    needs_clarification: bool = Field(description="是否缺少开始处理所必需的信息。")
    clarification: str | None = Field(description="需要用户回答的问题；不需要询问时为null。")
    reason: str = Field(min_length=1, max_length=500, description="对计划或询问的简短解释，不包含模型推理过程。")

    @model_validator(mode="after")
    def validate_plan(self) -> "RequestAnalysis":
        """拒绝前后矛盾的计划；不会因此证明模型理解正确。"""
        valid = {"file": {"single"}, "web": {"single"}, "both": {"parallel", "file_then_web"},
                 "undetermined": {"undetermined"}}
        if self.execution_order not in valid[self.source_mode]:
            raise ValueError("资料来源与执行顺序不匹配。")
        if self.needs_clarification != bool(self.clarification and self.clarification.strip()):
            raise ValueError("询问标记与询问内容不一致。")
        if self.source_mode == "undetermined" and not self.needs_clarification:
            raise ValueError("来源未确定时必须询问。")
        return self


class RequestAnalysisResult(BaseModel):
    """分析调用的内部结果；失败时无计划，不能继续执行资料分支。"""

    status: Literal["completed", "failed"] = Field(description="completed表示计划有效；failed表示分析未完成。")
    plan: RequestAnalysis | None = Field(description="成功的计划；失败时为null。")
    error_code: Literal["invalid_input", "model_timeout", "model_connection", "invalid_plan", "analysis_failed"] | None = Field(description="失败分类；成功时为null。")
    message: str = Field(min_length=1, description="安全中文提示，不包含原始异常或用户数据。")
