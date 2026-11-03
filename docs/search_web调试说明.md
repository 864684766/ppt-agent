# 第四个工具：search_web

状态（2026-11-03）：SearXNG适配器、配置读取、独立真实调用入口及JSON定义检查与真实搜索集成验证已完成。真实服务器使用sogou完成一次搜索，返回3条候选，其中包括https://dg.cnsoc.org/。HTTP接口、模型选工具循环、网页正文抓取不在本任务范围。

## 配置和运行

在根目录已有.env中增加以下配置，保留其他现有内容：

```dotenv
SEARXNG_BASE_URL=http://124.71.135.104:8082
SEARXNG_DEFAULT_ENGINES=sogou
SEARXNG_ALLOWED_ENGINES=sogou,bing,360search
WEB_SEARCH_TIMEOUT_SECONDS=30
```

服务地址不加/search，可含部署子路径；不填写server.secret_key。地址默认空，真实调用时未配置会明确报错。`SEARXNG_DEFAULT_ENGINES`是未指定本次引擎时的默认值；`SEARXNG_ALLOWED_ENGINES`是以后Agent工具参数允许选择的范围。允许列表只做配置边界，必须与服务器settings.yml中的name一致，不代表每个引擎当前可用。二者都用英文逗号分隔；空默认值使用服务器默认配置，允许列表不应为空。提示词将根据允许列表告诉模型范围，工具运行时仍需校验。本次工具尚未开放engines参数。超时为HTTP各阶段等待秒数，范围(0,120]，不是整个任务总时限。系统环境变量优先于.env，再使用Settings默认值。不会自动修改用户的.env。

从项目根目录运行真实搜索（会访问网络）：

```powershell
uv run --locked python -m examples.search_web_demo
```

PyCharm可将运行配置设为模块examples.search_web_demo，工作目录设为项目根目录。在示例的`result = await tool.ainvoke(arguments)`打断点，F8后查看result；修改arguments的query和max_results即可调试。服务地址通过配置修改，不修改测试网址。当前没有搜索HTTP接口，不为此增加Postman文件。

## 工具参数和输出

模型只传query和max_results，不选择服务器地址、引擎或超时。query去首尾空白后1–1000字符；max_results为1–10整数，默认5。每次只请求一次，不重试、不翻页、不扩词、不调用模型判断相关性。固定发送format=json、categories=general，配置非空时发送engines。

| 字段 | 含义与边界 |
| --- | --- |
| query | 本次实际搜索词，已去首尾空白，会发送给外部服务 |
| items | 本次候选网页列表；正常零命中时为空 |
| items[].candidate_id | web_加完整URL的SHA-256；用于比较候选，不是资料source_id，不能传给read_material |
| items[].title | 上游网页标题，缺失为空字符串，不代表内容已核实 |
| items[].url | 有效HTTP/HTTPS网页地址；尚未抓取正文 |
| items[].snippet | SearXNG的content搜索摘要，缺失为空字符串，不是完整正文 |
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
| integrations/searxng_search_client.py | HTTP请求、响应结构检查、SearXNG字段转换 |
| tools/web/search_web_tool.py | LangChain入口及公开输出组装 |
| config/settings.py | 环境变量读取 |
| examples/search_web_demo.py | 独立真实调用与资源组装，适合断点 |
| tests/test_search_web.py | JSON定义检查及读取配置的真实搜索集成验证 |

调用方拥有httpx.AsyncClient并通过async with关闭连接；适配器只借用。领域层不依赖Settings、HTTP库或LangChain。无新增包或升级，沿用uv.lock中的httpx等依赖。Tavily实现、依赖和密钥配置已移除。

SearXNG接口依据：[官方Search API](https://docs.searxng.org/dev/search_api.html)。latest镜像内容可能变化；本轮验证的是现有服务的接口行为，未读取服务器镜像digest。
