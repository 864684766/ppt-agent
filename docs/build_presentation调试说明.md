# build_presentation 调试说明

工具把已确认的页面计划写入已登记的模板。它不决定大纲、不生成正文、不查资料，也不执行 `check_presentation`。页面计划按列表顺序决定成品页面顺序；未选中的原模板示例页不会放入成品，原模板不变。

## 输入与输出

`template_id` 是宿主登记的模板编号；`pages` 是1至100个页面计划，100为资源限制，不是成品合格标准。每页 `role` 是用途标签，`source_slide_number` 是原模板实际页码（从1起），`replacements` 是文字替换列表。替换项中 `shape_id` 来自同一模板、同一实际参考页的 `inspect_template` 结果；组合内文字要查看 `children`。`text` 是已确认的文字，空字符串可清空对应文字框。

返回 `template_id`、`artifact_id`（新编号）、`file_name`、`slide_count`、`pages` 和 `warnings`。每个pages项有成品 `slide_number`、原模板 `source_slide_number`、用途 `role`、`replacement_count`。宿主尚未自动登记artifact_id，后续调用检查工具需要外层把编号与新文件绑定。

## 范围和限制

2026-11-16更新：每页可选填 `elements`，按顺序混合 `type=text/image/video/audio/chart/table/list`，位置和宽高单位为英寸。文字填入 `text`；图片填宿主预先注入的 `image_id`（PNG/JPEG，按指定宽高拉伸）；视频填 `video_id`（MP4），可选 `poster_image_id` 指定封面；音频填 `audio_id`（MP3）。图表填 `chart_type`（column/line/pie）、`categories` 和 `series`；表格与列表使用各自绘制方案。图表系列的数据个数必须与分类数一致，饼图须有一个非负且含正数的系列。宿主在构造 `LocalPresentationBuilder` 时通过 `images`、`videos`、`audios` 三个编号到bytes的映射提供媒体；当前HTTP尚未接入媒体上传登记。

同一页元素按列表顺序叠放；不能自动避免与模板既有内容互相遮挡，不能自动检查文本溢出或分页。列表符号为普通文字，表格支持斑马色，不支持合并单元格或自动拆页；图表是原生对象，WPS中的数据编辑与显示仍需人工验证。模板中已有图表的复制仍可能因复杂关系被拒绝，与新建图表是两回事。

独立表格/列表工具已移除，内部绘制模块仍由 `build_presentation` 调用。未接入Agent自动设计，不代表调用方可只传主题就生成真实内容。视频与音频使用python-pptx实验性媒体接口，音频通过该库的movie接口嵌入；只核对基本文件标识和包内字节，无法保证编码或WPS/PowerPoint播放。无封面视频使用默认图标；默认不自动生成或下载媒体。

现有对象的文字替换仅支持实际页面的文字框，包含组合内文字；不修改已有图片文字、表格单元格、母版或版式文字。新增表格等对象使用上面的 `elements` 方案。未指定的文字保留，可能残留模板示例内容；图片文字也可能包含示例信息。替换以整个文字框为单位，仅尽量保留第一段和首个文字片段样式，复杂多段格式、显示换行、溢出和视觉效果需核对。复制使用底层PPTX XML，动画、切换和备注不复制；复杂图表、音视频等关联可能被明确拒绝。不会宣称任意PPTX格式无损。

生成工具只校验输入是否可执行，不自行运行成品质检或决定8至12页规则。应由模型或调用方按需调用独立的 `check_presentation`。生成结果不代表事实准确或引用已核实。

## 测试

`tests/test_build_presentation.py` 默认使用 `ppt-demo/公司模板.pptx`，包含手工准备的封面、目录、5个内容页和来源页，共8页。第3页混合文字、图片、柱状图、表格和列表；第4页有视频和音频。测试媒体来自MDN公开样例并保存在被git忽略的 `data/media-samples/`，从以下地址手动下载或替换同名文件：`https://raw.githubusercontent.com/mdn/learning-area/main/html/multimedia-and-embedding/video-and-audio-content/poster.png`、`rabbit320.mp4`、`viper.mp3`（后两项与前者同目录）。本项目不承诺样例资源可永久访问或已获得商业使用授权。其它文字、图表数值和来源均为示例，并非经过研究的业务内容；其它未替换的模板原文仍会保留。

在 `result = await tool.ainvoke(arguments)` 设置断点；测试打印完整工具JSON、输入、输出和文件路径。每次在 `data/built-presentations/` 新建文件，不覆盖原模板。用户用WPS或PowerPoint打开检查并自行管理测试文件。

```powershell
uv run --locked --no-sync python -m pytest tests/test_build_presentation.py -s -q
```

当前两项工具测试通过，生成及读取8页真实模板样例；与补全、页面绘制和检查工具相关回归共8项通过。Gotenberg转换该样例为8页PDF并检查第3/4页静态预览；PDF不验证视频或音频播放，WPS人工验收尚未进行。未知文字对象及未登记媒体会失败且不生成文件。
