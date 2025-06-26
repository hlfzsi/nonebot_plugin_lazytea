import asyncio
import ujson
from typing import Dict, Set, Type
from pydantic import BaseModel, ValidationError
from nonebot.plugin import get_loaded_plugins, get_plugin_by_module_name
from nonebot import get_plugin_config as nb_config

from .server import Server
from ..utils.config import _config
from .envhandler import EnvWriter
from ..utils.roster import FuncTeller

server = Server()


def json_config(config: Type[BaseModel]):
    schema = config.model_json_schema()
    model: BaseModel = nb_config(config)
    data = model.model_dump()
    return {
        "schema": schema,
        "data": data
    }


def ujson_default(obj):
    if isinstance(obj, Set):
        return list(obj)
    return "Error"


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
        new_config = config(**data)
        existed_config = nb_config(config)
    except ValidationError:
        return {"error": "Plugin config unmatched"}
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
