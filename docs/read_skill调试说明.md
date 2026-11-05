# 第七个工具：read_skill

日期：2026-11-04。状态：独立实现、JSON定义检查和实际技能文件结果验证完成；尚未接入Agent选技能循环、资源读取或脚本执行。

## 运行与断点

```powershell
uv run --locked --no-sync python -m pytest tests/test_read_skill.py -s -q
```

PyCharm以pytest运行tests/test_read_skill.py，参数-s。在`result = await tool.ainvoke(arguments)`打断点，查看result。默认读取fitness-nutrition；可把arguments改成list_skills返回的其他skill_id，例如flyai、legal-issue-research。完整输出可能较长，不调用模型、不联网、不执行技能脚本。

```python
arguments = {"skill_id": "fitness-nutrition"}
result = await tool.ainvoke(arguments)
```

工具根目录由宿主固定组装为PROJECT_ROOT / "skills"。工具输入不接受目录、references路径或scripts路径。没有新增HTTP接口，因此本次通过PyCharm/pytest测试，不提供不存在的Postman地址。

## 字段

| 字段 | 含义 |
| --- | --- |
| skill_id（输入） | 必填，list_skills返回的目录编号，不是技能name；不能含斜杠、反斜杠、冒号或以点开头，不能指定任意文件路径 |
| skill_id（输出） | 本次实际读取的技能目录编号 |
| resource_path | 技能内文件标识，当前固定SKILL.md，不是本机绝对路径 |
| content | 完整Markdown，包括YAML头部；UTF-8读取，去除开头BOM、规范换行，不截断、不总结、不展开引用文件 |

返回示意（仅为字段说明，测试打印实际全文）：

```json
{"skill_id": "fitness-nutrition", "resource_path": "SKILL.md", "content": "完整文件文本"}
```

## 实现职责

| 文件 | 职责 |
| --- | --- |
| models/skills/read_skill_contract.py | Input与公开Output定义；Field描述进入tool-calling Schema |
| domain/skills/skill_reader_contract.py | SkillReader协议与可公开的SkillReadError |
| integrations/skills/local_skill_reader.py | 本地定位、链接与目录边界检查、介绍格式校验、完整文件读取 |
| integrations/skills/skill_header_reader.py | 发现和读取共用的64KiB头部读取，原先从目录扫描实现中提取 |
| integrations/skills/skill_metadata_parser.py | 共用YAML解析与name/description等元数据检查 |
| tools/skills/read_skill_tool.py | LangChain薄入口、asyncio.to_thread调度、公开结果及错误转换 |
| tests/test_read_skill.py | 两项验证，打印JSON、调用参数及完整结果 |

LocalSkillReader.read返回普通str，协议与实现不依赖LangChain、Settings或FastAPI。薄工具用闭包注入reader，通过线程读取避免阻塞事件循环。没有为仅转发读取再增加业务层。

介绍不规范时不猜测修复，记录WARNING并抛SkillReadError，工具转换成ToolException；指定单个技能时不能把读取失败伪装为空文本成功。发现工具则跳过无效项继续列出其他技能。目录链接、junction和链接文件不读取。文件不存在/不支持UTF-8/不可访问同样报安全错误；不暴露异常原文或绝对路径。日志遵守全系统LOG_LEVEL与LOG_OUTPUT配置。

每次读取当前磁盘内容，无缓存、版本锁定或Graph状态；发现后技能可能改变或删除，此时应按实际文件读取或报错。当前返回完整文本，未增加正文大小或token上限，大文件的上下文成本留给Agent接入时评估；64KiB仅限制介绍头部，不限制正文。

## 验证结果与边界

read_skill两项测试通过；与list_skills两项回归合计4 passed（0.73秒）。第一项检查模型可见名称、用途、skill_id必填与说明；第二项读取真实fitness-nutrition/SKILL.md，验证返回编号、相对标识和全部文本与磁盘读取一致。

结果项是本地文件系统接入验证，不是隔离文件系统的单元测试。没有读取或执行技能内部脚本、分析依赖、检查MCP或验证专业业务能力。read_skill能调用不代表Agent已会选择技能；发现策略、附属资源与执行入口仍待子Agent阶段测试讨论。本次未新增环境变量、依赖、Store或技能执行工具。
