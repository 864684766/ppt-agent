"""把明确的页面设计方案绘制为可编辑PPTX对象。"""

from collections.abc import Mapping
import logging
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.presentation import Presentation as PresentationDocument
from pptx.slide import Slide
from pptx.util import Inches, Pt

from diagnostics.operation_logging import log_operation, safe_error_location
from domain.templates.template_page_creator_contract import TemplatePageCreationError
from integrations.templates.template_file_operations import TemplateFileError, load_template, save_new_template
from models.templates.create_template_page_contract import CreateTemplatePageOutput, PageElement

logger = logging.getLogger(__name__)


class LocalTemplatePageCreator:
    """使用宿主登记模板及指定版式创建一页；保留原文件，不调用模型。"""

    def __init__(self, *, templates: Mapping[str, Path], output_directory: Path) -> None:
        self._templates = {key: Path(path).resolve() for key, path in templates.items()}
        self._output_directory = Path(output_directory).resolve()

    @log_operation("template.create_page")
    def create(self, *, template_id: str, layout_id: str, background_color: str,
               elements: list[PageElement]) -> CreateTemplatePageOutput:
        """绘制元素并另存；页外对象或不支持的方案会明确失败。"""
        path = self._templates.get(template_id)
        if path is None:
            logger.warning("event=template_page_rejected reason=template_not_registered")
            raise TemplatePageCreationError("模板编号未登记。")
        try:
            presentation = load_template(path)
            logger.info("event=template_page_template_loaded slide_count=%d layout_count=%d",
                        len(presentation.slides), sum(len(master.slide_layouts) for master in presentation.slide_masters))
            layouts = {str(layout.part.partname): layout for master in presentation.slide_masters for layout in master.slide_layouts}
            layout = layouts.get(layout_id)
            if layout is None:
                logger.warning("event=template_page_rejected reason=layout_not_found")
                raise TemplatePageCreationError("版式不属于当前模板，请使用inspect_template结果。")
            _validate_elements(presentation, elements)
            logger.info("event=template_page_plan_validated element_count=%d text_count=%d rectangle_count=%d",
                        len(elements), sum(item.kind == "text" for item in elements),
                        sum(item.kind == "rectangle" for item in elements))
            # add_slide按所选版式建立新页面，版式自身的占位符可能出现在页面上。
            slide = presentation.slides.add_slide(layout)
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = RGBColor.from_string(background_color[1:])
            _draw_elements(slide, elements)
            output_id, file_name = save_new_template(presentation, self._output_directory)
        except TemplatePageCreationError:
            raise
        except TemplateFileError as error:
            raise TemplatePageCreationError(str(error)) from None
        except Exception as error:
            logger.error("event=template_page_creation_failed error_location=%s", safe_error_location(error))
            raise TemplatePageCreationError("创建页面失败，请检查模板及运行日志。") from None
        logger.info("event=template_page_created slide_number=%d element_count=%d", len(presentation.slides), len(elements))
        return {"template_id": template_id, "output_template_id": output_id, "file_name": file_name,
                "slide_number": len(presentation.slides), "element_count": len(elements),
                "warnings": ["版式可能包含占位符或母版装饰；背景为指定纯色，未自动识别模板风格。",
                             "文字溢出、遮挡、字体和视觉效果未验证，请实际打开核对。",
                             "新文件编号尚未自动登记，需由调用方登记。"]}


def _validate_elements(presentation: PresentationDocument, elements: list[PageElement]) -> None:
    """检查对象数量、页面边界及矩形和文字的组合限制。"""
    if not 1 <= len(elements) <= 30:
        logger.warning("event=template_page_rejected reason=element_count")
        raise TemplatePageCreationError("绘制方案需要1至30个对象。")
    # Inches把人易读的英寸转换为PPT内部EMU；检查整个对象是否在画布内。
    for index, element in enumerate(elements, start=1):
        if (Inches(element.x + element.width) > presentation.slide_width or
                Inches(element.y + element.height) > presentation.slide_height):
            logger.warning("event=template_page_rejected reason=element_out_of_bounds element_index=%d", index)
            raise TemplatePageCreationError("绘制对象超出幻灯片边界，请调整坐标和尺寸。")
        if element.kind == "rectangle" and element.text:
            logger.warning("event=template_page_rejected reason=rectangle_text element_index=%d", index)
            raise TemplatePageCreationError("矩形不接受文字，请单独创建文字框。")


def _draw_elements(slide: Slide, elements: list[PageElement]) -> None:
    """按方案顺序绘制矩形和文字框；调用方负责页面和文件生命周期。"""
    for index, element in enumerate(elements, start=1):
        logger.debug("event=template_page_element_draw element_index=%d kind=%s", index, element.kind)
        left, top = Inches(element.x), Inches(element.y)
        width, height = Inches(element.width), Inches(element.height)
        color = RGBColor.from_string(element.color[1:])
        if element.kind == "rectangle":
            shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
            shape.line.fill.background()
        else:
            shape = slide.shapes.add_textbox(left, top, width, height)
            # text_frame.paragraphs[0]是文字框自动创建的第一段文字。
            paragraph = shape.text_frame.paragraphs[0]
            paragraph.text = element.text
            paragraph.font.name = element.font_name
            paragraph.font.size = Pt(element.font_size)
            paragraph.font.color.rgb = color
            shape.text_frame.word_wrap = True
