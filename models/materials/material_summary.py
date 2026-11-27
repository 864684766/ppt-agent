"""跨网页和文件的内部汇总契约；编号均只在调用方本次输入中有效。"""

from typing import Literal
from pydantic import BaseModel, Field
from models.outlines.presentation_outline import PresentationOutline


class MaterialReference(BaseModel):
    """一个网页或文件正文位置；文件块编号必须与所属文件一起使用。"""

    kind: Literal["web", "file"] = Field(description="来源类型：web网页或file文件。")
    source_id: str = Field(min_length=1, description="调用方本次分配的来源标识；网页可用candidate_id，不代表资料库登记。")
    block_ids: list[str] = Field(default_factory=list, description="文件原文块编号；网页为空。")


class MaterialInputPoint(BaseModel):
    """单条已提炼要点；来源由外层从实际提炼结果构造。"""

    point_id: str = Field(min_length=1, description="本次汇总内唯一要点编号，由调用方生成。")
    content: str = Field(min_length=1, description="依据来源提炼的内容，可能不完整或未经事实核验。")
    references: list[MaterialReference] = Field(min_length=1, description="本条要点的实际来源位置。")


class MaterialMergedPoint(BaseModel):
    """模型合并后的一条内容，以输入要点编号关联来源。"""

    content: str = Field(min_length=1, description="仅根据输入要点合并出的内容。")
    point_ids: list[str] = Field(min_length=1, description="支持该内容的输入要点编号；不能编造。")


class MaterialSummaryIssue(BaseModel):
    """输入中可见的问题；整体缺口允许没有关联要点。"""

    type: Literal["content_gap", "source_conflict", "version_issue", "source_requirement"] = Field(description="内容缺口、来源冲突、版本问题或来源要求。")
    message: str = Field(min_length=1, description="问题及需要补充或核实的内容。")
    point_ids: list[str] = Field(description="涉及的输入要点编号；整体缺口可为空。")


class MaterialSummaryContent(BaseModel):
    """资料汇总的公共内容；编号可关联本次输入，不代表事实核验。"""

    points: list[MaterialMergedPoint] = Field(description="合并后的要点；无相关内容为空。")
    issues: list[MaterialSummaryIssue] = Field(description="基于输入要点发现的问题；无问题为空。")

    def references_for(self, point: MaterialMergedPoint, inputs: list[MaterialInputPoint]) -> list[MaterialReference]:
        """由输入编号还原真实来源，去除完全重复的来源位置。"""
        lookup = {item.point_id: item for item in inputs}
        references: list[MaterialReference] = []
        seen = set()
        for point_id in point.point_ids:
            if point_id not in lookup:
                raise ValueError("汇总要点引用了不存在的输入编号。")
            for ref in lookup[point_id].references:
                key = (ref.kind, ref.source_id, tuple(ref.block_ids))
                if key not in seen:
                    seen.add(key)
                    references.append(ref)
        return references


class MaterialSummary(MaterialSummaryContent):
    """模型返回的汇总及可选大纲；中间汇总不生成大纲。"""

    outline: PresentationOutline | None = Field(default=None, description="最终汇总时生成的分页大纲；中间汇总或资料不足时为null。")


class MaterialOutlineSection(BaseModel):
    """模型为内容页选择标题和要点，程序从已提炼资料填入正文。"""

    title: str = Field(min_length=1, description="概括这页要点的简短标题。")
    keys: list[str] = Field(min_length=1, description="本页按顺序使用的条目编号，如k1。")


class MaterialOutlineDraft(MaterialSummaryContent):
    """最终模型输出。生成大纲时，公开汇总要点由程序从大纲构造。"""

    points: list[MaterialMergedPoint] = Field(default_factory=list, description="仅在无法生成大纲时返回可用的精简要点。")
    title: str = Field(default="", description="大纲标题，未生成时为空。")
    sections: list[MaterialOutlineSection] = Field(default_factory=list, max_length=50, description="按展示顺序组织的内容页，未生成时为空。")
