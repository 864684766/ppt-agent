"""提取单个容器的形状事实；不把对象名称或文字解释成页面角色。"""

from collections.abc import Iterable

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.base import BaseShape

from models.templates.template_structure import TemplateShape


def extract_shapes(
    shapes: Iterable[BaseShape], *, part_id: str, warnings: list[str], in_group: bool = False,
) -> list[TemplateShape]:
    """递归读取形状、文本及表格；warnings由本次解析独占，不使用全局状态。

    EMU保留原值，避免转换时丢精度。组合子对象保持其局部坐标，旋转、缩放、
    裁剪与继承不展开，因此结果不能当成最终渲染布局。
    """
    items: list[TemplateShape] = []
    for order, shape in enumerate(shapes, start=1):
        object_id = f"{part_id}#shape-{shape.shape_id}"
        placeholder = shape.placeholder_format if shape.is_placeholder else None
        children: list[TemplateShape] = []
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            children = extract_shapes(
                shape.shapes, part_id=part_id, warnings=warnings, in_group=True,
            )
        if shape.has_chart or shape.shape_type in {
            MSO_SHAPE_TYPE.IGX_GRAPHIC, MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT,
            MSO_SHAPE_TYPE.LINKED_OLE_OBJECT,
        }:
            warnings.append(f"{object_id}：仅提取对象外框，未展开图表、SmartArt或嵌入内容。")
        table_rows = (
            [[cell.text for cell in row.cells] for row in shape.table.rows]
            if shape.has_table else []
        )
        items.append({
            "object_id": object_id,
            "shape_id": shape.shape_id,
            "name": shape.name,
            "shape_type": shape.shape_type.name,
            "z_order": order,
            "coordinate_space": "group" if in_group else "slide",
            "left_emu": shape.left,
            "top_emu": shape.top,
            "width_emu": shape.width,
            "height_emu": shape.height,
            "rotation_degrees": shape.rotation,
            "is_placeholder": shape.is_placeholder,
            "placeholder_idx": placeholder.idx if placeholder is not None else None,
            "placeholder_type": placeholder.type.name if placeholder is not None else None,
            "text": shape.text_frame.text if shape.has_text_frame else None,
            "table_rows": table_rows,
            "children": children,
        })
    return items
