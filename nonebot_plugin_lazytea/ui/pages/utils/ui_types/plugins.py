from typing import TypedDict, Optional, Dict


class PluginMetaInfo(TypedDict):
    name: Optional[str]
    """插件的显示名称"""
    description: str
    """插件描述（默认为“暂无描述”）"""
    homepage: Optional[str]
    """插件主页链接"""
    config_exists: bool
    """是否存在配置项"""
    author: str
    """插件作者"""
    version: str
    """插件版本"""
    icon_abspath: str
    """插件图标绝对路径"""
    pip_name: str
    """pip包名称"""
    ui_support:bool
    """是否支持ui显示"""
    html_exists: bool
    """是否支持html显示"""

    # extra


class PluginInfo(TypedDict):
    name: str
    """插件名称"""
    module: str
    """插件所在模块名"""
    meta: PluginMetaInfo
    """插件的元信息字典"""


class PluginHTML(TypedDict):
    html: str
    """html内容"""
    is_rendered: bool
    """是否已渲染"""
    context: Dict[str, str]
    """上下文"""
    includes: Dict[str, str]
    """外部文件"""
