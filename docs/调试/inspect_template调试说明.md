# 第八个工具：inspect_template

日期：2026-11-04。状态：独立实现与ppt-demo真实文件验证完成；尚未接Harness、上传登记、页面角色判断或生成流程。

## 测试与断点

```powershell
uv run --locked --no-sync python -m pytest tests/test_inspect_template.py -s -q
```

PyCharm以pytest运行tests/test_inspect_template.py，附加参数-s。在`result = await tool.ainvoke(arguments)`打断点查看完整结果；可单步进入解析器和组合递归。结果很长，因为包含所有母版和版式，测试打印完整JSON，不需模型、网络、API密钥、Office或渲染工具。

测试入口扫描项目ppt-demo/下全部一级*.pptx，忽略Office的~$临时文件，以文件名（包含扩展名）登记为测试template_id。新增样本后重新运行，会逐份读取。工具本身不扫描ppt-demo，也不把编号当作路径拼接。

```python
templates = {"公司模板.pptx": PROJECT_ROOT / "ppt-demo" / "公司模板.pptx"}
inspector = LocalTemplateInspector(templates=templates)
tool = create_inspect_template_tool(inspector=inspector)
arguments = {"template_id": "公司模板.pptx"}
result = await tool.ainvoke(arguments)
```

此处是测试用登记映射。正式上传模块未来提供真实映射，不表示已经实现模板上传、模板列表工具或内存目录。尚无HTTP接口，本次不提供Postman地址。

## 返回结构

- template_id：本次宿主登记的模板编号；不是模型任意指定的本机路径。
- file_name：原始文件名，不含父目录。
- sha256：本次实际读取字节的SHA-256指纹。标识和结构应在相同指纹内解释，不是历史版本系统。
- slide_width_emu、slide_height_emu：画布宽高，914400 EMU=1英寸。
- slide_count、slides：实际样例页数与页面结构。slide_number从1开始，slide_id来自文件，不等于页码；layout_id关联layouts。
- layouts：全部母版的版式，包含未被样例页使用的版式；name是作者声明名称，master_id关联masters。
- masters：全部母版及管理的layout_ids。
- shapes：所在页面/版式/母版的直属对象。对象字段集中于models/templates/template_structure.py，包括定位、类型、坐标、文字、占位符与组合children。
- warnings：提取限制与具体对象警告。不等于模板无法使用或不合格，也不能把未提取解释成不存在。

坐标均为EMU。顶层coordinate_space=slide，组合子对象=group，未换算为页面绝对坐标；组合旋转/缩放/裁剪未展开。z_order只表示当前容器的绘制顺序，不代表阅读顺序。几何值None表示SDK未解析，不表示0。

text是对象自身文本框内容；None为没有文本框，空字符串为有空文本框。组合里的文字见children；表格文字见table_rows，合并关系和样式未展开。is_placeholder表示正式占位符，placeholder_idx和placeholder_type供后续映射；普通文本框不是占位符，但仍可能承载标题或正文。

object_id由包内part路径和shape_id组成，shape_id仅在所属part内唯一。layout_id/master_id是PPTX包内路径，不是宿主磁盘路径。文件变更后不承诺编号稳定。图像不OCR，图表数据、SmartArt、嵌入内容不展开；背景、主题字体、完整继承样式不解析，不进行视觉质量检查或页面渲染。

## 模块职责

| 文件 | 职责 |
| --- | --- |
| models/templates/template_structure.py | 公开结构事实，标准库TypedDict，不自动校验 |
| models/templates/inspect_template_contract.py | 输入Pydantic与输出契约；Output沿用事实字段，不重复定义同形内部实体 |
| domain/templates/template_inspector_contract.py | 可替换解析协议与公开错误 |
| integrations/templates/local_template_inspector.py | 宿主编号映射、读取字节、hash、页面/母版/版式结构提取 |
| integrations/templates/pptx_shape_extractor.py | 形状、占位符、文本、表格和组合递归 |
| tools/templates/inspect_template_tool.py | LangChain薄入口，线程执行与错误转换 |
| tests/test_inspect_template.py | 两项验证：tool-calling JSON及实际样本结果 |

