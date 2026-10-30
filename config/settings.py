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

    app_host: str = Field(default="127.0.0.1", min_length=1)
    app_port: int = Field(default=8000, ge=1, le=65535)

    # 当前几个任务共用一个代理；密钥使用 SecretStr 避免常规打印时泄露。
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""

    # 留空表示使用 llm_model；后续可独立替换每种任务的模型。
    llm_outline_model: str = ""
    llm_template_analysis_model: str = ""
    llm_ppt_generation_model: str = ""

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
