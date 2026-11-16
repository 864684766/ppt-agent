# complete_template 调试说明

工具按明确计划复制原模板实际页面，保留支持的图形、文本及图片，追加到末尾。`target_slide_count` 是包含原页面的最终页数，默认10，可设置8至12；原页数加计划页数必须等于目标，工具不自动删除或挑选页面。

在 `tests/test_complete_template.py` 设置 `TEMPLATE_PATH`、`SOURCE_SLIDE_NUMBER`、`TARGET_SLIDE_COUNT` 与 `OUTPUT_DIRECTORY`。参考页码从1开始，须属于原模板。示例将第3页复制到8页；换模板后要根据实际页面调整。也可以直接修改 `arguments["pages"]`，每项填写 `role` 和 `source_slide_number`，为不同新增页选择不同参考页。

在 `tool.ainvoke(arguments)` 处打断点。输出保存在 `data/completed-templates/`，使用随机文件名，不覆盖原文件。用WPS或PowerPoint打开，比较参考页和末尾新增页；每次运行均产生新文件，由调用方管理。

```powershell
uv run --locked --no-sync python -m pytest tests/test_complete_template.py -s -q
```

输出 `template_id` 为原模板编号，`output_template_id` 为新编号，`file_name` 为新文件名；`original_slide_count` 与 `slide_count` 为原始及输出总页数；`added_pages` 包含用途标签 `role`、原始参考页码 `source_slide_number` 和新增页码 `slide_number`；`warnings` 说明限制。新编号尚未自动登记给其他工具。

本版复制参考页的内容，不会自动设计不同用途的目录页或来源页；`role` 只是标签，新增页保留参考页原文字。复制使用python-pptx底层XML，支持页面对象中的图片和超链接；动画、切换、备注不复制，图表、音视频、页面链接等复杂关联明确拒绝，不保证任意模板完整兼容。生成的文件须实际打开核对。模型与LangGraph尚未接入。

本次真实模板为5页，目标8页，复制第3页3次，工具JSON及文件测试2项通过；Gotenberg转换后比较PDF第3页与第6页的渲染像素，平均差为0。该结果仅适用于该测试文件和转换环境，不代表WPS或其他模板效果相同。
