import time
import os
import uuid
from urllib.parse import quote
from collections import defaultdict
from typing import List, Optional, Callable, Dict, Any, TypedDict
from threading import Event, Lock

from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from pydantic import ValidationError
from PySide6.QtCore import QThreadPool, QRunnable, Signal, QObject, Slot, SignalInstance, QTimer, QMutex, QMutexLocker

from .tealog import logger
from .client_login.config_manager import ConnectionConfigManager, ConnectionDetails
from .client_login.login_ui import LoginDialog
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
        if not self.client.uri:
            logger.error(
                "WebSocketWorker started without a valid URI. Stopping.")
            self.signals.error.emit("Client URI not configured.")
            self.signals.connection_state.emit(False)
            return

        while not self.stop_event.is_set():
            try:
                with connect(self.client.uri) as websocket:
                    with self.client.lock:
                        self.client.ws = websocket

                    self.signals.connection_state.emit(True)
                    logger.debug("WebSocket connection established.")
                    if not self.client.single_attempt:
                        self.client.had_successful_connection = True

                    while not self.stop_event.is_set():
                        try:
                            message = websocket.recv(timeout=1)
                            if message:
                                if isinstance(message, bytes):
                                    message = message.decode("utf-8")
                                if isinstance(message, bytearray):
                                    message = message.decode("utf-8")
                                elif isinstance(message, memoryview):
                                    message = message.tobytes().decode("utf-8")
                                self._handle_message(message)
                        except TimeoutError:
                            continue
                        except (ConnectionClosed, ConnectionRefusedError):
                            self.stop_event.set()
                            break
                        except Exception as e:
                            logger.error(f"Error receiving message: {e}")
                            self.stop_event.set()
                            break
            except Exception as e:
                self.signals.error.emit(str(e))
                if self.client.single_attempt and not self.client.had_successful_connection:
                    break
                self.stop_event.wait(5)
            finally:
                with self.client.lock:
                    if self.client.ws:
                        try:
                            self.client.ws.close()
                        except Exception:
                            pass
                        self.client.ws = None

                self.signals.connection_state.emit(False)
                logger.info("WebSocket connection closed.")

    def _handle_message(self, raw_data: str):
        if ProtocolMessage.SEPARATOR in raw_data:
            msg, _ = raw_data.split(ProtocolMessage.SEPARATOR, 1)
            try:
                header, payload = ProtocolMessage.decode(msg)
                if header:
                    self.signals.message_received.emit(header, payload)
            except (ValidationError, Exception) as e:
                self.signals.error.emit(f"Message decoding error: {e}")


