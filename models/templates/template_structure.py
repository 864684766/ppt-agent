"""模板结构事实的共享数据；解析器创建、工具公开，不含宿主磁盘路径。

先认识三个不同的列表，它们的数量不需要相同：
1. slides（实际页面）：平时打开PPT看到的第1页、第2页……内容主要在这里。
2. layouts（版式）：可重复使用的排版定义，例如“标题幻灯片”“标题和内容”。
   多张实际页面可以使用同一个版式，文件也可以保存暂时没有页面使用的版式。
3. masters（母版）：管理一组版式的上层设计定义，可提供共用对象和样式。
   一份PPT可以包含多个母版；母版不是额外的演示页面，不计入slides页数。

通过编号查找关系：slide.layout_id → layout.layout_id，
再通过layout.master_id → master.master_id。箭头表示“按相同字符串查找”，
不是Python自动完成的关联查询。例如15页共享1个母版及其某个版式是正常的。
三个层级各自的shapes仅记录本层对象，不把继承对象复制进每张页面。

TypedDict仅描述字典结构，不执行运行时校验。此处数据本身就是公开结构事实，
没有另外复制一套同形内部实体；解析实现与工具共享标准库类型定义。
"""

from typing import Literal, TypedDict


class TemplateShape(TypedDict):
    """页面/版式/母版上的对象；组合的子对象递归保存，避免丢失文字。"""

    # 包内part标识加shape_id，定位同一文件内的对象，不是本机路径。
    object_id: str
    # Open XML形状编号，仅在所属part内唯一，不是跨文件主键。
    shape_id: int
    # 文件保存的内部对象名，如“标题 1”“Picture 2”；可能由软件默认命名或作者修改。
    # 可在WPS选择窗格核对；不是页面显示的文字，可重复，不能作为唯一标识。
    name: str
    # python-pptx识别的类型名称，例如GROUP/PICTURE/TEXT_BOX。
    shape_type: str
    # 当前容器内从1开始的XML绘制顺序；不代表语义阅读顺序。
    z_order: int
    # 顶层为slide，组合子对象为group；后者未转换为幻灯片绝对坐标。
    coordinate_space: Literal["slide", "group"]
    # 对象左边距离坐标原点的水平距离。EMU是PPT保存长度的整数单位，不是像素；
    # 360000 EMU=1厘米，914400 EMU=1英寸。例如720000表示2厘米。
    # SDK（这里是python-pptx库）无法解析时为None，表示未知，不是0。
    left_emu: int | None
    # 对象顶边坐标，单位EMU，坐标空间同coordinate_space；未知为None。
    top_emu: int | None
    # 对象宽度，单位EMU；未应用组合的外层缩放，未知为None。
    width_emu: int | None
    # 对象高度，单位EMU；未应用组合的外层缩放，未知为None。
    height_emu: int | None
    # 对象旋转角度，单位度；组合继承变换未展开。
    rotation_degrees: float
    # 是否为正式占位符；普通文本框不因此变为占位符。
    is_placeholder: bool
    # 占位符idx用于页与版式匹配，只在相应范围解释；非占位符为None。
    placeholder_idx: int | None
    # 正式类型，例如TITLE/BODY/OBJECT；非占位符为None，不等于封面/目录角色。
    placeholder_type: str | None
    # 文件中本对象自身文本框保存的文字；无文本框为None，空文本框为""。
    # 版式/母版可能保存“单击此处编辑母版标题样式”等提示，不等于实际页面正文。
    # 图片里的字不在这里（需要OCR或视觉模型），组合内部文字要继续看children。
    text: str | None
    # 表格按行和单元格提取文字；非表格为空列表，合并关系和样式未展开。
    table_rows: list[list[str]]
    # 组合内递归对象；普通对象为空列表，不复制母版/版式上的对象。
    children: list["TemplateShape"]


class TemplateSlide(TypedDict):
    """一张实际页面；对应WPS普通编辑视图左侧的一张页面缩略图。

    这里记录“页面上有什么”，不判断“这页是封面还是目录”；页面角色需后续分析。
    """

    # 当前文件内的slide_id，不是页码；配合文件sha256使用。
    slide_id: str
    # 从1开始的展示页序，文件修改后可能变化。
    slide_number: int
    # 本页使用的版式编号；用它在返回结果layouts中查找layout_id相同的那一项。
    # 例如slideLayout7.xml表示版式文件标识，不表示第7页；多页可以引用同一版式。
    # 版式只提供排版线索，使用标题版式也不保证这一页在业务上就是封面。
    layout_id: str
    # 本页自身对象；背景及母版对象未平铺到本页。
    shapes: list[TemplateShape]


class TemplateLayout(TypedDict):
    """可复用的排版定义，不是一张实际播放的页面。

    类似一张空白填写表：规定标题区、正文区等位置及默认样式。
    多张页面可以共用；未使用的版式也会返回，因此数量不等于slides数量。
    """

    # PPTX包内part路径，如/ppt/slideLayouts/slideLayout1.xml。
    layout_id: str
    # 作者声明的版式名，只作判断线索。
    name: str
    # 所属母版编号；在返回结果masters中查找master_id相同的项，即可找到上层设计。
    master_id: str
    # 版式自身对象与占位符，不包含母版继承对象。
    shapes: list[TemplateShape]


class TemplateMaster(TypedDict):
    """一套版式的上层设计定义，对应WPS母版视图中上方的大缩略图。

    一个母版可管理多个版式，母版的共用对象和默认样式可供页面继承。
    但是否实际显示还与页面、版式及显示设置有关，本结果不是最终渲染画面。
    当前只读取母版标识、所管理的版式编号及直属对象，没有完整展开样式继承。
    """

    # PPTX包内part路径，供版式关联，不是本机路径。
    master_id: str
    # 该母版管理的全部版式编号，用于在layouts列表中逐项查找。
    # len(layout_ids)=11表示这个母版管理11个版式，不表示11个母版或11张页面。
    layout_ids: list[str]
    # 母版自身对象；主题、背景、字体及完整继承样式未展开。
    shapes: list[TemplateShape]


class TemplateStructure(TypedDict):
    """inspect_template公开的确定性事实，不包含模型判断的页面角色。"""

    # 宿主登记的模板标识，不由模型解析为本地路径。
    template_id: str
    # 仅文件名，便于用户识别，不公开父目录。
    file_name: str
    # 读取字节的SHA-256；相同编号内容变更时hash随之改变，不是版本管理系统。
    sha256: str
    # 页面宽高，单位EMU；所有结构使用同一单位。
    slide_width_emu: int
    # 页面高度，单位EMU；与宽度合用描述页面画布，不代表对象可见边界。
    slide_height_emu: int
    # 样例页数，等于slides长度，不是目标PPT页数。
    slide_count: int
    # 实际页面列表，按展示顺序返回；len(slides)=slide_count，不分页、不截断。
    slides: list[TemplateSlide]
    # 所有母版管理的版式列表，包括未使用版式；数量不要求等于实际页数。
    layouts: list[TemplateLayout]
    # 母版列表，不是页面列表；len(masters)才是母版数量。
    # 每项内部layout_ids的长度是所属版式数，不是母版数；不假设文件只有一个母版。
    masters: list[TemplateMaster]
    # 当前提取限制及具体对象警告；没有提取不代表对象内容为空或不可用。
    warnings: list[str]
