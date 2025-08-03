import asyncio
import time
from typing import Any, Dict, Callable, Set, List, Tuple
import uuid
from nonebot import logger
from nonebot.drivers import WebSocket
from pydantic import ValidationError
from ..ui.protocol import ProtocolMessage, MessageHeader, RequestPayload, ResponsePayload

class Server:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.handlers: Dict[str, Callable] = {}

        self.start_time: float = time.time()
        self.has_connected: bool = False
        self._buffer_lock = asyncio.Lock()

        self.bot_status_buffer: Dict[str, Tuple[str, Dict]] = {}
        self.transient_message_buffer: List[Tuple[str, Dict]] = []

    async def clear_transient_buffer_after_delay(self):
        """一个一次性的后台任务，在60秒后运行，如果瞬时缓冲区仍有数据则清空它。"""
        await asyncio.sleep(60)
        async with self._buffer_lock:
            if self.transient_message_buffer:
                logger.info("启动后60秒窗口期已过，丢弃未发送的瞬时消息。")
                self.transient_message_buffer.clear()

    async def start(self, websocket: WebSocket, token: str) -> None:
        """处理WebSocket"""
        
        rq_token = websocket.request.url.query.get(
            'token') or websocket.request.headers.get('Authorization')

        if rq_token and rq_token.startswith('Bearer '):
            rq_token = rq_token[7:].strip()

        if rq_token != token:
            await websocket.close(code=4000)
            return

        await websocket.accept()
        await self.send_bot_status(websocket)

        is_first_connection = False
        async with self._lock:
            if not self.active_connections:
                is_first_connection = True

            self.active_connections.add(websocket)
            self.has_connected = True

        if is_first_connection and time.time() - self.start_time < 60:
            asyncio.create_task(self._flush_transient_buffer())

        try:
            buffer = ""
            while True:
                raw_data = await websocket.receive_text()
                buffer += raw_data

                while ProtocolMessage.SEPARATOR in buffer:
                    msg, buffer = buffer.split(ProtocolMessage.SEPARATOR, 1)
                    asyncio.create_task(self._process_message(websocket, msg))

        except:
            logger.debug("Client disconnected")
        finally:
            await self._cleanup_connection(websocket)

    def register_handler(self, method: str) -> Callable:
        """注册请求处理器的装饰器"""
        if not method:
            raise ValueError("method 名称不能为空")

        def decorator(func: Callable):
            if method not in self.handlers:
                self.handlers[method] = func
                return func
            else:
                raise RuntimeError(f"UI远程方法 {method} 发生冲突,请更换名称")
        return decorator

    async def broadcast(self, message_type: str, data: Dict) -> None:
        """
        广播方法。
        根据消息类型、服务器运行时间和连接状态来处理消息。
        """
        if message_type in {"bot_connect", "bot_disconnect"}:
            bot_id = data.get("bot")
            platform = data.get("platform")
            if bot_id and platform:
                composite_key = f"{bot_id}_{platform}"
                async with self._buffer_lock:
                    self.bot_status_buffer[composite_key] = (
                        message_type, data)

        elif not self.has_connected and time.time() - self.start_time < 60:
            async with self._buffer_lock:
                self.transient_message_buffer.append((message_type, data))

        if self.has_connected:
            await self._real_broadcast(message_type, data)

    async def _flush_transient_buffer(self):
        """发送所有在启动初期缓冲的瞬时消息，然后清空缓冲区。"""
        async with self._buffer_lock:
            messages_to_flush = self.transient_message_buffer.copy()
            self.transient_message_buffer.clear()

        if messages_to_flush:
            logger.info(f"首个客户端连接，发送 {len(messages_to_flush)} 条缓存的瞬时消息。")
            for msg_type, data in messages_to_flush:
                await self._real_broadcast(msg_type, data)

    async def send_bot_status(self, ws: WebSocket):
        """向指定的单个客户端发送当前所有bot的最新状态"""
        async with self._buffer_lock:
            statuses = list(self.bot_status_buffer.values())

        for msg_type, data in statuses:
            try:
                header = MessageHeader(
                    msg_id=str(uuid.uuid4()),
                    msg_type=msg_type,
                    timestamp=time.time()
                )
                encoded = ProtocolMessage.encode(header, data)
                await ws.send_text(encoded)
            except Exception as e:
                logger.error(f"向客户端发送bot状态失败: {e}")

    async def _real_broadcast(self, message_type: str, data: Dict) -> None:
        """实际执行广播的核心方法"""
        async with self._lock:
            if not self.active_connections:
                return

            tasks = []
            header = MessageHeader(
                msg_id=str(uuid.uuid4()),
                msg_type=message_type,
                timestamp=time.time()
            )
            encoded = ProtocolMessage.encode(header, data)

            for ws in list(self.active_connections):
                try:
                    tasks.append(ws.send_text(encoded))
                except Exception as e:
                    logger.error(f"Broadcast failed: {str(e)}")

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_message(self, ws: WebSocket, raw_data: str) -> None:
        """处理原始消息"""
        try:
            header, payload = ProtocolMessage.decode(raw_data)
            if not header:
                await self._send_error(ws, "Invalid message header")
                return

            if header.msg_type == "request":
                await self._handle_request(ws, header, payload)
            elif header.msg_type == "heartbeat":
                await self._send_heartbeat(ws)

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}")
            await self._send_error(ws, "Internal server error")

    async def _handle_request(
        self,
        ws: WebSocket,
        header: MessageHeader,
        payload: Dict[str, Any]
    ) -> None:
        """处理请求并返回响应"""
        try:
            request = RequestPayload(**payload)
            handler = self.handlers.get(request.method)

            if not handler:
                response = ResponsePayload(code=404, error="Method not found")
            else:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**request.params)
                else:
                    result = handler(**request.params)
                if isinstance(result, Dict) and result.get("error"):
                    response = ResponsePayload(
                        code=1, error=result.get("error"))
                else:
                    response = ResponsePayload(code=200, data=result)

        except ValidationError as e:
            import traceback
            response = ResponsePayload(
                code=400, error=f"Invalid request format,detail:{traceback.format_exc()}")
        except Exception as e:
            response = ResponsePayload(code=500, error=str(e))

        response_header = MessageHeader(
            msg_id=str(uuid.uuid4()),
            msg_type="response",
            correlation_id=header.msg_id,
            timestamp=time.time()
        )
        await self._send_response(ws, response_header, response)

    async def _send_response(
        self,
        ws: WebSocket,
        header: MessageHeader,
        payload: ResponsePayload
    ) -> None:
        """发送响应消息"""
        try:
            message = ProtocolMessage.encode(header, payload.model_dump())
            await ws.send_text(message)
        except Exception as e:
            logger.error(f"Send response failed: {str(e)}")

    async def _send_heartbeat(self, ws: WebSocket):
        """处理心跳响应"""
        try:
            header = MessageHeader(
                msg_id=str(uuid.uuid4()),
                msg_type="heartbeat",
                timestamp=time.time()
            )
            await ws.send_text(ProtocolMessage.encode(header, {"status": "alive"}))
        except Exception as e:
            logger.debug(f"Heartbeat failed: {str(e)}")

    async def _send_error(self, ws: WebSocket, error: str):
        """发送错误响应"""
        response = ResponsePayload(code=500, error=error)
        header = MessageHeader(
            msg_id=str(uuid.uuid4()),
            msg_type="response",
            timestamp=time.time()
        )
        await self._send_response(ws, header, response)

    async def _cleanup_connection(self, ws: WebSocket):
        """清理断开连接的客户端"""
        async with self._lock:
            if ws in self.active_connections:
                self.active_connections.remove(ws)
                if not self.active_connections:
                    self.has_connected = False
                try:
                    if not ws.closed:
                        await ws.close()
                except RuntimeError as e:
                    if "Unexpected ASGI message 'websocket.close'" in str(e):
                        logger.debug("WebSocket already closed")
                    else:
                        raise
