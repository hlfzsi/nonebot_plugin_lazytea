import asyncio
import os
from pathlib import Path
import sys
import subprocess
from importlib.resources import files, as_file

from nonebot import get_driver, require
require("nonebot_plugin_localstore")
require("nonebot_plugin_session")
from nonebot.drivers import ASGIMixin, WebSocket, WebSocketServerSetup, URL
from nonebot.plugin import PluginMetadata

from .utils.config import _config as config
from .utils.config import Config
from .utils.commute import server_send_queue
from .ipc import server, Server
from .bridge import for_import as _

import nonebot_plugin_localstore    # noqa

__version__ = "0.0.1b1"
__author__ = "hlfzsi"

try:
    resource_ref = files(__package__).joinpath("ui", "resources", "app.ico")
    with as_file(resource_ref) as icon_file:
        _icon_path = str(icon_file) if icon_file.is_file() else ""
except Exception:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)  # type: ignore
        _icon_path = str(base_path / "ui" / "resources" / "app.ico")
        if not Path(_icon_path).is_file():
            _icon_path = ""
    else:
        base_path = Path(__file__).parent
        _icon_path = str(base_path / "ui" / "resources" / "app.ico")
        if not Path(_icon_path).is_file():
            _icon_path = ""
    del base_path


__plugin_meta__ = PluginMetadata(
    name="LazyTea",
    description="今天也来杯红茶吗?",
    usage="开箱即用!",
    type="application",
    homepage="https://github.com/hlfzsi/nonebot_plugin_lazytea",
    config=Config,

    extra={
        "version": __version__,  # 用于在插件界面中显示版本与版本更新检查
        "author": __author__,   # 用于在插件界面中显示作者
        "icon_abspath": _icon_path  # 用于在插件界面中自定义插件图标 ，仅支持绝对路径
    }
)


driver = get_driver()
ui_process = None


@driver.on_startup
async def pre():
    async def websocket_endpoint(ws: WebSocket):
        await server.start(ws, config.get_token())
    if isinstance(driver, ASGIMixin):
        driver.setup_websocket_server(
            WebSocketServerSetup(
                path=URL("/plugin_GUI"),
                name="ui_ws",
                handle_func=websocket_endpoint,
            )
        )
    global ui_process
    script_dir = Path(__file__).parent.resolve()
    ui_env = os.environ.copy()
    ui_env["PORT"] = str(config.port)
    ui_env["TOKEN"] = str(config.get_token())
    ui_env["UIVERSION"] = __version__
    ui_env["UIAUTHOR"] = __author__
    ui_env["PIP_INDEX_URL"] = str(config.pip_index_url)
    ui_env["LOGLEVEL"] = config.log_level
    ui_env["UIDATADIR"] = str(
        nonebot_plugin_localstore.get_data_dir("LazyTea"))

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
