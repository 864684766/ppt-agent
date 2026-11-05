"""宿主登记文件到模板编号，使用python-pptx只读解析，不调用Office或模型。"""

import hashlib
import logging
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

from pptx import Presentation
from pptx.exc import PackageNotFoundError

from domain.templates.template_inspector_contract import TemplateInspectionError
from integrations.pptx_shape_extractor import extract_shapes
from models.templates.template_structure import (
    TemplateLayout, TemplateMaster, TemplateSlide, TemplateStructure,
)


logger = logging.getLogger(__name__)


class LocalTemplateInspector:
    """只读取templates映射中允许的文件，模型不能用template_id拼接磁盘路径。"""

    def __init__(self, *, templates: Mapping[str, Path]) -> None:
        """复制宿主登记结果，不扫描硬盘；目前不承担上传目录或持久化管理。"""
        self._templates = {key: path.resolve() for key, path in templates.items()}

    def inspect(self, *, template_id: str) -> TemplateStructure:
        """一次读取同一份字节计算hash与解析，不保存或覆盖原文件。

        包内part路径作为版式/母版定位，页用Open XML slide_id；这些标识只在
        相同sha256的文件内解释，不承诺跨文件修改保持稳定。布局名称仅作线索。
        """
        path = self._templates.get(template_id)
        if path is None:
            raise TemplateInspectionError("模板编号未登记，请选择宿主提供的template_id。")
        if path.suffix.lower() != ".pptx":
            raise TemplateInspectionError("当前只支持PPTX模板，不支持旧版PPT或加密文件。")
        try:
            # 内存字节与hash保持一致；不下载外部链接，不执行嵌入内容。
            payload = path.read_bytes()
            presentation = Presentation(BytesIO(payload))
            warnings = [
                "仅提取结构与可读取文字，未渲染或OCR；图片文字、图表数据、SmartArt与嵌入内容未展开。",
                "母版/版式/页面对象分别返回，背景、主题字体、完整样式继承及视觉效果未解析。",
                "组合子对象使用局部坐标，未展开缩放/旋转/裁剪；绘制顺序不等于阅读顺序。",
            ]
            masters: list[TemplateMaster] = []
            layouts: list[TemplateLayout] = []
            # 第一步：读取“设计定义”。外层遍历母版，内层遍历这个母版管理的版式。
            # 母版好比一套设计规范，版式好比规范中的标题页/正文页排版方案。
            # 这里不是按实际页数循环，也没有只取前11项之类的数量限制。
            for master in presentation.slide_masters:
                master_id = str(master.part.partname)
                # append每次只添加一个母版字典。字典里的layout_ids是版式编号列表；
                # 一个母版管理11个版式时，masters增加1项，layout_ids内部有11项。
                masters.append({
                    "master_id": master_id,
                    "layout_ids": [str(layout.part.partname) for layout in master.slide_layouts],
                    "shapes": extract_shapes(master.shapes, part_id=master_id, warnings=warnings),
                })
                for layout in master.slide_layouts:
                    # partname是PPTX压缩包里的文件路径，用作关联编号；不是本机路径。
                    layout_id = str(layout.part.partname)
                    layouts.append({
                        "layout_id": layout_id, "name": layout.name, "master_id": master_id,
                        "shapes": extract_shapes(layout.shapes, part_id=layout_id, warnings=warnings),
                    })
            slides: list[TemplateSlide] = []
            # 第二步：独立遍历实际页面。enumerate(..., start=1)同时得到从1开始的
            # 页码number和当前页面slide；不因为版式重复就跳过页面。
            # 15张页面完全可以共用一个版式，所以slides与layouts数量无需相同。
            for number, slide in enumerate(presentation.slides, start=1):
                slides.append({
                    "slide_id": str(slide.slide_id), "slide_number": number,
                    "layout_id": str(slide.slide_layout.part.partname),
                    # 只提取这张页面自己的对象。母版/版式对象在上面单独保存，
                    # 不复制进这里，避免把设计提示文字误认为每页都有的真实正文。
                    "shapes": extract_shapes(
                        slide.shapes, part_id=str(slide.part.partname), warnings=warnings,
                    ),
                })
            return {
                "template_id": template_id, "file_name": path.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "slide_width_emu": presentation.slide_width,
                "slide_height_emu": presentation.slide_height,
                "slide_count": len(slides), "slides": slides,
                "layouts": layouts, "masters": masters, "warnings": warnings,
            }
        except (OSError, BadZipFile, PackageNotFoundError, SyntaxError, ValueError, KeyError,
                IndexError, NotImplementedError):
            # 不输出异常原文，避免记录模板正文或本机路径；解析失败整体报错，不伪装完整。
            logger.warning("模板结构读取失败：文件不可读、包结构损坏或存在未支持结构。")
            raise TemplateInspectionError(
                "无法解析模板，请确认是可打开、未加密的PPTX文件。"
            ) from None
