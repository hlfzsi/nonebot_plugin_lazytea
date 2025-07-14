import asyncio
from typing import Dict
from collections import defaultdict

server_send_queue = asyncio.Queue()


async def send_event(type: str, data: Dict):
    await server_send_queue.put((type, data))

bot_off_line = defaultdict(set)  # platform | set(bot_id)
