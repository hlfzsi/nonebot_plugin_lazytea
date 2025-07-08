from nonebot import get_driver, require
require("nonebot_plugin_localstore")  # noqa
require("nonebot_plugin_session")  # noqa


from .bridge import for_import as _  # noqa
from .ipc import server, Server  # noqa
from .utils.commute import server_send_queue  # noqa
from .utils.config import Config  # noqa
from .utils.config import _config as config  # noqa
from nonebot_plugin_session import __plugin_meta__ as sspm  # noqa
from nonebot.plugin import PluginMetadata, inherit_supported_adapters  # noqa
from nonebot.drivers import ASGIMixin, WebSocket, WebSocketServerSetup, URL  # noqa
import asyncio  # noqa
import os  # noqa
from pathlib import Path  # noqa
import sys  # noqa
from importlib.resources import files, as_file  # noqa


import nonebot_plugin_localstore    # noqa

__version__ = "0.0.1b3"
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
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_session", "nonebot_plugin_localstore"),

    extra={
        "version": __version__,  # 用于在插件界面中显示版本与版本更新检查
        "author": __author__,   # 用于在插件界面中显示作者
        "icon_abspath": _icon_path  # 用于在插件界面中自定义插件图标 ，仅支持绝对路径
    }
)


driver = get_driver()
ui_process = None
send_task = None


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
    global ui_process, send_task
    script_dir = Path(__file__).parent.resolve()
    ui_env = os.environ.copy()
    ui_env["PORT"] = str(config.port)
    ui_env["TOKEN"] = str(config.get_token())
    ui_env["UIVERSION"] = __version__
    ui_env["UIAUTHOR"] = __author__
    ui_env["LOGLEVEL"] = str(config.log_level)
    ui_env["UIDATADIR"] = str(
        nonebot_plugin_localstore.get_data_dir("LazyTea"))

    ui_process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "ui.main_window",
        cwd=script_dir,
        env=ui_env,
    )

    async def send_data(server: Server, queue: asyncio.Queue):
        try:
            while True:
                type, data = await queue.get()
                await server.broadcast(type, data)
        except asyncio.CancelledError:
            pass

    send_task = asyncio.create_task(send_data(server, server_send_queue))


@driver.on_shutdown
async def cl():
    global send_task
    if send_task:
        send_task.cancel()

    if ui_process:
        try:
            ui_process.kill()
        except:
            pass
