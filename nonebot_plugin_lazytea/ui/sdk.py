from typing import Any, Optional, Union
from PySide6.QtCore import SignalInstance

from .pages.utils.BotTools import BotToolKit
from .pages.utils.client import talker, ResponsePayload
from .pages.utils.conn import AsyncQuerySignal, get_database
from .pages.utils.conn.pool import SQLiteConnectionPool

__all__ = ["SDK_UI", "ResponsePayload", "AsyncQuerySignal"]


class SDK_UI:
    """
    提供在UI进程中高频使用的工具, 不涵盖所有工具
    
    注意, 必须使用`PySide6`作为UI支持, 且不可使用`asyncio`
    """

    bot_tools = BotToolKit

    class IPC:
        """适用于进程通信的模块"""
        @staticmethod
        def send_request(
            method: str,
            success_signal: Optional[SignalInstance] = None,
            error_signal: Optional[SignalInstance] = None,
            timeout: float = 3.0,
            **params: Any
        ) -> None:
            """向主进程发送请求并等待回调, 回调信号参数类型为`ResponsePayload`, 
            LazyTea已定义部分方法, 可参阅`func_call.py`

            Args:
                method (str): 主进程注册节点名称, 通常为`{plugin_name}_{method_name}`
                success_signal (Optional[SignalInstance], optional): 请求成功的回调信号
                error_signal (Optional[SignalInstance], optional): 请求失败的回调信号
                timeout (float, optional): 超时时间
                请求参数采用关键字传参
            """
            talker.send_request(method=method, success_signal=success_signal,
                                error_signal=error_signal, timeout=timeout, **params)

        @staticmethod
        def subscribe(*types: str, signal: SignalInstance) -> None:
            """订阅事件, 回调信号参数类型为 (str,dict), 
            dict键值对与事件类型可参阅项目根目录中的`bridge.py`, 
            不需要手动取消订阅

            Args:
                signal (SignalInstance): 回调信号
            """
            talker.subscribe(*types, signal=signal)

    class DataBase:
        """提供统一的数据库接口"""
        @staticmethod
        def get() -> SQLiteConnectionPool:
            """返回连接池实例"""
            return get_database()

        @staticmethod
        def execute_async(sql: str, params: Union[tuple, list] = (),
                          callback_signal: Optional[AsyncQuerySignal] = None,
                          for_write: bool = True):
            """
            异步执行查询, 回调信号类型为`AsyncQuerySignal`

            :param for_write: 标记是否为写操作（默认为True） 如果你真的不清楚, 就填True
            """
            get_database().execute_async(sql=sql, params=params,
                                         callback_signal=callback_signal, for_write=for_write)

        @staticmethod
        def executelater(sql: str, params: Union[tuple, list]):
            """延迟提交(写)方法, 用于合并高频小数据, 利于性能

            建表等操作不要使用本方法, 因为本方法不完全保留顺序

            Args:
                sql (str)
                params (Union[tuple, list])
            """
            get_database().executelater(sql=sql, params=params)
