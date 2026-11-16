# create_template_page 调试说明

该工具按给定设计方案在模板末尾追加一页，并输出新的PPTX；不调用模型或自动分析风格。当前支持纯色背景、可编辑文字框与矩形，其他对象及图片未支持。版式可能继承母版装饰并带占位符，需要用户检查视觉效果。

运行 `tests/test_create_template_page.py` 的两个测试，或在 `result = await tool.ainvoke(arguments)` 打断点。`TEMPLATE_PATH` 为None时读取ppt-demo首个PPTX；`LAYOUT_ID` 必须来自同一模板的inspect_template结果。测试用的是该模板的第7个版式；更换模板时需同时调整版式和坐标。

`elements` 按列表顺序绘制，后画的对象位于前面对象上方。`x/y/width/height` 单位为英寸，起点为页面左上角，且对象必须完全位于页面内；`font_size` 单位为pt。颜色是`#RRGGBB`；矩形的`text`必须为空。字体依赖打开端安装，文字溢出、元素遮挡和外观未自动检查。

运行命令：`uv run --locked --no-sync python -m pytest tests/test_create_template_page.py -s -q`。测试输出完整工具JSON、参数、返回JSON和新文件路径，每次运行创建新文件。`output_template_id` 尚未自动登记给其他工具；需要外层登记。用户在WPS或PowerPoint中查看末页。

文件操作与complete_template共享读取、包校验和另存，原文件不修改。生成结果不能证明Office各版本视觉一致；用户询问、模型生成方案和工作流尚未接入。

2026-11-16：测试方案根据用户提供的“智研-微代码”截图手工填写，包含标题、说明文字和流程面板。工具仅支持文字框与矩形，右侧界面为可编辑的近似示意，非原界面截图；圆角、虚线及部分细节未复现。当前真实样本生成第6页，26个对象，工具JSON和结果两项测试通过；Gotenberg预览已人工检查，WPS字体和显示仍由用户确认。
