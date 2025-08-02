import asyncio
import importlib
import sys
import ujson
from typing import Any, Dict, List, Set, Type, Union, get_origin
from pydantic import BaseModel, ValidationError
from nonebot.plugin import get_loaded_plugins, get_plugin_by_module_name
from nonebot import get_plugin_config as nb_config, logger

from .server import Server
from ..utils.config import _config
from ..utils.commute import bot_off_line
from .envhandler import EnvWriter
from ..utils.roster import FuncTeller

server = Server()
# 确保 pip 检查和安装过程不会并发执行的锁
_pip_check_lock = asyncio.Lock()
# 标记 pip 是否已确认可用
_pip_available = False
# 存储当前正在进行更新的插件名称
_active_updates: Set[str] = set()
# 保护对 _active_updates 集合的并发读写操作
_active_updates_lock = asyncio.Lock()


def json_config(config: Type[BaseModel]):
    schema = config.model_json_schema()
    model: BaseModel = nb_config(config)
    data = model.model_dump_json()
    return {
        "schema": schema,
        "data": data
    }


def ujson_default(obj):
    if isinstance(obj, Set):
        return list(obj)
    return "Error"


async def _ensure_pip_is_available() -> bool:
    """
    一个内部函数，用于实际执行 `ensurepip` 命令来确保 pip 可用。
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "ensurepip", "--upgrade",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    return process.returncode == 0


def _preprocess_data_for_coercion(data: Dict[str, Any], model: Type[BaseModel]) -> Dict[str, Any]:
    """
    在Pydantic验证前预处理数据
    """
    processed_data = data.copy()
    model_fields = model.model_fields

    for key, field_info in model_fields.items():
        if key not in processed_data:
            continue

        value = processed_data[key]
        origin_type = get_origin(field_info.annotation)

        if type(value) == origin_type:
            continue

        if isinstance(value, str) and value.strip().lower() == 'none':
            processed_data[key] = None
            continue

        try:
            processed_data[key] = ujson.loads(value)
        except (ValueError, TypeError):
            pass

        current_value = processed_data[key]

        if origin_type is list and isinstance(current_value, set):
            processed_data[key] = list(current_value)
        elif origin_type is set and isinstance(current_value, list):
            processed_data[key] = set(current_value)

    return processed_data


@server.register_handler(method="get_plugins")
def get_plugins():
    plugins = get_loaded_plugins()
    plugin_dict = {plugin.name: {"name": plugin.name,
                                 "module": plugin.module_name,
                                 "meta":
                                     {"name": plugin.metadata.name if plugin.metadata else None,
                                      "description": plugin.metadata.description if plugin.metadata else "暂无描述",
                                      "homepage": plugin.metadata.homepage if plugin.metadata else None,
                                      "config_exist": True if plugin.metadata and plugin.metadata.config else False,
                                      "icon_abspath": "",
                                      "author": "未知作者",
                                      "version": "未知版本",
                                      **(plugin.metadata.extra if plugin.metadata and plugin.metadata.extra else {}),
                                      }
                                 }
                   for plugin in plugins}

    plugin_json = ujson.dumps(plugin_dict, default=ujson_default)
    return ujson.loads(plugin_json)


@server.register_handler(method="get_plugin_config")
def get_plugin_config(name: str):
    """
    获取插件配置项
    :param name: 插件名称
    :return: 插件配置项
    """
    plugins = get_loaded_plugins()
    plugin = next((plugin for plugin in plugins if plugin.name == name), None)
    if plugin is None:
        return {"error": "Plugin not found"}

    if plugin.metadata and plugin.metadata.config:
        return json_config(plugin.metadata.config)

    return {"error": "Plugin config not found"}


@server.register_handler("save_env")
async def save_env(module_name: str, data: Dict):
    plugin = get_plugin_by_module_name(module_name)
    if not plugin:
        return {"error": "Plugin not found"}
    plugin_name = plugin.name

    config = plugin.metadata.config if plugin.metadata else None
    if not config:
        return {"error": "Plugin config not found"}
    try:
        coerced_data = _preprocess_data_for_coercion(data, config)
        new_config = config(**coerced_data)
        existed_config = nb_config(config)
    except ValidationError:
        import traceback
        return {"error": f"Plugin config unmatched \n {traceback.format_exc()}"}
    else:
        writer = EnvWriter(plugin_name)
        await writer.write(new_config, existed_config, _config.get_envfile())
        handler = server.handlers.get(plugin.name) or server.handlers.get(
            plugin.metadata.name if plugin.metadata else "")
        if handler:
            if asyncio.iscoroutinefunction(handler):
                asyncio.create_task(handler(new_config))
            else:
                asyncio.create_task(asyncio.to_thread(handler(new_config)))
        return True


@server.register_handler("get_matchers")
async def get_matchers():
    """获取所有插件的匹配器信息"""
    return await FuncTeller.get_model()


@server.register_handler("sync_matchers")
async def sync_matchers(new_roster: str):
    await FuncTeller.sync(new_roster)


@server.register_handler("update_plugin")
async def update_plugin(plugin_name: str) -> Union[str, Dict[str, str]]:
    """
    异步处理插件更新请求。
    """
    global _pip_available
    if not _pip_available:
        async with _pip_check_lock:
            if not _pip_available:
                if await _ensure_pip_is_available():
                    _pip_available = True
                else:
                    return {"error": "当前环境缺少 pip，尝试自动安装失败！请手动运行 python -m ensurepip --upgrade"}

    async with _active_updates_lock:
        if plugin_name in _active_updates:
            return {"error": f"插件 {plugin_name} 的更新已在进行中，已忽略本次重复请求。"}
        _active_updates.add(plugin_name)

    try:
        pip_index_url = _config.pip_index_url
        command = [
            sys.executable, "-m", "pip", "install", "--upgrade",
            plugin_name, "--index-url", pip_index_url,
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return f"插件 {plugin_name} 更新成功！\n{stdout.decode(errors='ignore')}"
        else:
            return {"error": f"插件 {plugin_name} 更新失败！\n{stderr.decode(errors='ignore')}"}
    finally:
        async with _active_updates_lock:
            _active_updates.discard(plugin_name)


@server.register_handler("ui_load")
def ui_load(plugins_to_load: List):
    for plugin_name in plugins_to_load:
        try:
            module_path = f"{plugin_name}.__call__"
            importlib.import_module(module_path)
            logger.debug(f"成功导入{module_path}")
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"导入{plugin_name}.__call__ 时出现错误{e}")
            continue


@server.register_handler("bot_switch")
def bot_switch(bot_id: str, platform: str, is_online_now: bool):
    if is_online_now:
        bot_off_line[platform].discard(bot_id)
    else:
        bot_off_line[platform].add(bot_id)
