from typing import TypedDict, Optional


class PluginMetaInfo(TypedDict):
    name: Optional[str]
    """插件的显示名称"""
    description: str
    """插件描述（默认为“暂无描述”）"""
    homepage: Optional[str]
    """插件主页链接"""
    config_exist: bool
    """是否存在配置项"""
    author: str
    """插件作者"""
    version: str
    """插件版本"""
    icon_abspath: str
    """插件图标绝对路径"""
    # extra


class PluginInfo(TypedDict):
    name: str
    """插件名称"""
    module: str
    """插件所在模块名"""
    meta: PluginMetaInfo
    """插件的元信息字典"""
