# build_presentation 调试说明

工具把已确认的页面计划写入已登记的模板。它不决定大纲、不生成正文、不查资料，也不执行 `check_presentation`。页面计划按列表顺序决定成品页面顺序；未选中的原模板示例页不会放入成品，原模板不变。

## 输入与输出

`template_id` 是宿主登记的模板编号；`pages` 是1至100个页面计划，100为资源限制，不是成品合格标准。每页 `role` 是用途标签，`source_slide_number` 是原模板实际页码（从1起），`replacements` 是文字替换列表。替换项中 `shape_id` 来自同一模板、同一实际参考页的 `inspect_template` 结果；组合内文字要查看 `children`。`text` 是已确认的文字，空字符串可清空对应文字框。

返回 `template_id`、`artifact_id`（新编号）、`file_name`、`slide_count`、`pages` 和 `warnings`。每个pages项有成品 `slide_number`、原模板 `source_slide_number`、用途 `role`、`replacement_count`。宿主尚未自动登记artifact_id，后续调用检查工具需要外层把编号与新文件绑定。

## 范围和限制

2026-11-16更新：每页可选填 `elements`，按顺序混合 `type=text/image/video/audio/chart/table/list`，位置和宽高单位为英寸。文字填入 `text`；图片填宿主预先注入的 `image_id`（PNG/JPEG，按指定宽高拉伸）；视频填 `video_id`（MP4），可选 `poster_image_id` 指定封面；音频填 `audio_id`（MP3）。图表填 `chart_type`（column/line/pie）、`categories` 和 `series`；表格与列表使用各自绘制方案。图表系列的数据个数必须与分类数一致，饼图须有一个非负且含正数的系列。宿主在构造 `LocalPresentationBuilder` 时通过 `images`、`videos`、`audios` 三个编号到bytes的映射提供媒体；当前HTTP尚未接入媒体上传登记。

同一页元素按列表顺序叠放；不能自动避免与模板既有内容互相遮挡，不能自动检查文本溢出或分页。列表符号为普通文字，表格支持斑马色，不支持合并单元格或自动拆页；图表是原生对象，WPS中的数据编辑与显示仍需人工验证。模板中已有图表的复制仍可能因复杂关系被拒绝，与新建图表是两回事。

表格可用 `header_color`、`header_text_color`、`row_colors`、`text_color` 设置颜色，不传时使用代码默认色，并非自动识别模板。本次健身计划显式指定深绿表头、白字和白/浅绿交替行。

图表每个柱状或折线系列可选 `color`（#RRGGBB），未指定时保留Office主题色；饼图可选 `point_colors`，颜色顺序和数量与分类一致，未传时保留主题色。`point_colors`只用于饼图，饼图不能传系列`color`。当前没有完整的图表背景、图例、字号及布局样式接口，且不会自动提取模板配色；实际显示需在目标Office软件验收。

图表现可选 `style`：`title`（空字符串隐藏）、`legend_visible`、`legend_position`（bottom/top/left/right，须开启图例）、`data_labels`（显示数值）、`font_name`、`font_size`（pt）。柱状和折线图另可选 `category_axis` 和 `value_axis`：`visible`、`title`、`line_visible`、`line_color`、`line_width`（pt）、`major_tick`/`minor_tick`（none/inside/outside/cross）、`label_position`（none/next_to_axis/low/high）、`label_font_name`、`label_font_size`（pt）、`label_color`、`major_gridlines`、`gridline_color`、`gridline_width`（pt）。数值轴额外支持 `minimum`、`maximum`、`major_unit`、`minor_unit` 和数字格式 `number_format`（例如0、0.0、0%）。不传时沿用Office默认；饼图不能配置坐标轴，分类轴不支持数值范围/间隔/数字格式。隐藏轴线不能同时配置其颜色/宽度，网格线颜色或宽度要求开启主要网格线。模型字段、范围、默认值和交叉约束见 `models/presentations/presentation_chart_style.py`。

