import asyncio
import time
import os
import uuid
from urllib.parse import quote
from typing import Optional, Callable, Dict, Any, Awaitable, Tuple, Union
import websockets
from websockets.legacy.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed
from nonebot import logger
from pydantic import ValidationError

from ...protocol import ProtocolMessage, MessageHeader, RequestPayload, ResponsePayload


class WebSocketClient:
    def __init__(
        self,
        message_cb: Optional[Callable[[
            MessageHeader, Any], Awaitable[None]]] = None,
        port: int | str = os.getenv("PORT", "8000"),
        token: str = os.getenv("TOKEN", "HELLO?")
    ):
        self.port = port
        self.uri = f"ws://127.0.0.1:{self.port}/plugin_GUI?token={quote(token)}"
        self.ws: Optional[WebSocketClientProtocol] = None
        self.active = False
        self.retry_intervals = [1, 2, 5, 10]
        self.message_cb = message_cb
        self.state_lock = asyncio.Lock()
        self.tasks: set[asyncio.Task] = set()
        self._reconnect_flag = False

    async def run(self) -> None:
        """启动客户端"""
        asyncio.create_task(self._connection_manager())

    async def _connection_manager(self) -> None:
        """连接管理主循环"""
        while True:
            try:
                await self._establish_connection()
                await self._start_tasks()
                await self._monitor_connection()
            except (ConnectionClosed, ConnectionError) as e:
                logger.error(f"Connection error: {e}")
                await self._handle_reconnection()
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(5)
            finally:
                await self._cleanup()

    async def _establish_connection(self) -> None:
        """建立WebSocket连接"""
        retries = self.retry_intervals.copy()
        while True:
            await self._cleanup()

            try:
                self.ws = await websockets.connect(self.uri)
                self.active = True
                logger.success(f"Connected to {self.uri}")
                return
            except (ConnectionRefusedError, ConnectionError) as e:
                if not retries:
                    logger.error("All connection retries failed.")
                    raise
                await asyncio.sleep(retries.pop(0))
            except Exception as e:
                logger.error(f"Connection attempt failed: {e}")
                await asyncio.sleep(5)

    async def _start_tasks(self) -> None:
        """启动接收和心跳任务"""
        self.tasks.update({
            asyncio.create_task(self._receiver()),
            asyncio.create_task(self._heartbeat())
        })

    async def _monitor_connection(self) -> None:
        """监控连接状态"""
        try:
            while self.active and self.ws:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Connection monitoring cancelled")

    async def _handle_reconnection(self) -> None:
        """处理重连逻辑"""
        self._reconnect_flag = True
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
        await self._cleanup()

    async def send_raw_message(self, message: str) -> None:
        """发送原始消息"""
        if self.ws and not self.ws.closed:
            try:
                await self.ws.send(message)
            except ConnectionClosed:
                logger.warning("Send failed, connection closed")
                self._reconnect_flag = True

    async def _receiver(self) -> None:
        """接收消息循环"""
        buffer = ""
        try:
            async for raw_data in self.ws:
                buffer += raw_data
                while ProtocolMessage.SEPARATOR in buffer:
                    msg, buffer = buffer.split(ProtocolMessage.SEPARATOR, 1)
                    await self._process_raw_message(msg)
        except ConnectionClosed:
            logger.info("WebSocket disconnected normally")
        except Exception as e:
            logger.error(f"Receiver error: {e}")

    async def _process_raw_message(self, raw_data: str) -> None:
        """处理原始消息"""
        if not self.message_cb:
            return

        try:
            header, payload = ProtocolMessage.decode(raw_data)
            if header:
                await self.message_cb(header, payload)
        except ValidationError as e:
            logger.error(f"Invalid message format: {e}")

    async def _heartbeat(self) -> None:
        """心跳机制"""
        try:
            while self.active and self.ws and not self.ws.closed:
                await asyncio.sleep(5)
                header = MessageHeader(
                    msg_id=str(uuid.uuid4()),
                    msg_type="heartbeat",
                    timestamp=time.time()
                )
                message = ProtocolMessage.encode(header, {"status": "alive"})
                await self.send_raw_message(message)
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

    async def _cleanup(self) -> None:
        """清理资源"""
        async with self.state_lock:
            self.active = False
            for task in self.tasks:
                task.cancel()
            self.tasks.clear()
            if self.ws and not self.ws.closed:
                await self.ws.close()
            self.ws = None


class MessageHandler:
    """高层操作类：处理消息路由、队列管理和响应等待"""

    def __init__(self):
        self.client = WebSocketClient(self.sort_data)
        self.request_lock = asyncio.Lock()
        self.queues: Dict[str, asyncio.Queue] = {
            "message": asyncio.Queue(),
            "call_api": asyncio.Queue(),
            "bot_connect": asyncio.Queue(),
            "bot_disconnect": asyncio.Queue()
        }
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """启动客户端"""
        await self.client.run()

    async def send_request(
        self,
        method: str,
        params: Dict[str, Any] = None,
        timeout: float = 10.0,
        wait: bool = True
    ) -> Union[ResponsePayload, asyncio.Future]:
        if params is None:
            params = {}
        msg_id = str(uuid.uuid4())
        future = asyncio.Future()

        async with self.request_lock:
            self.pending_requests[msg_id] = future

        header = MessageHeader(
            msg_id=msg_id,
            msg_type="request",
            correlation_id=msg_id,
            timestamp=time.time()
        )
        payload = RequestPayload(method=method, params=params)
        message = ProtocolMessage.encode(header, payload.model_dump())
        await self.client.send_raw_message(message)

        if not wait:
            return future

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Request {msg_id} timed out")
            async with self.request_lock:
                if msg_id in self.pending_requests:
                    future = self.pending_requests.pop(msg_id)
                    if not future.done():
                        future.set_exception(TimeoutError("Request timeout"))
            raise

    async def sort_data(self, header: MessageHeader, payload: Dict) -> None:
        """消息路由处理"""
        if header.msg_type == "response":
            future = self.pending_requests.pop(header.correlation_id, None)
            if future and not future.done():
                try:
                    response = ResponsePayload(**payload)
                    future.set_result(response)
                except ValidationError as e:
                    future.set_exception(e)
        else:
            queue = self.queues.get(header.msg_type)
            if queue:
                await queue.put((header, payload))

    async def get_message(self, *types: str) -> Tuple[str, Any]:
        """从指定类型队列获取第一个到达的消息"""
        if not types:
            raise ValueError("At least one type required")

        tasks = [asyncio.create_task(self.queues[t].get()) for t in types]

        try:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            result_task = done.pop()
            result = result_task.result()

            for i, task in enumerate(tasks):
                if task.done() and not task.cancelled():
                    return (types[i], result[1])

            return (types[0], result)
        finally:
            for task in pending:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass


talker = MessageHandler()