class HeartbeatWorker(QRunnable):
    def __init__(self, client: 'WebSocketClient'):
        super().__init__()
        self.client = client
        self.stop_event = Event()

    def run(self):
        while not self.stop_event.is_set():
            if self.client.is_connected():
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
        port: int | str | None = os.getenv("PORT"),
    ):
        self.port = port
        self.uri: Optional[str] = None
        self.ws: Optional[Any] = None
        self.message_cb = message_cb
        self.connection_cb = connection_cb
        self.thread_pool = QThreadPool.globalInstance()

        self.ws_worker = WebSocketWorker(self)
        self.heartbeat_worker = HeartbeatWorker(self)

        self.lock = Lock()
        self._connected = False
        self._workers_started = False
        self.single_attempt = False
        self.had_successful_connection = False

        self._setup_signals()

    def configure(self, host: str, port: int, token: str):
        """使用给定的参数配置WebSocket URI"""
        self.uri = f"ws://{host}:{port}/plugin_GUI?token={quote(token)}"
        logger.info(f"WebSocket client configured for URI: {self.uri}")

    @property
    def connected(self):
        """获取连接状态"""
        with self.lock:
            return self._connected

    def is_connected(self) -> bool:
        """检查连接状态"""
        with self.lock:
            return self._connected and self.ws is not None

    def _setup_signals(self):
        self.ws_worker.signals.message_received.connect(
            self._on_message_received)
        self.ws_worker.signals.error.connect(
            lambda e: logger.error(f"WebSocket Error: {e}"))
        self.ws_worker.signals.connection_state.connect(
            self._on_connection_state)

    def _on_connection_state(self, state: bool):
        """处理连接状态变化"""
        with self.lock:
            self._connected = state

        if self.connection_cb:
            self.connection_cb(state)

    @Slot(MessageHeader, dict)
    def _on_message_received(self, header: MessageHeader, payload: dict):
        if self.message_cb:
            self.message_cb(header, payload)

    def run(self):
        """启动客户端。多次调用会先停止旧的 worker 再启动。"""
        with self.lock:
            if self._workers_started:
                self.ws_worker.stop_event.set()
                self.heartbeat_worker.stop_event.set()
                self.thread_pool.waitForDone(1000) 

            if not self.uri:
                logger.error("Cannot run client: URI is not configured.")
                return

            self.ws_worker.stop_event.clear()
            self.heartbeat_worker.stop_event.clear()

            self.thread_pool.start(self.ws_worker)
            self.thread_pool.start(self.heartbeat_worker)
            self._workers_started = True

    def send_raw_message(self, message: str) -> bool:
        """发送原始消息，返回是否发送成功"""
        with self.lock:
            if not self._connected or not self.ws:
                logger.warning("Cannot send message: Not connected")
                return False
            try:
                self.ws.send(message)
                return True
            except ConnectionClosed:
                logger.warning("Cannot send message: Connection closed")
                self._connected = False
                return False
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                return False

    def stop(self):
        """停止客户端"""
        logger.debug("Stopping WebSocket client...")
        self.ws_worker.stop_event.set()
        self.heartbeat_worker.stop_event.set()

        with self.lock:
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                    logger.warning(f"Error closing websocket: {e}")
            self._connected = False
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
        self.client: Optional[WebSocketClient] = None
        self.config_manager = ConnectionConfigManager()
        self.signal_dict: Dict[str, List[SignalInstance]] = defaultdict(list)
        self._pending_requests: Dict[str, RequestDict] = {}
        self._started_emitted_this_session = False
        self._requests_mutex = QMutex()
        self._subscriptions_mutex = QMutex()
        self._session_state_mutex = QMutex()

    def _create_client(self):
        """创建并配置WebSocketClient实例"""
        if self.client:
            self.client.stop()
        self.client = WebSocketClient(
            message_cb=self.sort_data,
            connection_cb=self._handle_connection_change
        )

    def _handle_connection_change(self, is_connected: bool) -> None:
        """处理连接状态变化，用于触发 started 信号"""
        with QMutexLocker(self._session_state_mutex):
            if is_connected and not self._started_emitted_this_session:
                self.started.emit()
                self._started_emitted_this_session = True
            elif not is_connected:
                self._started_emitted_this_session = False

    def start(self) -> None:
        """
        启动消息处理器。
        现在包含检查配置、尝试自动连接或显示登录对话框的逻辑。
        """
        env_port = os.getenv("PORT")
        if env_port:
            logger.info(
                f"Found PORT environment variable: {env_port}. Connecting...")
            self._attempt_connection("127.0.0.1", int(
                env_port), os.getenv("TOKEN", "疯狂星期四V我50"), single_attempt=False)
            return

        saved_config = self.config_manager.load_config()

        self._show_login_dialog(saved_config)

    def _show_login_dialog(self, initial_details: Optional[ConnectionDetails] = None):
        """创建并显示登录对话框"""
        dialog = LoginDialog(initial_details=initial_details)
        dialog.connect_requested.connect(
            lambda h, p, t, r: self._handle_login_request(
                dialog, h, p, t, r)
        )
        dialog.exec()

    def _handle_login_request(self, dialog: LoginDialog, host: str, port: int, token: str, remember: bool):
        """处理来自登录对话框的连接请求"""

        def on_success():
            logger.info("Connection successful from dialog.")
            if remember:
                details = ConnectionDetails(
                    host=host, port=port, token=token, remember=remember)
                self.config_manager.save_config(details)
            dialog.connection_successful()

        def on_failure(error_msg: str):
            logger.warning(f"Connection failed from dialog: {error_msg}")
            if "Connection refused" in error_msg:
                error_msg = "连接被拒绝。请检查服务器地址、端口和防火墙设置。"
            elif "timed out" in error_msg:
                error_msg = "连接超时。请检查网络连接或服务器是否正在运行。"
            dialog.show_error(error_msg)

        self._attempt_connection(
            host, port, token, on_success=on_success, on_failure=on_failure, single_attempt=True)

    def _attempt_connection(
        self,
        host: str,
        port: int,
        token: str,
        on_success: Optional[Callable[[], None]] = None,
        on_failure: Optional[Callable[[str], None]] = None,
        single_attempt: bool = False
    ):
        """
        配置并运行客户端，并使用一次性信号连接来处理连接结果。
        """
        self._create_client()
        assert self.client is not None, "Client must be initialized by _create_client"

        self.client.single_attempt = single_attempt
        self.client.had_successful_connection = False
        self.client.configure(host, port, token)

        _handled = False

        def handle_result(state: bool):
            nonlocal _handled
            if _handled:
                return

            _handled = True

            self._cleanup_temp_callbacks()

            if state:
                if on_success:
                    on_success()
            else:
                if on_failure:
                    on_failure("连接失败。")

        def handle_error(error_msg: str):
            nonlocal _handled
            if _handled:
                return

            _handled = True

            self._cleanup_temp_callbacks()

            if on_failure:
                on_failure(error_msg)

        self._temp_connection_handler = handle_result
        self._temp_error_handler = handle_error

        self.client.ws_worker.signals.connection_state.connect(
            self._temp_connection_handler)
        self.client.ws_worker.signals.error.connect(self._temp_error_handler)

        self.client.run()

    def _cleanup_temp_callbacks(self):
        """清理临时回调和断开信号连接。"""
        try:
            if self.client:
                self.client.ws_worker.signals.connection_state.disconnect(
                    self._temp_connection_handler)
                self.client.ws_worker.signals.error.disconnect(
                    self._temp_error_handler)
        except (TypeError, RuntimeError):
            pass

        if hasattr(self, '_temp_connection_handler'):
            del self._temp_connection_handler
        if hasattr(self, '_temp_error_handler'):
            del self._temp_error_handler

    def stop(self) -> None:
        self.stopping.emit()
        if self.client:
            self.client.stop()

        with QMutexLocker(self._requests_mutex):
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

        logger.info("ws会话终止")

    def send_request(
        self,
        method: str,
        success_signal: Optional[SignalInstance] = None,
        error_signal: Optional[SignalInstance] = None,
        timeout: float = 3.0,
        **params: Any
    ) -> None:
        if not self.client:
            if error_signal:
                error_signal.emit(
                    "Client not initialized. Cannot send request.")
            else:
                logger.error("Client not initialized. Cannot send request.")
            return
        msg_id = str(uuid.uuid4())
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handle_timeout(msg_id))

        with QMutexLocker(self._requests_mutex):
            self._pending_requests[msg_id] = {
                "timer": timer,
                "success_signal": success_signal,
                "error_signal": error_signal
            }

        header = MessageHeader(
            msg_id=msg_id, msg_type="request", correlation_id=msg_id, timestamp=time.time())
        payload = RequestPayload(method=method, params=params)
        message = ProtocolMessage.encode(header, payload.model_dump())

        timer.start(int(timeout * 1000))

        if not self.client.send_raw_message(message):
            self._cleanup_request(msg_id)
            if error_signal:
                error_signal.emit("Failed to send request: Not connected")

    def _handle_timeout(self, msg_id: str):
        with QMutexLocker(self._requests_mutex):
            if msg_id in self._pending_requests:
                request_info = self._pending_requests.pop(msg_id)
                error_signal = request_info.get("error_signal")
            else:
                return

        if error_signal:
            error_signal.emit(f"Request timeout for {msg_id}")
        else:
            logger.warning(
                f"Request timeout for {msg_id} with no error signal.")

        request_info["timer"].deleteLater()

    def _cleanup_request(self, msg_id: str):
        """线程安全地清理请求资源"""
        with QMutexLocker(self._requests_mutex):
            if msg_id in self._pending_requests:
                request_info = self._pending_requests.pop(msg_id)
                request_info["timer"].stop()
                request_info["timer"].deleteLater()

    def sort_data(self, header: MessageHeader, payload: Dict) -> None:
        if header.msg_type == "response" and header.correlation_id:
            self._handle_response(header.correlation_id, payload)
        else:
            with QMutexLocker(self._subscriptions_mutex):
                signals_to_emit = list(
                    self.signal_dict.get(header.msg_type, []))

            for signal in signals_to_emit:
                try:
                    signal.emit(header.msg_type, payload)
                except RuntimeError as e:
                    if "deleted" in str(e).lower():
                        with QMutexLocker(self._subscriptions_mutex):
                            if signal in self.signal_dict[header.msg_type]:
                                self.signal_dict[header.msg_type].remove(
                                    signal)
                    else:
                        raise e

    def fake_message(
        self,
        msg_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        伪造一个来自服务端的消息并进行分发。

        Args:
            msg_type (str): 消息类型。
            payload (Dict[str, Any]): 消息的载荷。
            correlation_id (Optional[str], optional): 如果要模拟对某个请求的响应，
                                                    请提供原始请求的 msg_id。
                                                    默认为 None。
        """

        header = MessageHeader(
            msg_id=f"fake-{uuid.uuid4()}",
            msg_type=msg_type,
            timestamp=time.time(),
            correlation_id=correlation_id
        )
        self.sort_data(header, payload)

    def _handle_response(self, msg_id: str, payload: Dict):
        with QMutexLocker(self._requests_mutex):
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
                    logger.error(
                        f"An Exception occurred while processing {error}")
            elif success_signal := request_info["success_signal"]:
                success_signal.emit(response)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise e

    def subscribe(self, *types: str, signal: SignalInstance) -> None:
        """订阅指定类型的消息"""
        if not types:
            raise ValueError("At least one type required")
        with QMutexLocker(self._subscriptions_mutex):
            for type_ in types:
                self.signal_dict[type_].append(signal)

    def unsubscribe(self, signal: SignalInstance, *types: str) -> None:
        """
        取消订阅消息。这一操作相对昂贵, 大部分场景下不需要使用, `MessageHandler`自身会处理失效的信号。

        Args:
            signal (SignalInstance): 要取消订阅的信号实例。
            *types (str): 可选参数。要取消订阅的特定消息类型。
                          如果未提供，则会从所有消息类型中移除该信号。
        """
        with QMutexLocker(self._subscriptions_mutex):
            if not types:
                for type_key in list(self.signal_dict.keys()):
                    while signal in self.signal_dict[type_key]:
                        self.signal_dict[type_key].remove(signal)

                    if not self.signal_dict[type_key]:
                        del self.signal_dict[type_key]
            else:
                for type_ in types:
                    if type_ in self.signal_dict:
                        while signal in self.signal_dict[type_]:
                            self.signal_dict[type_].remove(signal)

                        if not self.signal_dict[type_]:
                            del self.signal_dict[type_]


# 全局实例
talker = MessageHandler()
