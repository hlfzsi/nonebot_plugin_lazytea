import time
import os
import uuid
from urllib.parse import quote
from collections import defaultdict
from typing import List, Optional, Callable, Dict, Any, TypedDict
from threading import Event
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from pydantic import ValidationError
from PySide6.QtCore import QThreadPool, QRunnable, Signal, QObject, Slot, SignalInstance, QTimer

from .tealog import logger
from ...protocol import ProtocolMessage, MessageHeader, RequestPayload, ResponsePayload


class WorkerSignals(QObject):
    message_received = Signal(MessageHeader, dict)
    connection_state = Signal(bool)
    error = Signal(str)


class WebSocketWorker(QRunnable):
    def __init__(self, client: 'WebSocketClient'):
        super().__init__()
        self.client = client
        self.signals = WorkerSignals()
        self.stop_event = Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                with connect(self.client.uri) as websocket:
                    self.client.ws = websocket
                    self.signals.connection_state.emit(True)

                    while not self.stop_event.is_set():
                        try:
                            message = websocket.recv(timeout=1)
                            if message:
                                self._handle_message(message)  # type: ignore
                        except TimeoutError:
                            continue
                        except (ConnectionClosed, ConnectionRefusedError):
                            logger.info("Connection closed.")
                            self.stop_event.set()
                            break
                        except Exception as e:
                            logger.error(f"Error receiving message: {e}")
                            self.stop_event.set()
                            break
            except Exception as e:
                self.signals.error.emit(str(e))
                self.stop_event.wait(5)
            finally:
                if self.client.ws:
                    self.client.ws.close()
                    self.client.ws = None
                self.signals.connection_state.emit(False)

    def _handle_message(self, raw_data: str):
        if ProtocolMessage.SEPARATOR in raw_data:
            msg, _ = raw_data.split(ProtocolMessage.SEPARATOR, 1)
            try:
                header, payload = ProtocolMessage.decode(msg)
                if header:
                    self.signals.message_received.emit(header, payload)
            except ValidationError as e:
                self.signals.error.emit(str(e))


class HeartbeatWorker(QRunnable):
    def __init__(self, client: 'WebSocketClient'):
        super().__init__()
        self.client = client
        self.stop_event = Event()

    def run(self):
        while not self.stop_event.is_set():
            if self.client.connected and self.client.ws:
                try:
                    header = MessageHeader(
                        msg_id=str(uuid.uuid4()),
                        msg_type="heartbeat",
                        timestamp=time.time(),
                        correlation_id=None
                    )
                    message = ProtocolMessage.encode(
                        header, {"status": "alive"})
                    self.client.send_raw_message(message)
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
            self.stop_event.wait(5)


class WebSocketClient:
    def __init__(
        self,
        message_cb: Optional[Callable[[MessageHeader, Any], None]] = None,
        connection_cb: Optional[Callable[[bool], None]] = None,
        port: int | str = os.getenv("PORT", "8000"),
        token: str = os.getenv("TOKEN", "HELLO?")
    ):
        self.port = port
        self.uri = f"ws://127.0.0.1:{self.port}/plugin_GUI?token={quote(token)}"
        self.ws: Optional[Any] = None
        self.message_cb = message_cb
        self.connection_cb = connection_cb
        self.thread_pool = QThreadPool.globalInstance()
        self.ws_worker = WebSocketWorker(self)
        self.heartbeat_worker = HeartbeatWorker(self)
        self.connected = False

        self._workers_started = False

        self._setup_signals()

    def _setup_signals(self):
        self.ws_worker.signals.message_received.connect(
            self._on_message_received)
        self.ws_worker.signals.error.connect(
            lambda e: logger.error(f"WebSocket Error: {e}"))
        self.ws_worker.signals.connection_state.connect(
            self._on_connection_state)

    def _on_connection_state(self, state: bool):
        """处理连接状态变化"""
        self.connected = state
        if self.connection_cb:
            self.connection_cb(state)

    @Slot(MessageHeader, dict)
    def _on_message_received(self, header: MessageHeader, payload: dict):
        if self.message_cb:
            self.message_cb(header, payload)

    def run(self):
        """
        启动客户端。
        多次调用不会产生副作用。
        """
        if not self._workers_started:
            self.thread_pool.start(self.ws_worker)
            self.thread_pool.start(self.heartbeat_worker)
            self._workers_started = True

    def send_raw_message(self, message: str) -> bool:
        """发送原始消息,返回是否发送成功"""
        if not self.connected:
            logger.warning("Cannot send message: Not connected")
            return False

        if self.ws:
            try:
                self.ws.send(message)
                return True
            except ConnectionClosed:
                self.connected = False
                return False
        return False

    def stop(self):
        self.ws_worker.stop_event.set()
        self.heartbeat_worker.stop_event.set()
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logger.warning(f"关闭 websocket 时发生错误: {e}")
        self.connected = False
        self._workers_started = False
        logger.debug("WebSocket client stopped.")


