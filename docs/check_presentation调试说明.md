# check_presentation调试说明

2026-11-06，已完成基础检查工具的独立实现。当前是模型可选择的Agent工具，不是HTTP接口，也没有接入Harness或模型选工具循环。
本轮按用户决定先实现检查工具；下一项仍为build_presentation。大纲覆盖等扩展规则未实现，不将工具基础版完成写成全产品质检完成。

## 文件与职责

| 文件 | 职责 |
| --- | --- |
| models/presentations/check_presentation_contract.py | 输入CheckPresentationInput、公开报告CheckPresentationOutput及规则条目PresentationCheckItem |
| domain/presentations/presentation_checker_contract.py | PresentationChecker协议与安全错误，不依赖HTTP、文件系统或PPT SDK |
| integrations/templates/local_presentation_checker.py | 宿主编号对应本机PPTX，有界读取、包校验、PPT解析及规则结果组装 |
| tools/presentations/check_presentation_tool.py | 向模型暴露Schema，通过工作线程调用检查器，安全错误转ToolException |
| tests/test_check_presentation.py | 仅两项：tool-calling JSON及真实PPTX结果，完整打印供断点查看 |

模板与生成PPTX共用的外部PPT接入仍归integrations/templates；模型/协议按产物业务归presentations。不新增文件存储服务、全局缓存、模型调用、渲染、OCR或接口。

## 当前实际检查

| rule_id | required | 内容 |
| --- | --- | --- |
| file_size | true | 原文件非空，实际读取不超过宿主字节上限 |
| package_structure | true | 直接复用validate_office_package：ZIP/CRC/展开限额、关键XML、类型及根主文档关系等 |
| pptx_parse | true | python-pptx能读取实际幻灯片及基本文字，不代表Office打开无修复提示 |
| page_count | true | 对照宿主注入的总页数区间，默认8–12页，包含所有页面 |
| pages_without_text | false | 实际页文字框/组合/表格是否存在非空文字；缺少只给warning，不把图片页当空白错误 |
| outline_coverage | false | not_checked，未接入大纲/页面映射 |
| source_verification | false | not_checked，未核对来源原文与引用 |
| visual_layout | false | not_checked，未检查字号/越界/占位符残留/文字溢出/审美 |
| office_open | false | not_checked，需要用户在PowerPoint/WPS等实际打开核对 |

固定检查顺序为检查器内部必要技术依赖，不是把多个Agent工具串成固定流程。
前置失败后，无法执行的规则留not_checked。例如包损坏时不能伪造页数0或宣称页数通过。
passed仅表示所有required规则为pass；不包括尚未实现的产品验收标准。warning不会自动使passed为false。
no-text检查不读取母版编辑提示、图片OCR或图表数据，也不展开可见性/字体继承，不能证明内容完整或页面可见。

## 调用与参数

模型只传：

```json
{"artifact_id": "demo-presentation"}
```

artifact_id为宿主提供的本次产物编号，不是本机路径、URL或模板ID。工具不会自动扫描硬盘，未知编号报工具执行错误。
当前尚无生成产物系统；测试由宿主把ppt-demo真实PPTX登记成demo-presentation，后续生成时再登记实际产物。

```python
checker = LocalPresentationChecker(
    artifacts={"demo-presentation": pptx_path},
    min_slides=8,
    max_slides=12,
)
tool = create_check_presentation_tool(checker=checker)
result = await tool.ainvoke({"artifact_id": "demo-presentation"})
```

模型不能传入页数或大小限额来降低检查要求。宿主的构造参数均为正整数：
min_slides默认8、max_slides默认12，前者不能大于后者；max_file_bytes默认52428800（50MiB），max_uncompressed_bytes默认104857600（100MiB）。
这些是显式参数，没有新环境变量；以后实际工作流可以由外层注入配置。已有包校验还有5000个ZIP条目、关键XML2MiB等规则，不因为外层上限提高就自动取消。

只读打开文件，最多读取max_file_bytes+1字节判断实际超限；校验、解析和SHA-256针对同一份字节，避免重复读到不同版本。
超限中止时size_bytes和sha256为null，不把已读部分的长度/指纹冒充整份文件。
SDK对象及文件流不进入报告；文件流与BytesIO由实现关闭，PPT解析对象在调用结束后释放。取消to_thread等待不保证立刻终止底层读取，当前没有沙箱或独立进程超时。

## 报告字段

| 字段 | 含义 |
| --- | --- |
| artifact_id / file_name | 登记编号、展示文件名，不返回绝对路径 |
| sha256 | 本次完整文件字节指纹；超限未读完为null，不是真实性证明 |
| size_bytes | 完整读取后的字节数；超限为null |
| slide_count | 可解析后的实际页数；解析未成功为null |
| passed | 仅本轮必过规则是否全部pass，不是完整验收结论 |
| checks | 各条规则结果，固定顺序 |
| checks[].rule_id / status / required | 规则名；pass/fail/warning/not_checked；是否本轮必过 |
| checks[].message / expected / actual | 中文说明、要求、实际值；未取到事实为null，actual可为数字/字符串/页码列表 |
| checks[].slide_numbers | 有关实际页码，从1起；文件级或无问题时[] |

内容不合格返回正常报告，passed=false；无效编号/不可读取属于执行失败，抛PresentationCheckError并由工具变成ToolException。
包检查失败转换为规则结果，不吞掉真实错误，也不把SDK原文、正文和绝对路径返回模型。

## PyCharm测试

打开tests/test_check_presentation.py，修改顶部PPTX_PATH：

```python
PPTX_PATH = Path("E:/我的资料/演示文稿.pptx")
```

None时取ppt-demo中按名称排序的第一份PPTX（忽略~$文件）；不会循环检查整个目录。
修改MIN_SLIDES/MAX_SLIDES可改变宿主本次要求，它们不是模型参数。调用tool.ainvoke(arguments)处打断点，查看result即可。

```powershell
uv run --locked --no-sync python -m pytest tests/test_check_presentation.py -s -q
```

示例实际15页，而默认要求8–12页，所以passed=false、page_count=fail是正确检查结果，不是测试失败。
若只核对这份示例的15页要求，可将测试MIN_SLIDES/MAX_SLIDES都设为15；正式要求应由用户确认后由宿主提供。
未新增Postman目录、接口测试或模型请求。当前工具测试不要求先让模型选中工具。

## 日志与验证

tool.check_presentation → presentation.check记录父子操作、开始/结束/耗时；摘要仅passed、页数、失败/警告数量。
报告发现不合格为WARNING，执行错误为ERROR；包检查fail也会使报告摘要告警。SDK解析失败用safe_error_location记录安全位置。
正常日志不包含文件名、artifact_id、绝对路径、正文或SDK异常原文；测试控制台主动打印公开报告供学习。

本轮两项测试2 passed（0.91秒）：JSON定义可解析且参数说明可见；真实绿色几何创意演示PPT模板.pptx为3279793字节/15页，包与解析通过、页数不符合默认要求，其他未实现检查明确not_checked。
不把测试通过当作模型正确选工具、Harness接线、Windows打开验收或内容准确性验证。无新依赖或版本升级。

补充回归验证：检查工具、模板结构检查、日志配置和操作日志共15项测试通过（1.12秒）。临时文件烟测确认：10页样本通过必过规则且无文字页仅告警；损坏包返回不合格报告；未知产物编号明确报错。日志包含检查操作事件，未写入烟测文件正文标记。临时样本已清理，未新增额外持久测试。
