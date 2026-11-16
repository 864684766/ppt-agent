"""在复制后的实际幻灯片上定位文字框并写入已确认内容。"""

from pptx.enum.shapes import MSO_SHAPE_TYPE

from domain.presentations.presentation_builder_contract import PresentationBuildError
from models.presentations.build_presentation_contract import TextReplacement


def _text_shapes(shapes):
    """递归遍历组合对象；母版、版式、表格单元格和图片中的文字不在此范围。"""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _text_shapes(shape.shapes)
        elif shape.has_text_frame:
            yield shape


def replace_slide_text(slide, replacements: list[TextReplacement]) -> None:
    """按shape_id替换完整文字框；保留第一段及第一文字片段样式，其他段落不保留。"""
    shapes = {shape.shape_id: shape for shape in _text_shapes(slide.shapes)}
    seen: set[int] = set()
    for item in replacements:
        if item.shape_id in seen:
            raise PresentationBuildError("同一页面的文字对象不能重复指定。")
        seen.add(item.shape_id)
        shape = shapes.get(item.shape_id)
        if shape is None:
            raise PresentationBuildError("指定的文字对象不存在或不支持，请检查参考页shape_id。")
        frame = shape.text_frame
        # text_frame.clear()保留第一段的段落属性；先复制第一段第一个run的样式。
        # 新内容可能有多行，但不声称保留原文字框中多段/多颜色的全部样式。
        from copy import deepcopy
        paragraph = frame.paragraphs[0]
        run_properties = deepcopy(paragraph.runs[0]._r.rPr) if paragraph.runs and paragraph.runs[0]._r.rPr is not None else None
        frame.clear()
        run = frame.paragraphs[0].add_run()
        if run_properties is not None:
            run._r.insert(0, run_properties)
        run.text = item.text
