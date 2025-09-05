from typing import Dict

from .ipc import server
from .ipc.models import HTMLFunction, PluginHTML

__all__ = ["PluginHTML", "HTMLFunction", "SDK_nb", "server"]


class SDK_nb:
    """提供主进程开发高频使用的工具, 不涵盖所有工具"""
    class Server:
        """服务相关"""
        register_handler = server.register_handler
        """
        注册节点的装饰器, method为调用方法名称
        
        特别地, 若method为插件名称, 它将在插件配置被修改时被调用, 传参为相应插件的新配置实例
        """

        @staticmethod
        async def broadcast(message_type: str, data: Dict) -> None:
            """广播事件

                Args:
                    message_type (str) : 标记事件类型
                    data (Dict) : 事件数据, 要求可序列化

            """
            await server.broadcast(message_type=message_type, data=data)
