"""根据用户确认的参考页追加示例页，不调用模型。"""

from collections.abc import Mapping
import logging
from pathlib import Path

from diagnostics.operation_logging import log_operation, safe_error_location
from domain.templates.template_completer_contract import TemplateCompletionError
from integrations.templates.template_file_operations import TemplateFileError, load_template, save_new_template
from integrations.templates.template_slide_copy import copy_template_slide
from models.templates.complete_template_contract import CompleteTemplateOutput, CompletedTemplatePage, TemplatePagePlan

logger = logging.getLogger(__name__)


class LocalTemplateCompleter:
    """读取宿主登记模板，在指定目录创建独立PPTX；调用方管理输出文件生命周期。

    复制原文件中明确指定的参考页及受支持的对象；不自动识别角色或改写正文。
    复杂关联会明确拒绝，动画等不复制，视觉一致性需实际打开核对。
    """

    def __init__(self, *, templates: Mapping[str, Path], output_directory: Path) -> None:
        self._templates = {key: Path(path).resolve() for key, path in templates.items()}
        self._output_directory = Path(output_directory).resolve()

    @log_operation("template.complete")
    def complete(self, *, template_id: str, target_slide_count: int, pages: list[TemplatePagePlan]) -> CompleteTemplateOutput:
        """追加计划中的页面；输入错误或文件处理失败抛TemplateCompletionError。"""
        source_path = self._templates.get(template_id)
        if source_path is None or source_path.suffix.lower() != ".pptx":
            raise TemplateCompletionError("模板编号未登记或不是PPTX文件。")
        # 直接调用适配器时也需要与工具输入相同的数量限制。
        if not 8 <= target_slide_count <= 12 or not 1 <= len(pages) <= 12:
            raise TemplateCompletionError("目标总页数应为8至12，补全计划需要1至12个页面。")
        try:
            presentation = load_template(source_path)
            original_count = len(presentation.slides)
            if original_count + len(pages) != target_slide_count:
                raise TemplateCompletionError("原页数加补全计划页数必须等于目标总页数；不会自动删页或重复页面。")
            added: list[CompletedTemplatePage] = []
            for plan in pages:
                if plan.source_slide_number > original_count:
                    raise TemplateCompletionError("参考页码超出原模板页数，请重新检查补全计划。")
                # 原始页码从1起，而Python集合下标从0起；不能把新加的页面当作原参考页。
                source_slide = presentation.slides[plan.source_slide_number - 1]
                copy_template_slide(presentation, source_slide)
                added.append({"role": plan.role, "source_slide_number": plan.source_slide_number,
                              "slide_number": len(presentation.slides)})
            # 全部计划成功后才保存；随机编号防止覆盖现有文件，包括原始模板。
            output_id, file_name = save_new_template(presentation, self._output_directory)
        except TemplateCompletionError:
            raise
        except TemplateFileError as error:
            raise TemplateCompletionError(str(error)) from None
        except Exception as error:
            logger.error("event=template_completion_failed error_location=%s", safe_error_location(error))
            raise TemplateCompletionError("模板读取或保存失败，请检查文件及运行日志。") from None
        logger.info("event=template_completion_result original_slides=%d added_slides=%d", original_count, len(added))
        return {"template_id": template_id, "output_template_id": output_id, "file_name": file_name,
                "original_slide_count": original_count, "slide_count": len(presentation.slides), "added_pages": added,
                "warnings": ["按参考页复制支持的对象和图片；动画、切换及备注未复制，请人工核对效果。",
                             "新增页保留参考页原文字，role仅为用途标签；未自动生成目录或来源内容。",
                             "新增页位于末尾；未进行角色识别、正文生成或Office实际打开验证。",
                             "输出编号尚未自动登记到其他工具，需由调用方登记输出文件。"]}
