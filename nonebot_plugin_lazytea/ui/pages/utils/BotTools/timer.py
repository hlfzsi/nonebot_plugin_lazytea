import time
import threading
from typing import Dict, Optional


class BotStatus:
    """表示机器人的计时状态。"""
    __slots__ = ("start_time", "offline_start", "total_offline", "lock")

    def __init__(self, start_time: float) -> None:
        """
        初始化机器人状态。

        :param start_time: 机器人注册的初始时间戳。
        """
        self.lock = threading.Lock()
        self.start_time: float = start_time
        self.offline_start: Optional[float] = None
        self.total_offline: float = 0.0


class BotTimer:
    """跟踪多个机器人的在线/离线计时状态。"""

    def __init__(self) -> None:
        self.bots: Dict[str, BotStatus] = {}
        self._lock = threading.Lock()

    def add_bot(self, bot_id: str) -> None:
        """
        注册一个新机器人，并记录当前时间戳。这是一个线程安全的操作。

        :param bot_id: 机器人唯一标识符。
        """
        with self._lock:
            if bot_id not in self.bots:
                self.bots[bot_id] = BotStatus(time.time())

    def remove_bot(self, bot_id: str) -> None:
        """
        移除指定机器人及其所有跟踪数据。

        :param bot_id: 机器人唯一标识符。
        """
        with self._lock:
            self.bots.pop(bot_id, None)

    def set_offline(self, bot_id: str) -> None:
        """
        标记机器人离线，并记录当前时间戳。

        :param bot_id: 机器人唯一标识符。
        """
        with self._lock:
            status: Optional[BotStatus] = self.bots.get(bot_id)

        if status:
            with status.lock:
                if status.offline_start is None:
                    status.offline_start = time.time()

    def set_online(self, bot_id: str) -> None:
        """
        标记机器人上线，并累加离线时长。

        :param bot_id: 机器人唯一标识符。
        """
        with self._lock:
            status: Optional[BotStatus] = self.bots.get(bot_id)

        if status:
            with status.lock:
                if status.offline_start is not None:
                    status.total_offline += time.time() - status.offline_start
                    status.offline_start = None

    def get_start_time(self, bot_id: str) -> Optional[float]:
        """
        获取机器人的初始注册时间。

        :param bot_id: 机器人唯一标识符。
        :return: 如果存在，返回初始注册时间；否则返回None。
        """
        with self._lock:
            status: Optional[BotStatus] = self.bots.get(bot_id)

        if not status:
            return None

        return status.start_time

    def get_elapsed_time(self, bot_id: str) -> float:
        """
        计算机器人有效在线时长（排除离线时间段）。

        :param bot_id: 机器人唯一标识符。
        :return: 机器人有效在线时长。
        """
        with self._lock:
            status: Optional[BotStatus] = self.bots.get(bot_id)

        if not status:
            return 0.0

        with status.lock:
            current_time: float = time.time()

            current_offline: float = (
                current_time - status.offline_start) if status.offline_start is not None else 0.0
            total_offline: float = status.total_offline + current_offline

            elapsed: float = current_time - status.start_time - total_offline
            return elapsed
