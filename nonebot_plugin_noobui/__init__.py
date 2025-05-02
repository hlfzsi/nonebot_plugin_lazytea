import asyncio
import os
from pathlib import Path
import sys
import subprocess
from typing import Optional

import fastapi
from pydantic import BaseModel, Field, field_validator
from nonebot import get_driver, get_plugin_config, get_app
from nonebot.plugin import PluginMetadata

from .utils.commute import server_send_queue
from .ipc import server, Server
from .bridge import for_import as _

__version__ = "0.0.1a1"
__author__ = "hlfzsi"


class Config(BaseModel):
    port: int = Field(8080, description="Nonebot实例占用的端口号")
    token: str = Field("疯狂星期四V我50", description="访问令牌")
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


__plugin_meta__ = PluginMetadata(
    name="NOOB_UI",
    description="菜鸟也能用的UI,以小而美为目标",
    usage="开箱即用!",
    type="application",
    homepage="https://github.com/hlfzsi/nonebot_plugin_NoobUI",
    config=Config,

    extra={
        "version": __version__,
        "author": __author__,
    }
)


driver = get_driver()
ui_process = None
config = get_plugin_config(Config)
app: fastapi.FastAPI = get_app()


@driver.on_startup
async def pre():
    @app.websocket("/plugin_GUI")
    async def websocket_endpoint(ws: fastapi.WebSocket):
        await server.start(ws, config.get_token())
    global ui_process
    script_dir = Path(__file__).parent.resolve()
    ui_env = os.environ.copy()
    ui_env["PORT"] = str(config.port)
    ui_env["TOKEN"] = str(config.get_token())
    ui_env["ENVFILE"] = str(config.get_envfile())
    ui_env["UIVERSION"] = __version__
    ui_env["UIAUTHOR"] = __author__
    ui_env["PIP_INDEX_URL"] = str(config.pip_index_url)

    ui_process = subprocess.Popen(
        [sys.executable, "-m", "ui.main_window"],
        cwd=script_dir,
        env=ui_env)

    async def send_data(server: Server, queue: asyncio.Queue):
        while True:
            type, data = await queue.get()
            await server.broadcast(type, data)
    asyncio.create_task(send_data(server, server_send_queue))


@driver.on_shutdown
async def cl():
    if ui_process and ui_process.poll() is None:
        ui_process.kill()
