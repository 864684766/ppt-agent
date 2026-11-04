# 第六个工具：list_skills

日期：2026-11-04。状态：独立实现、JSON定义检查及真实本地技能目录验证完成；read_skill已独立实现；Agent选择技能、附属资源读取和执行脚本尚未实现。

## 运行与断点

```powershell
uv run --locked --no-sync python -m pytest tests/test_list_skills.py -s -q
```

PyCharm以pytest运行tests/test_list_skills.py，附加参数-s；在`result = await tool.ainvoke(arguments)`打断点，F8后查看result。keyword为空列出全部，改为法律或nutrition可看字面筛选。不会调用模型、联网或运行技能脚本。

固定从项目根目录skills/读取，不通过环境变量切换目录。目录不存在明确报错，不自动创建。只扫描一级目录中的SKILL.md，不递归扫描技能内tests、src、脚本或配置。链接目录、junction及链接SKILL.md不读取。

## 职责边界

list_skills只扫描项目内置skills/目录，读取SKILL.md介绍并返回摘要。不会检查技能依赖、分析脚本或执行步骤、检查MCP配置、安装环境或判断技能是否可执行。不符合读取格式的技能只记录WARNING日志并忽略，不返回模型警告字段。技能内部如何执行由技能说明与实际调用方处理，不属于发现工具。

## 输入输出

| 字段 | 含义与边界 |
| --- | --- |
| keyword（输入） | 可选字符串，默认空，最多200字符；按编号/名称/用途说明做大小写不敏感的字面子串匹配，不自动翻译或扩展同义词 |
| items | 匹配后的有效技能摘要，按skill_id排序；无匹配为空 |
| items[].skill_id | 根目录下一级文件夹名，标识技能；可能不同于name，不是任意文件路径 |
| items[].name | SKILL.md YAML头部的name，必需非空字符串 |
| items[].description | 头部description，必需非空字符串，支持多行；作者声明不代表能力已验证 |
| items[].version | 优先顶层version，其次metadata.version；不存在为null，不虚构版本 |
| returned_count | items条数；当前无分页 |

工具元数据通过Field描述及工具description向模型解释。项目skills/下所有一级技能目录均属于发现范围，当前没有任务授权筛选、角色自动分类或市场安装。不能因为列出flyai或legal-issue-research，就认为它们的MCP、外部API或专业规则已经接通。

## 元数据读取

支持的基本结构为一级技能目录中的UTF-8 SKILL.md，以---包围YAML头部，必需非空字符串name与description；不会从不规范正文猜测或修复介绍。不做完整技能包规范/执行有效性审查。可选版本无法识别时返回null，不因无关可选字段拒绝介绍。

日志由integrations.local_skill_catalog模块的logger记录，仅包含目录名和安全原因。宿主入口读取LOG_LEVEL（默认INFO）和LOG_OUTPUT（默认both），统一组装日志；file写项目log/ppt-agent-YYYY-MM-DD.log，console写stderr且不创建文件，both两者。导入工具不初始化日志；独立结果测试已在入口接线。pytest自带输出及print不受本项目输出目标控制。详见[日志使用说明](日志使用说明.md)。不符合格式的技能记录WARNING后忽略；根目录不可用仍报错。

只读SKILL.md的开头YAML头部，最多64KiB，支持UTF-8 BOM、Windows换行、多行description和嵌套metadata.version；使用yaml.safe_load，不执行文件或导入技能代码。其他头部字段暂不映射为可执行能力。缺失SKILL.md、非法YAML、缺少非空name/description等通过Python logging记录WARNING后跳过该技能；根目录整体不可访问则工具报错。

每次工具调用重新扫描，文件扫描在asyncio.to_thread中执行，不阻塞事件循环，不建立全局缓存。创建工具及转换JSON时不扫描。此次元数据列表只是发现结果，不是后续read_skill的正文快照锁定或热更新系统；重新扫描不能被描述为运行中技能已安全替换。

## 验证记录

