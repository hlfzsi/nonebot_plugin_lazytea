from pydantic import BaseModel
from nonebot.plugin import get_loaded_plugins

from .server import Server
server = Server()


def json_config(config: BaseModel):
    schema = config.model_json_schema()
    data = config.model_dump()
    return {
        "schema": schema,
        "data": data
    }


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
                                      "author": "未知作者",
                                      "version": "未知版本",
                                      **(plugin.metadata.extra if plugin.metadata and plugin.metadata.extra else {}),
                                      }
                                 }
                   for plugin in plugins}

    return plugin_dict


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
