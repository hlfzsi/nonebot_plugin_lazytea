from .color import ColorMap
from .counter import MsgCounter
from .timer import BotTimer

__all__ = ["ColorMap", "MsgCounter","BotTimer"]


class BotToolKit:
    color = ColorMap
    counter = MsgCounter(merge_threshold=128)
    timer = BotTimer()
    
    @classmethod
    def add_bot(cls, bot_id):
        cls.timer.add_bot(bot_id)
        cls.color.get(bot_id)
    