"""只读检查宿主登记的PPTX；复用Office包校验，不依赖HTTP、环境配置或模型。"""

from collections.abc import Mapping
import hashlib
from io import BytesIO
import logging
from pathlib import Path
from typing import Literal

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from diagnostics.operation_logging import log_operation, safe_error_location
from domain.presentations.presentation_checker_contract import PresentationCheckError
from domain.uploads.file_upload_errors import FileUploadError
from domain.uploads.office_package_validation import validate_office_package
from models.presentations.check_presentation_contract import (
    CheckPresentationOutput, PresentationCheckItem,
)

logger = logging.getLogger(__name__)


def _rule(
    rule_id: str, status: Literal["pass", "fail", "warning", "not_checked"], required: bool, message: str, *,
    expected: str | None = None, actual: int | str | list[int] | None = None,
    slides: list[int] | None = None,
) -> PresentationCheckItem:
    """集中构造公开规则字段；只传开发者选择的安全摘要，不传异常或正文对象。"""
    return dict(rule_id=rule_id, status=status, required=required, message=message,
                expected=expected, actual=actual, slide_numbers=slides or [])


class LocalPresentationChecker:
    """检查登记编号→本机文件，不扫描硬盘，不允许模型传任意路径。

    artifacts由外层复制登记，例如{"demo": Path(...)}，生成模块以后可登记实际产物。
    min_slides/max_slides为宿主本次要求，默认8–12页；默认原文件50MiB、
    Office展开100MiB。它们是显式构造参数，不是新环境变量或模型可改参数。
    文件以同一份有界字节校验/解析/计算指纹，不修改原文件；无跨请求缓存。
    """

    def __init__(
        self, *, artifacts: Mapping[str, Path], min_slides: int = 8, max_slides: int = 12,
        max_file_bytes: int = 50 * 1024 * 1024,
        max_uncompressed_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        for value in (min_slides, max_slides, max_file_bytes, max_uncompressed_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError("页数和文件检查限额必须为正整数。")
        if min_slides > max_slides:
            raise ValueError("最少页数不能大于最多页数。")
        self._artifacts = {key: Path(path).resolve() for key, path in artifacts.items()}
        self._min_slides, self._max_slides = min_slides, max_slides
        self._max_file_bytes = max_file_bytes
        self._max_uncompressed_bytes = max_uncompressed_bytes

    @log_operation("presentation.check")
    def check(self, *, artifact_id: str) -> CheckPresentationOutput:
        """文件不合格仍返回报告；未登记/不可读抛安全错误，由工具转换执行失败。"""
        path = self._artifacts.get(artifact_id)
        if path is None:
            raise PresentationCheckError("产物编号未登记，请选择宿主提供的artifact_id。")
        if path.suffix.lower() != ".pptx":
            raise PresentationCheckError("当前只能检查PPTX，请登记.pptx文件。")
        try:
            # 多读1字节判断实际超限，不依赖可能过期的文件stat，也不无限读大文件。
            with path.open("rb") as source:
                content = source.read(self._max_file_bytes + 1)
        except OSError:
            raise PresentationCheckError("无法读取登记的PPTX，请检查文件是否存在及访问权限。") from None
        report = self._check_content(content=content, artifact_id=artifact_id, file_name=path.name)
        logger.info(
            "event=presentation_check_result passed=%s slide_count=%s fail_count=%d warning_count=%d",
            report["passed"], report["slide_count"],
            sum(r["status"] == "fail" for r in report["checks"]),
            sum(r["status"] == "warning" for r in report["checks"]),
        )
        if not report["passed"]:
            logger.warning("event=presentation_checks_not_passed 文件未满足本轮必过规则，详情由检查报告提供。")
        return report

    def _check_content(self, *, content: bytes, artifact_id: str, file_name: str) -> CheckPresentationOutput:
        """复用包校验后才解析；前置失败的后续规则留not_checked，绝不假装通过。"""
        complete = len(content) <= self._max_file_bytes
        rules = [
            _rule("file_size", "not_checked", True, "尚未检查文件大小。"),
            _rule("package_structure", "not_checked", True, "文件大小/非空检查通过后才检查包结构。"),
            _rule("pptx_parse", "not_checked", True, "包结构检查通过后才尝试解析。"),
            _rule("page_count", "not_checked", True, "解析成功后才核对页数。",
                  expected=f"{self._min_slides}–{self._max_slides}页（包含封面等所有页）"),
            _rule("pages_without_text", "not_checked", False, "解析成功后才检查实际页面可提取文字。"),
            _rule("outline_coverage", "not_checked", False, "当前没有大纲/页面映射输入，未核对内容覆盖。"),
            _rule("source_verification", "not_checked", False, "当前未核查引用与来源原文，不能证明事实正确。"),
            _rule("visual_layout", "not_checked", False, "未检查字号、越界、占位符残留、实际溢出或审美。"),
            _rule("office_open", "not_checked", False, "未使用PowerPoint/WPS实际打开，请人工核对显示与修复提示。"),
        ]
        count = None
        if not content or not complete:
            rules[0] = _rule("file_size", "fail", True, "文件为空或超过本轮原文件字节上限。",
                             expected=f"1–{self._max_file_bytes}字节", actual=len(content) if complete else "超过上限，未完整读取")
        else:
            rules[0] = _rule("file_size", "pass", True, "原文件非空且未超过字节上限。",
                             expected=f"1–{self._max_file_bytes}字节", actual=len(content))
            try:
                validate_office_package(content=content, file_format="pptx", max_uncompressed_bytes=self._max_uncompressed_bytes)
            except FileUploadError as error:
                # 该错误在共享校验函数中只使用固定安全文案，不含PPT正文/路径。
                rules[1] = _rule("package_structure", "fail", True, str(error), actual=error.code)
            else:
                rules[1] = _rule("package_structure", "pass", True, "Office包基础检查通过，不代表所有关系或显示效果正确。")
                try:
                    with BytesIO(content) as stream:
                        presentation = Presentation(stream)
                        count = len(presentation.slides)
                        missing = [number for number, slide in enumerate(presentation.slides, 1)
                                   if not self._has_text(slide.shapes)]
                except Exception as error:
                    logger.warning("event=presentation_parse_failed error_location=%s", safe_error_location(error))
                    rules[2] = _rule("pptx_parse", "fail", True, "python-pptx无法解析实际页面，需检查文件或兼容性。")
                    count = None
                else:
                    rules[2] = _rule("pptx_parse", "pass", True, "python-pptx能够读取实际页面，不等于Office真实打开通过。")
                    rules[3] = _rule("page_count", "pass" if self._min_slides <= count <= self._max_slides else "fail", True,
                                     "按宿主本次要求核对总页数。", expected=rules[3]["expected"], actual=count)
                    rules[4] = _rule("pages_without_text", "warning" if missing else "pass", False,
                                     "无可提取文字页可能是合法图片页，不等于空白、内容缺失或错误。" if missing else "每页至少有一处可提取文字，不保证内容完整。",
                                     actual=missing, slides=missing)
        return dict(
            artifact_id=artifact_id, file_name=file_name,
            sha256=hashlib.sha256(content).hexdigest() if complete else None,
            size_bytes=len(content) if complete else None, slide_count=count,
            passed=all(r["status"] == "pass" for r in rules if r["required"]), checks=rules,
        )

    @staticmethod
    def _has_text(shapes) -> bool:
        """只看实际页上的文字框、组合及表格；不把母版编辑提示当正文。

        这里只回答“存在文字吗”，不是完整正文读取，不能据此判断图片、图表或
        母版继承内容为空。无需调用读取器私有方法或生成整份正文再丢弃结果。
        """
        for shape in shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP and LocalPresentationChecker._has_text(shape.shapes):
                return True
            if shape.has_text_frame and shape.text.strip():
                return True
            if shape.has_table and any(cell.text.strip() for row in shape.table.rows for cell in row.cells):
                return True
        return False