本次还检查了其他绘制模块：文字支持字体、字号、颜色和位置，暂不支持独立对齐/行距/粗体等；表格支持表头/行颜色、字号和字体，暂不支持列宽、边框、合并或单元格独立样式；列表支持内容、层级和普通文字标记，不是原生自动编号；图片按指定尺寸拉伸，不支持等比裁剪；视频/音频为实验性嵌入。图表本次也未覆盖所有大屏图表效果，例如对数轴、轴交叉位置、刻度标签旋转、次网格线、透明度、渐变、逐点特殊样式与动画。不要将上述基础配置表述为全部细节可调；在真实模板、WPS、PowerPoint中的视觉和编辑效果仍需验收。

后续Harness接入时，应在提示词与技能中要求结合模板结构、可用的视觉分析和用户要求选择表格/图表配色，注意文字对比度，并在不确定时询问用户；提示词不能代替工具能力或自动保证效果。完整样式提取、自动配色、视觉对照及真实模型遵循情况仍待实现和验证，不能表述为已接入。

独立表格/列表工具已移除，内部绘制模块仍由 `build_presentation` 调用。未接入Agent自动设计，不代表调用方可只传主题就生成真实内容。视频与音频使用python-pptx实验性媒体接口，音频通过该库的movie接口嵌入；只核对基本文件标识和包内字节，无法保证编码或WPS/PowerPoint播放。无封面视频使用默认图标；默认不自动生成或下载媒体。

现有对象的文字替换仅支持实际页面的文字框，包含组合内文字；不修改已有图片文字、表格单元格、母版或版式文字。新增表格等对象使用上面的 `elements` 方案。未指定的文字保留，可能残留模板示例内容；图片文字也可能包含示例信息。替换以整个文字框为单位，仅尽量保留第一段和首个文字片段样式，复杂多段格式、显示换行、溢出和视觉效果需核对。复制使用底层PPTX XML，动画、切换和备注不复制；复杂图表、音视频等关联可能被明确拒绝。不会宣称任意PPTX格式无损。

生成工具只校验输入是否可执行，不自行运行成品质检或决定8至12页规则。应由模型或调用方按需调用独立的 `check_presentation`。生成结果不代表事实准确或引用已核实。

## 测试

`tests/test_build_presentation.py` 默认使用 `ppt-demo/绿色几何创意演示PPT模板.pptx`，生成8页健身计划：封面引用原模板第1页，目录引用第2页，后续内容页引用第4页；通过原页面的shape_id替换文字，复用其几何装饰和布局。图表单独添加白色图片底板，提高主题图表与原绿色背景的对比度。原模板不变；更换模板时须重新分析参考页、文字对象和空余区域，不能沿用页码和坐标。

运动建议参考 [WHO 身体活动事实清单](https://www.who.int/news-room/fact-sheets/detail/physical-activity)及 [CDC 成人运动指南](https://www.cdc.gov/physical-activity-basics/guidelines/adults.html)。图表中的分钟分配是手工编写的演示计划，不是统计数据或固定推荐比例，不能代替个体化运动指导。

图片为 Larry D. Moore 的 [Exercise Treadmill Convey Motion](https://commons.wikimedia.org/wiki/File:Exercise_Treadmill_Convey_Motion.jpg)，CC BY 4.0；视频为 FitnessScape 的 [Squat exercise demonstration](https://commons.wikimedia.org/wiki/File:Squat_-_exercise_demonstration_video.webm)，CC BY 3.0。本次将视频从WebM转为H.264 MP4，并截取一帧作封面；素材来源及修改已在成品来源页标注。素材放在被Git忽略的 `data/media-samples/`，测试需要 `fitness-treadmill.jpg`、`fitness-squat.mp4`、`fitness-squat-poster.jpg`，删除后应重新准备或修改测试。用于其他用途时应自行遵守相应素材许可。

在 `result = await tool.ainvoke(arguments)` 设置断点；测试打印完整工具JSON、输入、输出和文件路径。每次在 `data/built-presentations/` 新建文件，不覆盖原模板。用户用WPS或PowerPoint打开检查并自行管理测试文件。

```powershell
uv run --locked --no-sync python -m pytest tests/test_build_presentation.py -s -q
```

当前两项工具测试通过，生成及读取8页样例；Gotenberg转换为8页PDF并逐页检查静态预览。PDF不能验证视频播放，WPS中的播放和图表编辑仍需用户验收。测试执行时不联网搜索，也不会使用模型自动生成计划。