class RequestDict(TypedDict):
    timer: QTimer
    success_signal: Optional[SignalInstance]
    error_signal: Optional[SignalInstance]


class MessageHandler(QObject):
    """
    消息处理器,处理所有消息路由和请求响应。
    提供启动后和关闭前钩子信号。
    """
    started = Signal()
    stopping = Signal()

    def __init__(self):
        super().__init__()
        self.client = WebSocketClient(
            message_cb=self.sort_data,
            connection_cb=self._handle_connection_change
        )
        self.signal_dict: Dict[str, List[SignalInstance]] = defaultdict(list)
        self._pending_requests: Dict[str, RequestDict] = {}
        self._started_emitted_this_session = False

    def _handle_connection_change(self, is_connected: bool) -> None:
        """处理连接状态变化，用于触发 started 信号"""
        if is_connected and not self._started_emitted_this_session:
            self.started.emit()
            self._started_emitted_this_session = True
        elif not is_connected:
            self._started_emitted_this_session = False

    def start(self) -> None:
        """启动客户端并开始监听连接"""
        self.client.run()

    def stop(self) -> None:
        """停止客户端，并触发关闭前钩子"""
        self.stopping.emit()

        self.client.stop()

        # 清理待处理的请求
        for msg_id, request_info in list(self._pending_requests.items()):
            request_info["timer"].stop()
            request_info["timer"].deleteLater()

            if error_signal := request_info.get("error_signal"):
                try:
                    error_signal.emit(
                        "Client is shutting down. Request cancelled.")
                except RuntimeError:
                    pass
        self._pending_requests.clear()
        logger.info("MessageHandler has been shut down.")

    def send_request(
        self,
        method: str,
        success_signal: Optional[SignalInstance] = None,
        error_signal: Optional[SignalInstance] = None,
        timeout: float = 3.0,
        **params: Any
    ) -> None:
        """发送请求并设置响应信号"""
        msg_id = str(uuid.uuid4())

        # 设置超时定时器
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handle_timeout(msg_id))
        timer.start(int(timeout * 1000))

        # 保存请求信息
        self._pending_requests[msg_id] = {
            "timer": timer,
            "success_signal": success_signal,
            "error_signal": error_signal
        }

        # 发送请求
        header = MessageHeader(
            msg_id=msg_id,
            msg_type="request",
            correlation_id=msg_id,
            timestamp=time.time()
        )
        payload = RequestPayload(method=method, params=params)
        message = ProtocolMessage.encode(header, payload.model_dump())

        if not self.client.send_raw_message(message):
            self._cleanup_request(msg_id)
            if error_signal:
                error_signal.emit("Failed to send request: Not connected")

    def _handle_timeout(self, msg_id: str):
        """处理请求超时"""
        if msg_id in self._pending_requests:
            request_info = self._pending_requests.pop(msg_id)
            if error_signal := request_info["error_signal"]:
                error_signal.emit(f"Request timeout for {msg_id}")
            else:
                raise RuntimeWarning(f"Request timeout for {msg_id}")

    def _cleanup_request(self, msg_id: str):
        """清理请求资源"""
        if msg_id in self._pending_requests:
            request_info = self._pending_requests.pop(msg_id)
            request_info["timer"].stop()
            request_info["timer"].deleteLater()

    def sort_data(self, header: MessageHeader, payload: Dict) -> None:
        """消息路由处理"""
        # 处理响应消息
        if header.msg_type == "response" and header.correlation_id:
            self._handle_response(header.correlation_id, payload)
        # 处理其他类型消息
        else:
            for signal in self.signal_dict[header.msg_type]:
                try:
                    signal.emit(header.msg_type, payload)
                except RuntimeError as e:
                    if "deleted" in str(e).lower():
                        self.signal_dict[header.msg_type].remove(signal)
                    else:
                        raise e

    def _handle_response(self, msg_id: str, payload: Dict):
        """处理响应消息"""
        if msg_id not in self._pending_requests:
            return

        request_info = self._pending_requests.pop(msg_id)
        request_info["timer"].stop()
        request_info["timer"].deleteLater()

        response = ResponsePayload(**payload)
        try:
            if error := payload.get("error"):
                if error_signal := request_info["error_signal"]:
                    error_signal.emit(response)
                else:
                    raise ValueError(
                        f"An Exception occurred while processing {error}")
            elif success_signal := request_info["success_signal"]:
                success_signal.emit(response)

        except RuntimeError as e:
            if "deleted" in str(e).lower():
                pass
            else:
                raise e

    def subscribe(self, *types: str, signal: SignalInstance) -> None:
        """订阅指定类型的消息,返回类型和负载(str,dict)"""
        if not types:
            raise ValueError("At least one type required")
        for type_ in types:
            self.signal_dict[type_].append(signal)


# 全局实例
talker = MessageHandler()
