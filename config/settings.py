"""集中读取配置；系统环境变量优先于项目根目录的 .env 文件。"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# 使用绝对路径，避免 IDE 的工作目录变化导致读取另一份 .env。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ModelTask = Literal["outline", "template_analysis", "ppt_generation"]


class Settings(BaseSettings):
    """应用启动和模型路由配置。

    环境变量名与字段名对应，例如 app_port 对应 APP_PORT。
    模型和密钥在接入模型时使用，当前启动健康服务无需填写。
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        str_strip_whitespace=True,
    )

    # 服务监听地址，默认127.0.0.1；python main.py启动时使用，对应APP_HOST。
    app_host: str = Field(default="127.0.0.1", min_length=1)
    # 服务监听端口，默认8000，范围1–65535；对应APP_PORT。
    app_port: int = Field(default=8000, ge=1, le=65535)

    # 应用日志最低级别；对应LOG_LEVEL，修改后重启服务或重新运行测试生效。
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志最低级别，使用大写；默认INFO，记录所选级别及更严重的日志。",
    )
    # 应用日志输出目标；对应LOG_OUTPUT，独立于最低日志级别。
    log_output: Literal["file", "console", "both"] = Field(
        default="both",
        description="日志输出：file仅文件，console仅控制台标准错误，both两者；默认both。",
    )

    # 上传原文件的实际字节上限；20 MiB=20×1024×1024字节，不是2000万字节。
    upload_max_file_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024,
        description="单文件上传上限，单位字节，默认20 MiB，范围1 KiB–100 MiB；不代表解析后的内存占用。",
    )
    # DOCX/XLSX/PPTX均是ZIP容器，还要限制展开规模，不能只看上传大小。
    upload_max_uncompressed_bytes: int = Field(
        default=100 * 1024 * 1024, ge=1024, le=1024 * 1024 * 1024,
        description="DOCX/XLSX/PPTX所有ZIP条目累计解压上限，单位字节，默认100 MiB，范围1 KiB–1 GiB。",
    )

    # 附件读取结果与遍历规模上限，避免把很长文件无限装入响应或模型上下文。
    document_max_characters: int = Field(default=200000, ge=1, le=2000000, description="单附件读取结果累计字符上限，默认20万；超限明确失败，不静默截断。")
    document_max_blocks: int = Field(default=5000, ge=1, le=20000, description="单附件检查的段落/表格行/页面等单元上限，默认5000，包含空单元。")
    document_max_cells: int = Field(default=100000, ge=1, le=1000000, description="单附件累计遍历表格单元格上限，默认10万，包含空单元格。")

    # S3兼容对象存储：当前用于RustFS模板目录，具体连接只在接口请求时建立。
    s3_endpoint_url: str = Field(default="", description="RustFS的S3 API根地址，如http://host:8081；不是管理控制台，空值时模板列表503。")
    s3_template_bucket: str = Field(default="ppts", min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$", description="模板所在桶名，默认ppts，服务端固定配置；HTTP调用方不能任意切换。")
    s3_access_key_id: SecretStr = Field(default=SecretStr(""), description="RustFS访问密钥ID，与Secret配对；两者均空则匿名，不使用AWS默认凭据链。")
    s3_secret_access_key: SecretStr = Field(default=SecretStr(""), description="RustFS访问密钥Secret，仅后端保存，不返回前端；两者均空则匿名。")
    s3_template_max_file_bytes: int = Field(
        default=50 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024,
        description="OSS模板下载与解析原文件上限，默认50 MiB，范围1 KiB–200 MiB；与普通上传20 MiB分开，Office展开及正文读取上限仍独立生效。",
    )
    s3_region: str = Field(default="us-east-1", min_length=1, description="S3签名区域，默认us-east-1；按RustFS配置填写，不是物理部署位置推断。")
    s3_timeout_seconds: float = Field(default=20, gt=0, le=120, description="S3连接/读取阶段超时秒数，默认20，范围(0,120]；单次请求不自动重试，不是HTTP端到端总时限。")

    # 当前几个任务共用一个代理；密钥使用 SecretStr 避免常规打印时泄露。
    # OpenAI兼容代理基础地址，空值表示未配置；对应LLM_BASE_URL。
    llm_base_url: str = ""
    # 模型代理密钥，空值表示未配置；SecretStr遮蔽常规输出，对应LLM_API_KEY。
    llm_api_key: SecretStr = SecretStr("")
    # 默认模型名称，空值表示未配置；当前单轮聊天使用，对应LLM_MODEL。
    llm_model: str = ""
    # 单次模型请求超时（秒）与输出 token 上限；不等同于输入字符数。
    # 单次模型请求超时秒数，默认60、范围(0,600]；不是整个任务总时限。
    llm_timeout_seconds: float = Field(default=60, gt=0, le=600)
    # 最大输出token数，默认1024、范围1–32768；仍受模型实际限制。
    llm_max_tokens: int = Field(default=1024, ge=1, le=32768)

    # 留空表示使用 llm_model；后续可独立替换每种任务的模型。
    # 大纲任务模型，空值回退llm_model；业务尚未接线。
    llm_outline_model: str = ""
    # 模板识别模型，空值回退llm_model；业务尚未接线，名称不保证视觉能力。
    llm_template_analysis_model: str = ""
    # 图片理解模型，供当前视觉模块真实图片测试使用；尚未接入Harness。
    llm_vision_model: str = Field(
        default="glm-5.3-flash", min_length=1,
        description="视觉识别模型名称，默认glm-5.3-flash；代理与密钥沿用LLM连接配置。",
    )
    # PPT生成任务模型，空值回退llm_model；Harness业务尚未接线。
    llm_ppt_generation_model: str = ""

    # Gotenberg服务根地址，对应GOTENBERG_BASE_URL；不是转换接口的完整路径。
    # 空字符串表示未配置。真实转换测试读取后注入适配器，启动服务不自动转换。
    gotenberg_base_url: str = Field(
        default="",
        description="Gotenberg HTTP(S)服务根地址，不含/forms/libreoffice/convert；默认空，真实转换测试使用。",
    )
    # Gotenberg客户端HTTP各阶段等待上限（秒）；与服务端API超时分别设置。
    gotenberg_timeout_seconds: float = Field(
        default=120, gt=0, le=600,
        description="Gotenberg转换HTTP等待超时秒数，默认120，范围(0,600]；不是整体转换时限。",
    )

    # SearXNG根地址，空值表示未配置；仅在外层创建搜索适配器时使用。
    searxng_base_url: str = Field(default="", description="SearXNG服务根地址，留空不启用。")
    # 普通网页默认引擎name，英文逗号分隔；空值使用服务器默认引擎。
    searxng_default_engines: str = Field(default="sogou", description="普通网页引擎名称，默认sogou。")
    # 预留的Agent可选普通网页引擎name，英文逗号分隔；尚未接入工具参数校验。
    # 它不是服务器全部引擎清单，必须与SearXNG settings.yml中已启用的name一致。
    searxng_allowed_engines: str = Field(
        default="sogou,bing,360search",
        description="Agent可选择的普通网页引擎名称，英文逗号分隔。",
    )
    # HTTP各阶段等待超时秒数，默认30、范围(0,120]；不是整个任务时限。
    web_search_timeout_seconds: float = Field(default=30, gt=0, le=120)

    # 读取网页的HTTP各阶段超时秒数，与SearXNG搜索超时分别配置。
    webpage_timeout_seconds: float = Field(default=20, gt=0, le=120)
    # 解压后HTML下载字节上限，默认200万，范围1024至1000万；不是max_chars。
    webpage_max_download_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)
    # 网页HTTPS证书校验开关：默认True；False跳过全部目标的证书身份校验。
    # 只控制外层连接策略，模型不能通过工具参数修改，不保证所有网站均可读。
    webpage_tls_verify: bool = Field(default=True, description="是否校验网页HTTPS证书，默认开启。")

    def get_searxng_allowed_engines(self) -> tuple[str, ...]:
        """返回去空白、去重后的Agent可选搜索引擎名称。

        该方法只解析配置，不检查远端SearXNG当前是否启用；远端可用性需要
        在真实搜索时由适配器或手工验证确认。返回元组避免调用方意外修改配置结果。
        """
        names = (name.strip() for name in self.searxng_allowed_engines.split(","))
        return tuple(dict.fromkeys(name for name in names if name))

    def get_model(self, task: ModelTask) -> str:
        """返回任务专用模型，未配置时退回默认模型。

        Args:
            task: 大纲、模板识别或 PPT 生成任务。

        Returns:
            去掉首尾空白后的模型名称。

        Raises:
            ValueError: 任务不支持，或任务模型和默认模型均未配置。
        """
        task_models = {
            "outline": self.llm_outline_model,
            "template_analysis": self.llm_template_analysis_model,
            "ppt_generation": self.llm_ppt_generation_model,
        }
        if task not in task_models:
            raise ValueError(f"不支持的模型任务：{task}")

        model = task_models[task] or self.llm_model
        if not model:
            raise ValueError(f"请为任务 {task} 配置专用模型或 LLM_MODEL")
        return model
