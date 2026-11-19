# 第四个工具：search_web

状态（2026-11-17）：搜索工具已供独立网页资料研究图调用；chat与网页正文核验尚未接入该图。资料收集测试仅保留tests/test_research_workflow.py中的test_real_research，运行会访问真实模型与搜索服务。

资料收集每轮均不传engines，由SearXNG的general分类选择引擎；结果不足时根据检查反馈调整搜索词。`max_attempts`是包含首轮的总搜索次数，达到目标数量或次数用尽即停止。当前测试入口需要读取真实模型和SearXNG。

资料不足时返回`awaiting_user`及`user_options`：有候选时可选`provide_materials`（补充资料）或`use_current`（使用当前候选）；有备用时还可选`use_alternatives`并传入选中的候选编号；所有不足场景均可选`end_conversation`（结束）。`apply_user_decision`接收实际选择并返回状态；当前没有chat接口接线、前端交互、资料上传后的自动恢复或持久化。搜索全部失败会在消息中明确说明；候选仍需读取正文核对。

**阅读代码的顺序：**先看 `tests/test_research_workflow.py` 如何创建模型、客户端和工具，再看 `workflows/web_research_workflow.py` 的 `run → _query → _review → _next`。查询Agent使用模型生成搜索词，由代码调用宿主注入的默认搜索工具；它目前不是 `create_agent` 自动选择工具。检查Agent只返回候选编号和反馈；图会过滤不存在的编号、按完整URL合并候选。需要观察某一轮时，可在图的 `_query`、`_review` 打断点。

`test_real_research` 的测试包装类会逐轮打印搜索策略、搜索词、候选与检查Agent输出，包括备用候选及原因；这些输出仅用于测试，不写入应用日志；最终结果另行输出图累计的备用候选。最后打印工作流的正式候选、状态、提示及用户选项。使用 `pytest -s` 或 PyCharm 的pytest运行器查看；运行会调用真实模型和搜索服务。

`tests/test_search_web.py` 中 `test_searxng_raw_response` 只发送q和format，打印服务器原始JSON，不截取也不经过工具，便于与相同参数的浏览器地址对照。`test_tool_return_result` 执行项目工具：引擎和语言由测试变量指定，服务端响应会被转换并按max_results（1至10）截取；两次独立请求可能因上游状态、网络或排序发生变化。原始结果可含图片和视频及其专有字段；工具只公开统一候选字段，不能视为完整媒体搜索结果。

2026-11-17实际运行六个主题（两次搜索、目标两条，使用bing与baidu kaifa）：膳食指南一条、本草纲目黄芪零条、劳动合同解除达到目标、身体活动建议达到目标、垃圾分类达到目标；Python官方文档初次因模型反馈超过长度限制失败，修改为接收后截取反馈，再单独重测，结果零条且bing本次连接失败。通过代表图运行结束，不能证明来源真实准确；博客候选尚需正文及权威性核查。


2026-11-19真实验证：黄芪案例使用真实模型与SearXNG，首轮完成，审核获得3条候选并按目标保留2条。另以真实模型的1 token输出上限人为触发审核超限，再将该次测试的审核模型额度调回至少4096，同实例恢复后完成，搜索次数仍为1。此验证不代表原4096额度下每次恢复都能成功。

### 内存检查点与恢复

每次调用 `run` 前生成唯一的 `thread_id`，同一 `WebResearchWorkflow` 实例内部的 `InMemorySaver` 在图节点结束后保存状态。若检查节点因模型输出超限失败，测试代码在同一个实例及HTTP连接仍有效时调用 `resume(thread_id=thread_id)` 一次；搜索成功后恢复不重搜，但失败的整个检查节点会重新执行，模型输出预算不会因此增加。再次失败仍抛出异常。

在 PyCharm 里运行 `test_real_research`，查看【任务编号】和【恢复】输出；需要人为触发错误才能观察恢复分支。检查点只在进程和该工作流实例存活时有效，重新运行测试或退出进程会丢失；不支持跨实例恢复、持久化、用户交互恢复或批次级恢复。`run` 不接受已经存在的编号，完成的任务和未知编号不能调用 `resume`。避免同一任务编号并发运行或恢复。

## 配置和运行

在根目录已有.env中增加以下配置，保留其他现有内容：

```dotenv
SEARXNG_BASE_URL=http://124.71.135.104:8082
SEARXNG_DEFAULT_ENGINES=sogou
WEB_SEARCH_TIMEOUT_SECONDS=30
```

服务地址不加/search；不填写server.secret_key。`SEARXNG_DEFAULT_ENGINES`为空时由服务器general分类选择；资料收集工作流每轮显式使用空引擎配置，不受`SEARXNG_DEFAULT_ENGINES`影响。本次工具的模型参数仍只有query和max_results，引擎由宿主绑定；系统环境变量优先于.env。

在 `tests/test_search_web.py` 文件顶部修改 `TEST_ENGINES`：`None`读取.env、`""`使用服务器默认、`"bing"`或`"baidu kaifa"`指定引擎。`TEST_LANGUAGE="zh-CN"`发送中文语言参数，设为空则由服务器决定；这两个变量只影响当前测试，不修改.env。修改 `arguments` 可改变搜索词与条数（最多10条）。