解析器只读原文件，一份字节同时计算hash与解析；不会修改或保存PPTX。标识不在宿主映射中、后缀不支持、文件不可读或解析失败时报TemplateInspectionError，工具转换ToolException；解析错误不返回上游原文，具体提取限制通过warnings公开。结构提取不能代替PowerPoint真实打开验证。

## 实际结果

测试2 passed（1.06秒）。JSON定义含必填template_id及模型可见说明；实际结果核对原包XML页数与尺寸、hash、母版/版式关联和递归对象数量，并确认原文件hash未改变。

样本公司模板.pptx：

| 项目 | 实际结果 |
| --- | --- |
| 页数 | 5 |
| 母版 | 1，直属对象5个 |
| 版式 | 13，直属对象合计64个 |
| 画布 | 12192000 × 6858000 EMU，约13.333 × 7.5英寸 |
| 各页对象数（含组合子对象） | 9、15、7、3、1 |
| 样例页正式占位符 | 5页均为0，不代表无可填充文本框 |
| 目录文字 | 第2页组合内读取到CONTENTS及编号和文字 |

版式名称中有标题幻灯片、标题和内容等，但这些只是线索；不能因此将所有使用标题版式的页都认定为封面。工具不输出cover/content等角色、不判断残缺与否；后续由Agent综合结构与语义判断，不确定时交给用户。

结果项属于真实本地PPTX集成验证，不是隔离文件系统的单元测试。当前只验证这份实际样本，没有声称覆盖任意复杂PPTX、Office可打开性或视觉分析。当前使用已声明/锁定/安装的python-pptx==1.0.2，无新增依赖、升级、环境变量或Store；字段清单已更新。资源限制、并发与跨组件接线在后续实际任务中确定。

## 初学者：为什么页面、版式和母版数量不同（2026-11-05）

- `slides`是实际页面，相当于普通编辑视图左侧的每张幻灯片。
- `layouts`是可重复使用的排版定义，比如标题区、正文区如何摆放。一个版式可以被多页使用，未使用的版式也可保留。
- `masters`是管理一组版式的上层设计。一个母版可以管理多个版式，母版不是额外的播放页面。

查找关系为：`slides[i].layout_id`对应`layouts`中相同的`layout_id`；该版式的`master_id`再对应`masters`中的一项。这里的`i`是列表下标，从0开始，`slides[0]`就是第1页。

`len(result["masters"])`才是母版数量；`len(result["masters"][0]["layout_ids"])`是第一个母版管理的版式数量。两者不能混为一谈。解析循环没有11条截断限制。

本次核对当前样本`黄色活泼卡通幼儿通用PPT.pptx`：15张实际页面、1个母版、11个版式；唯一母版管理11个版式，15页全部关联`/ppt/slideLayouts/slideLayout7.xml`。通过python-pptx集合读取与直接检查PPTX压缩包XML文件数量交叉核对，三类数量一致。这不表示15页长得相同：各页仍然保存自己的图片、文字和其他对象。之前“实际结果”章节的公司模板是历史样本，不是当前文件。

`name`是文件保存的对象内部名称，可能由软件默认命名，也可能由作者修改；在WPS选择窗格可核对。`text`是对象文本框中保存的内容；母版/版式上的“单击此处编辑母版标题样式”是设计提示，不应直接作为实际页面正文。图片内文字不会自动变成`text`。

长度采用EMU整数单位：360000 EMU=1厘米，914400 EMU=1英寸；它不是像素。`None`表示库无法解析的未知值，不是坐标0。三个层级的`shapes`分别保存自身对象，不把继承对象平铺，不能直接等同于渲染后看到的所有元素。

本次仅完善代码注释、工具说明和文档，无新增字段、配置、依赖或工具；没有实现母版样式继承展开、渲染或页面角色判断。
