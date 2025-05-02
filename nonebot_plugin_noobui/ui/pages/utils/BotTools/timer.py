import time
from typing import Dict, Optional


class BotStatus:
    """表示机器人的计时状态。"""
    __slots__ = ("start_time", "offline_start", "total_offline")
    
    def __init__(self, start_time: float) -> None:
        """
        初始化机器人状态。
        
        :param start_time: 机器人注册的初始时间戳。
        """
        self.start_time: float = start_time  # 初始注册时间
        self.offline_start: Optional[float] = None  # 上次离线开始的时间戳
        self.total_offline: float = 0.0  # 累计离线总时长


class BotTimer:
    """跟踪多个机器人的在线/离线计时状态。"""
    
    def __init__(self) -> None:
        """初始化机器人计时器，存储所有机器人的状态。"""
        self.bots: Dict[str, BotStatus] = {}  # 存储机器人ID到状态的映射

    def add_bot(self, bot_id: str) -> None:
        """
        注册一个新机器人，并记录当前时间戳。
        
        :param bot_id: 机器人唯一标识符。
        """
        if bot_id not in self.bots:
            self.bots[bot_id] = BotStatus(time.time())

    def remove_bot(self, bot_id: str) -> None:
        """
        移除指定机器人及其所有跟踪数据。
        
        :param bot_id: 机器人唯一标识符。
        """
        self.bots.pop(bot_id, None)

    def set_offline(self, bot_id: str) -> None:
        """
        标记机器人离线，并记录当前时间戳（如果之前是在线状态）。
        
        :param bot_id: 机器人唯一标识符。
        """
        status: Optional[BotStatus] = self.bots.get(bot_id)
        if status and status.offline_start is None:
            status.offline_start = time.time()

    def set_online(self, bot_id: str) -> None:
        """
        标记机器人上线，并累加离线时长。
        
        :param bot_id: 机器人唯一标识符。
        """
        status: Optional[BotStatus] = self.bots.get(bot_id)
        if status and status.offline_start is not None:
            status.total_offline += time.time() - status.offline_start
            status.offline_start = None

    def get_start_time(self, bot_id: str) -> Optional[float]:
        """
        获取机器人的初始注册时间。
        
        :param bot_id: 机器人唯一标识符。
        :return: 如果存在，返回初始注册时间；否则返回None。
        """
        status: Optional[BotStatus] = self.bots.get(bot_id)
        return status.start_time if status else None

    def get_elapsed_time(self, bot_id: str) -> float:
        """
        计算机器人有效在线时长（排除离线时间段）。
        
        :param bot_id: 机器人唯一标识符。
        :return: 机器人有效在线时长。
        """
        status: Optional[BotStatus] = self.bots.get(bot_id)
        if not status:
            return 0.0

        current_time: float = time.time()  # 当前时间戳
        current_offline: float = time.time() - status.offline_start if status.offline_start else 0.0  # 当前离线时长
        total_offline: float = status.total_offline + current_offline  # 总离线时长

        elapsed: float = current_time - status.start_time - total_offline  # 有效在线时长
        return elapsed