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
        self.message_buffer: List[Tuple[str, Dict]] = []
        self.has_connected = False
        self._buffer_lock = asyncio.Lock()

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

        async with self._lock:
            self.active_connections.add(websocket)
            if not self.has_connected:
                self.has_connected = True
                asyncio.create_task(self._flush_buffer())

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
        """广播方法"""
        if not self.has_connected:
            async with self._buffer_lock:
                self.message_buffer.append((message_type, data))
            return

        await self._real_broadcast(message_type, data)

    async def _flush_buffer(self):
        """发送所有缓冲消息"""
        async with self._buffer_lock:
            messages = self.message_buffer.copy()
            self.message_buffer.clear()

        for msg_type, data in messages:
            await self._real_broadcast(msg_type, data)

    async def _real_broadcast(self, message_type: str, data: Dict) -> None:
        """实际执行广播的核心方法"""
        async with self._lock:
            if not self.active_connections:
                return

            tasks = []
            for ws in list(self.active_connections):
                try:
                    header = MessageHeader(
                        msg_id=str(uuid.uuid4()),
                        msg_type=message_type,
                        timestamp=time.time()
                    )
                    encoded = ProtocolMessage.encode(header, data)
                    tasks.append(ws.send_text(encoded))
                except Exception as e:
                    logger.error(f"Broadcast failed: {str(e)}")
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
                try:
                    if not ws.closed:
                        await ws.close()
                except RuntimeError as e:
                    if "Unexpected ASGI message 'websocket.close'" in str(e):
                        logger.debug("WebSocket already closed")
                    else:
                        raise