按日文件命名后共8 passed（0.89秒），跨天首条记录自动切换、同日追加通过；历史条目中的文件行为以当前日志使用说明为准。

统一日志输出接线后共7 passed（0.96秒），验证三种目标、多个模块共享配置、级别及切换行为；此前记录为对应历史验证结果。

LOG_LEVEL接入后：日志及技能测试3 passed（0.66秒），验证WARNING排除INFO、切换DEBUG后写入调试记录、相同处理器不重复写入；Settings读取LOG_LEVEL=WARNING通过。

2026-11-04文件日志接线验证：test_logging_config.py与test_list_skills.py合计3 passed（0.73秒）；重复初始化仅写一份中文WARNING。实际目录当前返回4项（含chef-assistant），无扫描WARNING；另用临时不规范技能验证跳过日志实际写入项目log/ppt-agent-YYYY-MM-DD.log，FastAPI lifespan启动记录也已落盘。用户技能未修改。

2026-11-04移除技能目录环境配置后重新验证：JSON定义及真实目录结果2 passed（0.72秒），读取项目根目录skills/，返回fitness-nutrition、flyai、legal-issue-research三项；chef-assistant因SKILL.md缺失、不可读或非UTF-8触发WARNING并跳过，没有中断其他技能扫描。未修改用户技能文件。

两项检查2 passed：JSON定义可解析且keyword说明可见；真实本地目录输出结果结构正常、编号有对应文件且按编号排序。实际返回fitness-nutrition（1.0.0）、flyai（metadata.version为1.0.15）、legal-issue-research（未声明版本，null），未产生扫描警告日志。另以真实快照检查法律关键词，命中legal-issue-research。未新增模拟技能，没有改写用户技能包。

结果项是依赖本地目录的集成验证，不是完全隔离文件系统的单元测试；目录变化后内容可变化。未验证模型选工具、read_skill、MCP、脚本或技能的专业结论。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| models/skills/skill_summary.py | 内部技能摘要 |
| models/skills/list_skills_contract.py | 工具输入与公开输出 |
| domain/skills/skill_catalog_contract.py | 可替换目录协议和安全异常 |
| domain/skills/skill_catalog.py | 纯筛选与排序，无文件系统和框架依赖 |
| integrations/local_skill_catalog.py | 实际目录扫描 |
| integrations/skill_header_reader.py | 发现与完整读取共用的有界头部读取 |
| integrations/skill_metadata_parser.py | YAML元数据解析与字段检查 |
| tools/skills/list_skills_tool.py | LangChain薄入口与公开字段组装 |
| config/settings.py | 提供已有PROJECT_ROOT定位；技能目录不属于Settings环境配置 |
| config/logging_config.py | 统一日志输出组装与级别控制，工具不承担日志文件管理 |
| tests/test_list_skills.py | JSON定义和真实目录结果验证 |

无新增Store、数据库或项目/会话模型。skill_id用于本地目录定位，不与资料source_id混用。

## 依赖记录

2026-11-04核对PyPI官方发布源：https://pypi.org/pypi/PyYAML/json 。最新稳定6.0.3；现有预发布中最高版本为6.0.2rc1，早于当前稳定版，无需采用。pyproject.toml直接声明pyyaml==6.0.3，uv.lock更新，本机安装6.0.3，Windows/Python当前环境导入和解析通过，uv pip check通过。PyYAML原本已是环境中的间接依赖，本次使直接使用关系显式化。

执行uv sync --locked时曾清理15个未声明的本地解析/OCR依赖，已按原版本恢复；未将它们加入本任务依赖声明。调试使用--no-sync避免再自动同步清理；正式可复现安装仍按项目规则使用uv sync --locked，未声明包不属于锁定环境。没有为IDE生成requirements.txt。

本次另外用临时目录放入一份真实技能介绍副本及一份缺少YAML头部的文件，验证后者产生WARNING且被忽略，前者仍正常返回；未改动用户技能目录。
