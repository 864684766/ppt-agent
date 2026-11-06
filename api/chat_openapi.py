"""对话接口的文档声明；运行时校验仍由chat_request_parser执行。

同一路径支持JSON和multipart，不能只使用一个普通Body模型表示。
此模块仅保存OpenAPI描述，不读取配置、处理文件或创建模型。
"""

from models.chat.chat_request import ChatRequest
from models.chat.chat_response import ChatErrorResponse


CHAT_RESPONSES = {
    code: {"model": ChatErrorResponse} for code in (400, 404, 413, 415, 422, 502, 503)
}
# JSON允许message/template_key；附件必须以multipart文件字段发送，不能塞入base64。
CHAT_REQUEST_BODY = {"requestBody": {"required": True, "content": {
    "application/json": {"schema": ChatRequest.model_json_schema()},
    "multipart/form-data": {"schema": {
        "type": "object", "required": ["message"], "additionalProperties": False,
        "properties": {
            "message": ChatRequest.model_json_schema()["properties"]["message"],
            "template_key": ChatRequest.model_json_schema()["properties"]["template_key"],
            "file": {"type": "string", "format": "binary", "description": "可选单个附件，附件统一作为参考资料；本阶段只返回读取结果，不调用模型。"},
        },
    }},
}}}
