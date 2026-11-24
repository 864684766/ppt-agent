"""按已确认的页面计划生成PPTX；不决定大纲、不做成品质检。"""

from collections.abc import Mapping
import logging
from pathlib import Path

from pptx.presentation import Presentation as PresentationDocument
from pptx.slide import Slide

from diagnostics.operation_logging import log_operation, safe_error_location
from domain.presentations.presentation_builder_contract import PresentationBuildError
from domain.templates.template_completer_contract import TemplateCompletionError
from integrations.presentations.presentation_text_writer import replace_slide_text
from integrations.presentations.presentation_element_dispatcher import draw_page_elements
from integrations.templates.template_file_operations import TemplateFileError, load_template, save_new_template
from integrations.templates.template_slide_copy import copy_template_slide
from models.presentations.build_presentation_contract import BuildPresentationOutput, BuiltPresentationPage, PresentationPagePlan

logger = logging.getLogger(__name__)


class LocalPresentationBuilder:
    """根据宿主登记的模板与成品计划生成独立文件，原模板不会修改。"""

    def __init__(self, *, templates: Mapping[str, Path], output_directory: Path,
                 images: Mapping[str, bytes] | None = None, videos: Mapping[str, bytes] | None = None,
                 audios: Mapping[str, bytes] | None = None) -> None:
        self._templates = {key: Path(path).resolve() for key, path in templates.items()}
        self._output_directory = Path(output_directory).resolve()
        # 图片由宿主按编号预先提供，模型不能借工具读取任意本机文件。
        self._images = dict(images or {})
        self._videos = dict(videos or {})
        self._audios = dict(audios or {})

    @log_operation("presentation.build")
    def build(self, *, template_id: str, pages: list[PresentationPagePlan]) -> BuildPresentationOutput:
        """执行页面复制与替换；只校验能否执行，不调用成品检查工具。"""
        path = self._templates.get(template_id)
        if path is None:
            raise PresentationBuildError("模板编号未登记。")
        if not 1 <= len(pages) <= 100:
            raise PresentationBuildError("页面计划必须包含1至100页。")
        try:
            presentation = load_template(path)
            # 原页对象先保留引用：新页追加期间，计划只允许引用原模板，不能引用刚生成的页面。
            originals = list(presentation.slides)
            built = self._build_pages(presentation, originals, pages)
            # python-pptx没有公开删除幻灯片API：移除原页关系和列表项，保留后面按计划复制的页。
            # 这是对底层XML的受限操作，保存后仍需外部Office检查兼容性。
            slide_ids = presentation.slides._sldIdLst
            for slide_id in list(slide_ids)[:len(originals)]:
                presentation.part.drop_rel(slide_id.rId)
                slide_ids.remove(slide_id)
            artifact_id, file_name = save_new_template(presentation, self._output_directory)
        except PresentationBuildError:
            raise
        except (TemplateCompletionError, TemplateFileError) as error:
            raise PresentationBuildError(str(error)) from None
        except Exception as error:
            logger.error("event=presentation_build_failed error_location=%s", safe_error_location(error))
            raise PresentationBuildError("PPTX生成失败，请检查模板与运行日志。") from None
        logger.info("event=presentation_built slide_count=%d replacement_count=%d", len(built),
                    sum(item["replacement_count"] for item in built))
        return {"template_id": template_id, "artifact_id": artifact_id, "file_name": file_name,
                "slide_count": len(built), "pages": built,
                "warnings": ["未列出的文字保留原样，可能包含模板示例内容，请检查。",
                             "新增图片按指定宽高拉伸；列表标记为普通文字，表格列表不自动拆页。",
                             "视频和音频通过实验性接口嵌入，播放效果和编解码兼容性须在WPS/PowerPoint中验证。",
                             "未自动检查文字溢出、元素遮挡、字体或图表数据准确性。",
                             "文字替换仅保留第一段及首个文字片段样式，多段样式、换行显示及溢出需核对。",
                             "动画、切换及备注未复制，复杂资源可能不支持；实际Office打开效果未验证。",
                             "未核验页数要求、事实、大纲覆盖或来源；产物编号需宿主登记后供检查工具使用。"]}

    def _build_pages(self, presentation: PresentationDocument, originals: list[Slide],
                     pages: list[PresentationPagePlan]) -> list[BuiltPresentationPage]:
        """按计划复制原参考页、替换文字和绘制元素，并记录各页结果。"""
        built: list[BuiltPresentationPage] = []
        for number, plan in enumerate(pages, start=1):
            if plan.source_slide_number > len(originals):
                raise PresentationBuildError("参考页码超出原模板范围。")
            slide = copy_template_slide(presentation, originals[plan.source_slide_number - 1])
            replace_slide_text(slide, plan.replacements)
            draw_page_elements(slide, plan.elements, images=self._images, videos=self._videos, audios=self._audios,
                               slide_width=presentation.slide_width, slide_height=presentation.slide_height)
            built.append({"slide_number": number, "source_slide_number": plan.source_slide_number,
                          "role": plan.role, "replacement_count": len(plan.replacements),
                          "element_count": len(plan.elements)})
        return built
