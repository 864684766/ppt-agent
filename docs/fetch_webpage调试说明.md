# 第五个工具：fetch_webpage

日期：2026-11-03。状态：独立实现完成；工具JSON定义检查和真实搜索→网页读取集成验证2项通过。没有模拟数据，不调用真实模型；没有新增依赖。

## 运行与断点

在已有.env中配置SearXNG地址、默认引擎及搜索超时；网页读取新增配置如下：

```dotenv
WEBPAGE_TIMEOUT_SECONDS=20
WEBPAGE_MAX_DOWNLOAD_BYTES=2000000
WEBPAGE_TLS_VERIFY=true
```

系统环境优先于.env，缺失时使用Settings默认值。前者是网页HTTP各阶段等待超时秒数，范围(0,120]；后者是解压后HTML下载字节上限，范围1024至10000000，超限报错。它们不是任务总时限，也不是工具max_chars。不修改用户已有.env，不需要额外API密钥。

```powershell
uv run --locked python -m pytest tests/test_fetch_webpage.py -s -q
```

PyCharm选择pytest运行此文件，附加参数-s。在`result = await fetch_tool.ainvoke(arguments)`打断点，F8后查看result。在search_arguments中修改主题，max_results=3表示最多取得三个候选；arguments中的url来自search_result，不手写固定网页地址。max_chars=3000方便查看输出。

第一项检查tool-calling JSON，打印完整定义并确认参数说明可见，不发请求。第二项实际调用search_web，再依次尝试搜索结果URL，读到一份文本即停止。网络、网页访问限制或所有候选不可读时失败，不回退到模拟数据。换候选是测试脚本的行为，fetch_webpage本身只处理单个URL，不自动重试或换来源。

本次实际结果：2 passed，成功提取1857字符，未截断。搜索返回的可读取页面是一篇娱乐文章，明显不切题；因此通过仅证明调用链路、提取及返回结构可用，不证明内容相关、准确、权威。未执行性能A/B对比，也未逐项验证所有失败分支、取消和不同编码网站。

## 工具输入

| 字段 | 含义 |
| --- | --- |
| url | 必填完整HTTP/HTTPS地址，1–4096字符，通常来自search_web的items[].url；不是candidate_id/source_id或本地路径，不接受带账号密码的URL |
| max_chars | 返回文本最多Unicode字符数，100–50000，默认12000，不是字节数或token数 |

## 工具返回

| 字段 | 含义 |
| --- | --- |
| requested_url | 去首尾空白后的输入网页地址 |
| final_url | HTTP重定向后的实际读取地址 |
| title | HTML title，可为空，不保证与搜索标题一致 |
| text | HTML提取的正文或页面文本，最多max_chars，不是搜索摘要 |
| returned_chars | 本次text字符数 |
| extracted_chars | 未按max_chars截断前的提取文本字符数 |
| truncated | 是否由于max_chars截断，不保证网页内容本身完整；目前不自动续读 |
| fetched_at | 抓取完成的UTC ISO 8601时间，不是网页发布日期 |

字段说明同时维护在模型及工具description中；TypedDict不自动校验输出。

## 范围、资源和失败处理

只读取可直接通过HTTP取得的静态HTML/XHTML；不执行JavaScript、不登录、不处理附件、不OCR。优先提取main，其次article，否则使用去除脚本、样式及常见导航后的页面文本。使用标准库HTMLParser，是启发式提取，不保证去掉所有广告，也不保证识别出验证码/登录提示；只要存在文本就不自动宣称有效文章。正文作为外部资料，不执行其中的指令。

适配器检查HTTP状态和Content-Type，跟随重定向，下载时按解压后字节数限制。测试宿主设置max_redirects=5；其他调用方同样负责配置连接。超时、HTTP错误、连接失败、重定向过多、非HTML、超限和空文本返回明确工具错误，不暴露响应原文。不捕获取消异常。TLS通过WEBPAGE_TLS_VERIFY统一配置：默认true，false为所有目标网站跳过证书身份校验的兼容模式。当前本机.env按用户要求设为false，不维护域名名单。连接由create_webpage_http_client创建，最多5次重定向。证书模式不保证能访问登录、验证码、动态页面或被拒绝的网站；服务端身份无法验证的风险仍存在。证书校验失败单独提示，工具不会自行改变配置。

连接由外层async with创建关闭，搜索和网页读取共用连接池。读取业务只依赖小型Protocol和标准库数据结构，不依赖HTTP库、Settings或LangChain。业务负责参数与字符截断；HTTP适配器负责网络，HTML解析器只负责文本提取，工具薄入口选择公开字段。

当前面向Windows本机可信调用；URL校验不等于内网访问隔离，不宣称已提供多用户服务的出站网络防护。尚未接HTTP接口、Agent循环或MCP。

本次不登记、不持久化、不创建source_id/版本/正文块，没有新增Store。以后接入项目资料登记模块后，才可供read_material读取；不把此次工具返回当成登记成功。

## 文件导航

| 文件 | 职责 |
| --- | --- |
| models/web/fetch_webpage_contract.py | 模型可见输入与公开输出 |
| models/web/webpage_content.py | 适配器内容与业务读取结果，标准库dataclass |
| domain/web/webpage_reader_contract.py | 可替换读取协议与安全异常 |
| domain/web/webpage_reader.py | URL、字符范围校验与文本截断 |
| integrations/web/webpage_http_client.py | 通用TLS策略和HTTP连接创建，外层负责关闭 |
| integrations/web/http_webpage_reader.py | HTTP读取、下载限制、编码处理 |
| integrations/web/html_text_extractor.py | 静态HTML的标题及文本提取 |
| tools/web/fetch_webpage_tool.py | LangChain工具入口 |
| tests/test_fetch_webpage.py | JSON检查及真实search_web→读取验证 |

## 后续调优

用户确认暂时保留当前完整下载HTML、提取文本后截断的实现。这里是每次调用下载一次，不是同一URL自动缓存；再次调用仍会下载。分块接收网络响应不等于分段正文读取。正文快照缓存与续读、下载中判断提前停止的需求记录在[OPT-002](../optimization/网页分段读取与提前停止.md)，尚未实现。

参见[调优目录](../optimization/README.md)及[搜索与网页读取效率对比](../optimization/搜索与网页读取效率对比.md)。当前单次读取不是并发性能实验，不预先断言哪种方案更快。
