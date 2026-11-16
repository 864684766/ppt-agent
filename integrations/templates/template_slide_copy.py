"""在同一PPTX中复制受支持的页面对象；明确拒绝无法可靠复制的关联。"""

from copy import deepcopy

from domain.templates.template_completer_contract import TemplateCompletionError


_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_HYPERLINK = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"


def copy_template_slide(presentation, source):
    """复制参考页的图形树和背景，图片沿用原文件资源；不复制动画、备注和切换效果。

    python-pptx没有公开的整页复制接口，这里操作底层XML，限定同一演示文稿。
    涉及图表、音视频、幻灯片链接等复杂引用时明确失败，避免生成错误引用。
    """
    destination = presentation.slides.add_slide(source.slide_layout)
    # add_slide会根据版式创建占位符；后面复制参考页自身对象，先移除这些占位符。
    for shape in list(destination.shapes):
        shape._element.getparent().remove(shape._element)

    objects = [deepcopy(shape._element) for shape in source.shapes]
    background = deepcopy(source._element.cSld.bg) if source._element.cSld.bg is not None else None
    roots = objects + ([background] if background is not None else [])
    relationships: dict[str, str] = {}
    for root in roots:
        for element in root.iter():
            for attr, old_id in list(element.attrib.items()):
                if not attr.startswith(_REL_NS):
                    continue
                if old_id not in relationships:
                    try:
                        relation = source.part.rels[old_id]
                    except KeyError:
                        raise TemplateCompletionError("参考页存在无法解析的资源关联，无法复制。") from None
                    if relation.reltype not in {_IMAGE, _HYPERLINK}:
                        raise TemplateCompletionError("参考页包含暂不支持复制的资源（如图表、音视频或页面链接），请选择其他参考页。")
                    target = relation.target_ref if relation.is_external else relation.target_part
                    relationships[old_id] = destination.part.relate_to(target, relation.reltype, relation.is_external)
                element.set(attr, relationships[old_id])
    if background is not None:
        existing = destination._element.cSld.bg
        if existing is not None:
            destination._element.cSld.remove(existing)
        destination._element.cSld.insert(0, background)
    for element in objects:
        destination.shapes._spTree.insert_element_before(element, "p:extLst")
    return destination
