import time
from hashlib import sha256
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from nonebot import get_driver, logger
from nonebot.typing import T_State
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Bot, Event, Message
from nonebot.message import event_preprocessor, run_preprocessor, run_postprocessor
from nonebot_plugin_session import extract_session

from .utils.commute import send_event
from .utils.parse import get_function_fingerprint

driver = get_driver()


_CONVERTERS: Dict[str, Callable[..., str]] = {
    "text": lambda data: data.get("text", ""),
    "face": lambda data: f"QQ表情[id={data.get('id', '')}]",
    "image": lambda data: data.get("url", data.get("file", "")),
    "record": lambda data: data.get("url", data.get("file", "")),
    "video": lambda data: data.get("url", data.get("file", "")),
    "at": lambda data: "全体成员" if data.get("qq") == "all" else f"@{data.get('qq', '')}",
    "rps": lambda _: "rps",
    "dice": lambda _: "dice",
    "shake": lambda _: "shake",
    "anonymous": lambda _: "anonymous",
    "poke": lambda data: f"{data.get('name', '')}[type={data.get('type', '')},id={data.get('id', '')}]",
    "share": lambda data: f"{data.get('title', '')} | {data.get('url', '')}",
    "contact": lambda data: f"推荐{data.get('type', '')}:{data.get('id', '')}",
    "location": lambda data: data.get("title", "") or f"位置({data.get('lat', '')},{data.get('lon', '')})",
    "music": lambda data: f"自定义音乐:{data['title']}" if data.get("type") == "custom" else f"音乐[{data.get('type', '')}]:{data.get('id', '')}",
    "reply": lambda data: f"回复:{data.get('id', '')}",
    "forward": lambda data: f"合并转发:{data.get('id', '')}",
    "node": lambda data: f"转发节点:{data['id']}" if "id" in data else f"{data.get('nickname', '')}({data.get('user_id', '')}): {StandardizedMessageSegment._parse_node_content(data.get('content', ''))}",
    "xml": lambda _: "[XML数据]",
    "json": lambda _: "[JSON数据]",
    "markdown": lambda data: data,
}


class StandardizedMessageSegment:
    __slots__ = ("type", "data")

    @staticmethod
    def to_standardized_list(message: Message) -> List[Tuple[str, str]]:
        return [
            (
                msg.get("type"),
                StandardizedMessageSegment.to_markdown(
                    msg.get("type"), _CONVERTERS.get(msg.get("type"), lambda d: str(d))(msg.get("data"))),
            )
            for msg in message
        ]

    def __init__(self, msg_type: str, data: Union[str, Dict]):
        self.type = msg_type
        self.data = _CONVERTERS.get(msg_type, lambda d: str(d))(data)

    @staticmethod
    def _parse_node_content(content: Union[str, list]) -> str:
        """节点内容解析"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                seg["data"] if isinstance(seg.get("data"), str)
                else _CONVERTERS.get(seg["type"], str)(seg.get("data", {}))
                for seg in content
            )
        return ""

    @staticmethod
    def to_markdown(type: str, data: str) -> str:
        handlers = {
            "text": lambda: data.replace("\n", "  \n"),
            "at": lambda: f"**@{data}**",
            "image": lambda: f"![图片]({data})",
            "face": lambda: f"`{data}`",
            "record": lambda: "`[语音]`",
            "video": lambda: "`[视频]`",
            "rps": lambda: "`[猜拳]`",
            "dice": lambda: "`[掷骰子]`",
            "shake": lambda: "`[窗口抖动]`",
            "poke": lambda: f"`[戳一戳:{data}]`",
            "share": lambda: f"[{parts[0]}]({parts[1]})" if (parts := data.split(" | ", 1)) and len(parts) > 1 else data,
            "contact": lambda: f"`{data}`",
            "location": lambda: f"`📍{data}`",
            "music": lambda: f"`🎵{data}`",
            "reply": lambda: "`↩️回复消息`",
            "forward": lambda: "`📨合并转发`",
            "node": lambda: f"`{data}`",
        }

        if handler := handlers.get(type):
            return handler()

        if type in {"xml", "json"}:
            return f"`{data}`"

        return f"`[未知类型:{type}]`"

    def serialize(self) -> Tuple[str, str]:
        return (self.type, self.data)

    def __repr__(self):
        return f"StandardizedMessageSegment(type={self.type!r}, data={self.data!r})"


@event_preprocessor
async def reocrd_event(bot: Bot, event: Event):
    type = event.get_type()
    if type == "message":

        session = extract_session(bot, event)
        group_id = session.id2
        user_id = session.id1

        data = {
            "bot": bot.self_id,
            "content": StandardizedMessageSegment.to_standardized_list(event.get_message()),
            "userid": user_id,
            "session": f"{f"群聊: {group_id}" if group_id is not None else "私信"} | 用户: {user_id}",
            "avatar": getattr(event, "avatar") or (f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100" if bot.adapter in ("OneBot V11", "OneBot V12") else ""),
            "groupid": group_id,
            "time": int(time.time())
        }
    else:
        data = {
            "bot": bot.self_id,
            "time": int(time.time())
        }

    await send_event(type, data)


@run_preprocessor
async def run_pre(bot: Bot, event: Event, matcher: Matcher, state: T_State):
    session = extract_session(bot, event)
    group_id = session.id2
    user_id = session.id1
    plugin_name = matcher.plugin_name
    # todo 检查黑名单
    ...
    state[f"UI{plugin_name}{hash(matcher)}"] = time.time()


@run_postprocessor
async def run_post(bot: Bot, event: Event, matcher: Matcher, exception: Optional[Exception], state: T_State):
    try:
        current_time = time.time()
        plugin_name = matcher.plugin_name or "Unknown"
        time_costed = current_time-state[f"UI{plugin_name}{hash(matcher)}"]
        session = extract_session(bot, event)
        group_id = session.id2
        user_id = session.id1

        special = [i.call for i in matcher.handlers]
        special = "".join([get_function_fingerprint(i) for i in special])

        data = {
            "bot": bot.self_id,
            "time_costed": time_costed,
            "time": int(current_time),
            "groupid": group_id,
            "userid": user_id,
            "plugin": plugin_name,
            "matcher_hash": sha256(special.encode()).hexdigest(),
            "exception": {"name": type(exception).__name__ if exception else None,
                          "detail": str(exception) if exception else None}
        }
        await send_event("plugin_call", data)
    except Exception as e:
        logger.warning(f"记录插件调用数据失败 {e}")


@Bot.on_calling_api
async def handle_api_call(bot: Bot, api: str, data: Dict[str, Any]):
    if api == "send_msg":
        data_to_send = {
            "api": api,
            "content": StandardizedMessageSegment.to_standardized_list(data["message"]),
            "bot": bot.self_id,
            "session": f"{data.get("group_id", "私聊")}-{data.get("user_id", "未知")}",
            "groupid": data.get("group_id", "私聊"),
            "time": int(time.time())
        }

    else:
        data_to_send = {
            "api": api,
            "bot": bot.self_id,
            "time": int(time.time())
        }
    await send_event("call_api", data_to_send)


@driver.on_bot_connect
async def track_connect(bot: Bot):
    data = {
        "bot": bot.self_id,
        "adapter": bot.adapter.get_name(),
        "time": int(time.time())
    }
    await send_event("bot_connect", data)


@driver.on_bot_disconnect
async def track_disconnect(bot: Bot):
    data = {
        "bot": bot.self_id,
        "adapter": bot.adapter.get_name(),
        "time": int(time.time())
    }
    await send_event("bot_disconnect", data)

for_import = None
