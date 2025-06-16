import asyncio
from typing import Dict

server_send_queue = asyncio.Queue()


async def send_event(type: str, data: Dict):
    await server_send_queue.put((type, data))
