from pydantic import BaseModel, Field

from typing import Callable, Union, Awaitable, Dict, Any


HTMLFunction = Callable[[], Union["PluginHTML", Awaitable["PluginHTML"]]]

class PluginHTML(BaseModel):
    html: str = Field(..., description="插件主页面")
    is_rendered: bool = Field(False, description="主页面是否已渲染")
    context: Dict[str, Any] = Field({}, description="渲染上下文, 必须可JSON化")
    includes: Dict[str, str] = Field(
        {}, description="单独的css/js文件, key为名称, value为内容")
