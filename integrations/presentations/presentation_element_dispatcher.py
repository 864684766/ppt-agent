"""根据元素类型分发给专一绘制模块，不负责模型决策。"""

import logging

from pptx.util import Inches

from domain.presentations.presentation_builder_contract import PresentationBuildError
from integrations.presentations.presentation_chart_drawing import draw_presentation_chart
from integrations.presentations.presentation_image_drawing import draw_presentation_image
from integrations.presentations.presentation_list_drawing import draw_presentation_list
from integrations.presentations.presentation_media_drawing import draw_presentation_media
from integrations.presentations.presentation_table_drawing import draw_presentation_table
from integrations.presentations.presentation_text_drawing import draw_presentation_text
from models.presentations.presentation_page_element import AudioElement, ChartElement, ImageElement, ListElement, TableElement, TextElement, VideoElement

logger = logging.getLogger(__name__)


def draw_page_elements(slide, elements, *, images: dict[str, bytes], videos: dict[str, bytes],
                       audios: dict[str, bytes], slide_width: int, slide_height: int) -> None:
    """按列表顺序添加对象；坐标越界或列表缩进无空间时明确拒绝。"""
    for index, element in enumerate(elements, start=1):
        if Inches(element.x + element.width) > slide_width or Inches(element.y + element.height) > slide_height:
            raise PresentationBuildError("新增元素超出页面边界，请调整坐标或尺寸。")
        logger.debug("event=presentation_element_draw element_index=%d kind=%s", index, element.type)
        if isinstance(element, TextElement):
            draw_presentation_text(slide, element)
        elif isinstance(element, ImageElement):
            draw_presentation_image(slide, element, images)
        elif isinstance(element, (VideoElement, AudioElement)):
            draw_presentation_media(slide, element, videos=videos, audios=audios, images=images)
        elif isinstance(element, ChartElement):
            draw_presentation_chart(slide, element)
        elif isinstance(element, TableElement):
            draw_presentation_table(slide, element)
        elif isinstance(element, ListElement):
            if any(item.level * 0.3 >= element.width for item in element.items):
                raise PresentationBuildError("列表宽度不足以容纳所选缩进。")
            draw_presentation_list(slide, element)
