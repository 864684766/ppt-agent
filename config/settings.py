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
    # PPT生成任务模型，空值回退llm_model；Harness业务尚未接线。
    llm_ppt_generation_model: str = ""

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
