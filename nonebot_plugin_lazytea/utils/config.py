from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from nonebot import get_plugin_config


class Config(BaseModel):
    port: int = Field(8080, description="Nonebot实例占用的端口号")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "DEBUG", description="日志输出等级")
    token: str = Field(
        "疯狂星期四V我50", description="访问令牌,若未设置,LazyTea默认将其视作  疯狂星期四V我50")
    ui_token: Optional[str] = Field(None, description="用户界面访问令牌，优先级高于普通token")
    environment: Optional[str] = Field(..., description="当前配置文件环境")
    pip_index_url: str = Field(
        "https://pypi.tuna.tsinghua.edu.cn/simple", description="更新地址")

    def get_token(self) -> str:
        """
        返回当前配置中的有效令牌。
        如果UI令牌存在且非空，则优先返回UI令牌；否则返回普通令牌。
        :return: 有效的令牌字符串
        """
        return self.ui_token if self.ui_token else self.token

    def get_envfile(self) -> str:
        """
        返回当前配置的环境变量文件路径。
        :return: 环境变量文件的绝对路径
        """
        if self.environment:
            env_file = Path.cwd() / f".env.{self.environment}"
        else:
            env_file = Path.cwd() / ".env"

        env_file = env_file.resolve()

        if not env_file.exists():
            raise FileNotFoundError(
                f"Environment file {env_file} does not exist.")

        return str(env_file)

    @field_validator('port', mode='before')
    @classmethod
    def validate_port(cls, value):
        """
        验证并转换端口值。
        如果提供了字符串形式的端口号，则尝试将其转换为整数。
        """
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                raise ValueError(
                    "Port must be an integer or an integer in string format.")
        elif not isinstance(value, int):
            raise ValueError("Port must be an integer.")
        return value

    @field_validator('ui_token', mode='before')
    @classmethod
    def validate_ui_token(cls, value):
        """
        验证并转换ui_token。
        """
        if value is not None:
            try:
                return str(value)
            except ValueError:
                raise ValueError("ui_token must be a string")
        
    @field_validator('token', mode='before')
    @classmethod
    def validate_token(cls, value):
        """
        验证并转换token。
        """
        if value is not None:
            try:
                return str(value)
            except ValueError:
                raise ValueError("token must be a string")


_config = get_plugin_config(Config)
