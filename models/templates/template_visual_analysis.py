"""视觉模型返回的数据：都是基于图片的判断，不是PPT文件结构事实。

与TemplateStructure不同，这里使用Pydantic，因为模型输出属于外部输入，
需要在交给调用方之前检查字段是否齐全、类型是否正确。校验通过只说明
“格式符合约定”，不表示文字识别和页面角色判断一定正确。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TemplateVisualAnalysis(BaseModel):
    """单张页面图片的观察结果；适配器创建，测试和未来Harness调用方使用。

    不包含对象编号、母版编号或可编辑性；这些必须结合结构解析确定。
    没有页面来源字段：调用方负责保存输入图片与真实页面的对应关系，
    本模块不把用户截图或PPT内嵌缩略图自动认作某一页。
    """

    # 拒绝未约定字段，避免模型额外生成的“可编辑性”等猜测悄悄进入结果。
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    page_role: Literal["cover", "agenda", "section", "content", "ending", "unknown"] = Field(
        description="页面用途判断：封面、目录、章节、正文、结尾、无法确定；不是结构事实。",
    )
    role_evidence: str = Field(
        min_length=1, description="判断页面用途的可见依据；无法判断时说明原因，不编造。",
    )
    visible_texts: list[str] = Field(
        description="图片中能辨认的文字，按大致阅读顺序列出；不补全模糊文字，无可读文字时为空列表。",
    )
    layout_description: str = Field(
        min_length=1, description="标题、正文、图片等区域的相对位置描述，不包含猜测的对象编号或精确坐标。",
    )
    main_colors: list[str] = Field(
        description="观察到的主要颜色名称，例如白色、深蓝；不是从主题文件提取的色值。",
    )
    limitations: list[str] = Field(
        description="低分辨率、遮挡、文字模糊等限制；没有额外发现时为空列表，不代表结果已验证。",
    )
