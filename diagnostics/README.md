# 诊断基础设施

- log_context.py：ContextVar请求/操作编号和日志过滤器；不承载业务会话。
- operation_logging.py：安全错误位置提取、操作作用域及同步/协程/异步生成器日志装饰器；不读取环境配置或函数参数。
- config/logging_config.py：配置处理器、级别与每日文件，由应用/pytest/独立脚本入口调用。
- api/request_logging_middleware.py：HTTP协议专属接入，创建请求编号并记录响应结果，不放进通用诊断模块。

依赖方向为API/工具/外部适配器→诊断；诊断不反向依赖API、业务实体、LangChain或Settings。纯业务函数和校验器不依赖诊断，由调用边界记录其失败。

用法、字段、排查示例和边界见[日志使用说明](../docs/日志使用说明.md)。
