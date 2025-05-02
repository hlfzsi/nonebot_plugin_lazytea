from typing import Any, Dict
from nonebot import get_driver
from nonebot.adapters import Bot, Event, Message
from nonebot.message import event_preprocessor
from .utils.commute import send_event


driver = get_driver()


def fetch_first_value(data: Dict):
    return next(
        (str(v) for v in data.values() if v is not None and v != ""),
        ""
    )


def convert_message_to_md(message: Message):
    return " ".join([
        f"`@ {fetch_first_value(seg.data)} :`" if seg.type == "at"
        else fetch_first_value(seg.data) if seg.type == "text"
        else f"![图片]({seg.data.get("url", fetch_first_value(seg.data))})" if seg.type == "image"
        else f"`Unknown Type {seg.type}`"
        for seg in message
    ]).strip()


@event_preprocessor
async def reocrd_event(bot: Bot, event: Event):
    type = event.get_type()
    if type == "message":
        data = {
            "bot": bot.self_id,
            "content": convert_message_to_md(event.get_message()),
            "userid": event.get_user_id(),
            "session": event.get_session_id(),
            "avatar": getattr(event, "avatar") or (f"http://q1.qlogo.cn/g?b=qq&nk={event.get_user_id()}&s=100" if bot.adapter == "OneBot V11'" else "")
        }
    else:
        data = {
            "bot": bot.self_id
        }

    await send_event(type, data)


@Bot.on_calling_api
async def handle_api_call(bot: Bot, api: str, data: Dict[str, Any]):
    if api == "send_msg":
        data_to_send = {
            "api": api,
            "message": convert_message_to_md(data["message"]),
            "bot": bot.self_id,
            "session": f"{data.get("group_id", "私聊")}-{data["user_id"]}"
        }

    else:
        data_to_send = {
            "api": api,
            "bot": bot.self_id
        }
    await send_event("call_api", data_to_send)


@driver.on_bot_connect
async def track_connect(bot: Bot):
    data = {
        "bot": bot.self_id,
        "adapter": bot.adapter.get_name()
    }
    await send_event("bot_connect", data)


@driver.on_bot_disconnect
async def track_disconnect(bot: Bot):
    data = {
        "bot": bot.self_id,
        "adapter": bot.adapter.get_name()
    }
    await send_event("bot_disconnect", data)

for_import = None