从项目根目录运行真实搜索（会访问网络）：

```powershell
uv run --locked python -m examples.search_web_demo
```

PyCharm可将运行配置设为模块examples.search_web_demo，工作目录设为项目根目录。在示例的`result = await tool.ainvoke(arguments)`打断点，F8后查看result；修改arguments的query和max_results即可调试。服务地址通过配置修改，不修改测试网址。当前没有搜索HTTP接口，不为此增加Postman文件。

## 工具参数和输出

工具参数为query和max_results，不选择服务器地址、引擎或超时；引擎由宿主组装客户端绑定。每次只请求一次，不重试、不翻页、不自行判断相关性。指定引擎时只发engines；未指定时发送categories=general，由服务器选择。两个Agent的独立图负责多轮搜索与摘要筛选。

| 字段 | 含义与边界 |
| --- | --- |
| query | 本次实际搜索词，已去首尾空白，会发送给外部服务 |
| items | 本次候选网页列表；正常零命中时为空 |
| items[].candidate_id | web_加完整URL的SHA-256；用于比较候选，不是资料source_id，不能传给read_material |
| items[].title | 上游网页标题，缺失为空字符串，不代表内容已核实 |
| items[].url | 有效HTTP/HTTPS网页地址；尚未抓取正文 |
| items[].snippet | SearXNG的content搜索摘要，缺失为空字符串，不是完整正文 |
| items[].engines | SearXNG实际报告的来源引擎名称列表；多个引擎合并时可能多项，缺失时为空列表 |
| returned_count | 实际items条数，可能小于max_results，不是全网结果总量 |

适配器保留上游顺序，跳过无效地址，按去首尾空白后的完整URL去重，再截取max_results条。不会移除查询参数；不进行语义过滤、权威性筛选或score阈值筛选。score不作为相似度返回。不会上传、解析或登记资料，不新建Store，Store结构未变化。

超时、连接失败、HTTP异常、非JSON、缺少results列表分别转换为安全工具错误，不暴露上游原文。没有可用候选且unresponsive_engines非空时报告引擎故障；有可用候选时仍返回候选，当前输出不包含部分引擎故障详情。取消不捕获，沿异步调用栈传播；取消和故障分支本轮未另做集成验证。

## JSON定义检查与真实搜索集成验证

按用户最新要求，tests/test_search_web.py已移除MockTransport、模拟响应和固定服务地址；两个测试都通过Settings读取.env及系统环境中的服务地址、默认引擎和超时。系统环境优先于.env。不打印整个Settings，避免泄露无关密钥。

```powershell
uv run --locked python -m pytest tests/test_search_web.py -s -q
```

2026-11-03实际结果：2 passed。第一项打印并检查tool-calling JSON，不发送请求；第二项实际调用配置的SearXNG，打印参数和真实结果，是依赖网络的集成验证，不再是离线单元测试。此次真实返回3条，其中包含食谱资料，也有不相关网页；通过仅说明接口和结果结构正常，不代表结果准确或相关。

在`result = await tool.ainvoke(arguments)`打断点，F8后查看result。query和max_results是本次查询输入，直接在arguments中修改；服务地址、默认引擎和超时只从Settings读取。真实结果会变化，不再与固定样本标题或网址比较，只检查查询词、条数和返回上限。正常零命中可通过；网络/配置/服务故障会导致测试失败，不自动切回模拟响应。

## 文件与依赖

| 文件 | 职责 |
| --- | --- |
| models/web/search_web_contract.py | 工具输入与公开输出契约 |
| models/web/web_search_candidate.py | 内部候选网页实体 |
| domain/web/web_search_contract.py | 可替换搜索接口与安全错误 |
| domain/web/web_search.py | 查询参数校验及一次业务调用 |
| integrations/web/searxng_search_client.py | HTTP请求、响应结构检查、SearXNG字段转换 |
| tools/web/search_web_tool.py | LangChain入口及公开输出组装 |
| config/settings.py | 环境变量读取 |
| examples/search_web_demo.py | 独立真实调用与资源组装，适合断点 |
| tests/test_search_web.py | JSON定义检查及读取配置的真实搜索集成验证 |

调用方拥有httpx.AsyncClient并通过async with关闭连接；适配器只借用。领域层不依赖Settings、HTTP库或LangChain。无新增包或升级，沿用uv.lock中的httpx等依赖。Tavily实现、依赖和密钥配置已移除。

SearXNG接口依据：[官方Search API](https://docs.searxng.org/dev/search_api.html)。latest镜像内容可能变化；本轮验证的是现有服务的接口行为，未读取服务器镜像digest。


SearchReview的alternatives包含候选编号及不满足要求原因，unmet_requirements说明本轮不足；图已按完整URL累计备用候选及原因；可通过apply_user_decision传入use_alternatives和alternative_ids选择，备用仍单独保存，真实用户交互尚未接入。
