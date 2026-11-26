"""基于资料生成的分页大纲；不代表已生成PPT文件。"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class OutlineBullet(BaseModel):
    """一条待展示内容，引用本次资料汇总输入编号。"""

    content: str = Field(min_length=1, description="根据提供资料整理的页面要点，不能编造。")
    point_ids: list[str] = Field(min_length=1, description="支持本要点的资料输入编号；必须来自本次汇总。")


class OutlineSlide(BaseModel):
    """按列表顺序展示的一页；封面或结束页允许没有事实要点。"""

    role: Literal["cover", "content", "closing"] = Field(description="页面用途：封面、内容或结束页。")
    title: str = Field(min_length=1, description="该页的简短标题。")
    bullets: list[OutlineBullet] = Field(description="页面的事实要点；封面和结束页可为空。")

    @model_validator(mode="after")
    def validate_content(self) -> "OutlineSlide":
        """内容页必须有可追溯的内容，避免生成空页面。"""
        if self.role == "content" and not self.bullets:
            raise ValueError("内容页必须包含至少一个要点。")
        return self


class PresentationOutline(BaseModel):
    """供用户查看的PPT初稿；页数由slides列表长度决定。"""

    title: str = Field(min_length=1, description="整份PPT的大纲标题。")
    slides: list[OutlineSlide] = Field(min_length=1, max_length=50, description="按展示顺序排列的页面；不应为凑页数编造内容。")

    @model_validator(mode="after")
    def validate_slides(self) -> "PresentationOutline":
        """至少包含一页有事实依据的内容页。"""
        if not any(slide.role == "content" and slide.bullets for slide in self.slides):
            raise ValueError("大纲必须包含至少一页内容。")
        return self
