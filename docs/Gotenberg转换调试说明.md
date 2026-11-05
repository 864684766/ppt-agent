# Gotenberg PPTX转PDF模块

本模块只完成PPTX→PDF，不生成页面图片、不调用视觉模型、不增加Agent工具或HTTP接口。
本机不需要安装LibreOffice，由配置的Gotenberg服务器负责转换；服务器字体会影响排版。

## 在PyCharm中测试

打开tests/test_gotenberg_converter.py，点击test_convert_real_pptx_to_pdf左侧图标选择Debug。
pytest附加参数填写-s，工作目录设置为项目根目录。测试读取ppt-demo的全部一级.pptx，
忽略以~$开头的锁文件。仅测试一份文件时，在测试内将templates改为指定Path的列表。

```powershell
uv run --locked --no-sync python -m pytest tests/test_gotenberg_converter.py -s -q
```

测试是真实集成验证，会把样本上传至Gotenberg，不使用模拟数据、不调用LLM。
在`pdf_bytes = await converter.convert(...)`处打断点，单步可进入请求和返回格式检查。
PDF输出到data/gotenberg-test/日期时间-随机后缀/原文件名.pdf，测试打印绝对路径。
每次输出独立目录，不覆盖原PPT或上次结果，不自动清理历史输出；data不纳入Git。

打开PDF对照原PPT检查：页数是否符合预期，中文是否缺字，标题/正文是否换行异常，
图片是否缺失及页面是否错位。当前没有PDF解析库，因此未自动计算页数，人工检查不能省略。
测试通过只证明转换接口、基本PDF格式、落盘和原文件未修改，不证明视觉完全一致。

## 配置

在.env填写：

```dotenv
GOTENBERG_BASE_URL=http://124.71.135.104:8083
GOTENBERG_TIMEOUT_SECONDS=120
```

系统环境优先于.env。地址默认空，空值不能创建转换器；根地址不加/health或转换接口。
超时默认120秒，范围(0,600]，不能留空。此值限制客户端各阶段等待，不是整个任务总时限，
也不能更改Gotenberg服务端API超时。服务端若先超时，需要另行调整服务端设置。

## 调用和代码职责

```python
async with httpx.AsyncClient() as client:
    converter = GotenbergPdfConverter(
        client=client, base_url=base_url, timeout_seconds=120,
    )
    pdf_bytes = await converter.convert(
        pptx_bytes=pptx_bytes, file_name="模板.pptx",
    )
```

- domain/templates/presentation_pdf_converter_contract.py：协议PresentationPdfConverter和安全错误PresentationConversionError。调用方可依赖该协议替换转换实现。
- integrations/templates/gotenberg_converter.py：GotenbergPdfConverter具体实现。构造时检查地址和超时；convert检查非空PPTX内容及纯文件名，上传后返回bytes。
- tests/test_gotenberg_converter.py：读取Settings和样本，创建/关闭HTTP客户端，调用转换器并保存PDF。

输入pptx_bytes是原文件字节，不是路径；file_name是含.pptx后缀的纯文件名，不允许目录、换行。
输出只有PDF原始bytes，没有新增实体或工具契约。谁读取文件、创建HTTP客户端，谁负责文件保存和连接关闭。
转换器不读取.env、不访问测试目录、不写磁盘；multipart的files字段由接口要求，Content-Type及boundary由httpx生成。

适配器向根地址拼接/forms/libreoffice/convert，只发送一次请求，不自动重试、不自动追随重定向。
HTTP错误只公开状态码，不泄露响应正文；超时和网络错误转为PresentationConversionError。
成功响应需具备application/pdf媒体类型、%PDF-文件头和末尾1024字节内的%%EOF标记。
这些是基本检查，不代替PDF解析及视觉验收。

取消信号正常传播；客户端取消不保证远程转换立即停止。当前整份PPTX和PDF放在内存中，
不实现大文件流式处理、并发调度或自动队列重试。后续有实际需求再增加限制和调优。

本次沿用已锁定httpx和pytest依赖，无安装或升级。PDF→逐页图片是下一项独立任务。

## 本次实际结果

2026-11-05真实集成验证：tests/test_gotenberg_converter.py为1 passed（8.41秒）。样本黄色活泼卡通幼儿通用PPT.pptx输入1428620字节，返回PDF为1227478字节，输出data/gotenberg-test/20261105-143304-dd0bceab/黄色活泼卡通幼儿通用PPT.pdf。基本PDF检查、文件落盘与原文件hash不变验证通过；未自动读取PDF页数，字体及版式一致性待用户打开核对。
