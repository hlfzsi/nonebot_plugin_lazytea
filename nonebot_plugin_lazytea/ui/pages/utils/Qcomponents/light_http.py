import http.server
import traceback
import uuid
import time
import threading
from typing import Dict, Optional, Any

import orjson
import portpicker
from PySide6.QtCore import QObject, Signal, QThread, QCoreApplication
from PySide6.QtWidgets import QApplication

from ....protocol import ResponsePayload
from ..client import talker
from ..tealog import logger


class TemporaryResponseHandler(QObject):
    success_signal = Signal(ResponsePayload)

    def __init__(self, request_id: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.request_id = request_id
        self.success_signal.connect(self._on_success)

    def _on_success(self, payload: ResponsePayload):
        RequestHandler.resolve_request(self.request_id, payload)
        TalkerDispatcher.get_instance()._cleanup_handler(self.request_id)
        self.deleteLater()


class TalkerDispatcher(QObject):
    request_received = Signal(str, dict, str)

    _instance: Optional["TalkerDispatcher"] = None
    _lock = threading.Lock()
    _temp: Dict[str, TemporaryResponseHandler] = {}
    _temp_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        if TalkerDispatcher._instance is not None:
            raise RuntimeError(
                "TalkerDispatcher 是一个单例类，请使用 get_instance() 获取实例")
        self.request_received.connect(self._process_request)

    @classmethod
    def get_instance(cls) -> "TalkerDispatcher":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    main_thread = QCoreApplication.instance().thread()  # type: ignore
                    cls._instance = TalkerDispatcher()
                    cls._instance.moveToThread(main_thread)
        return cls._instance

    def _process_request(self, method: str, params: Dict, request_id: str):
        temp_handler = TemporaryResponseHandler(request_id)

        with self._temp_lock:
            self._temp[request_id] = temp_handler

        try:
            talker.send_request(
                method=method,
                success_signal=temp_handler.success_signal,
                **params
            )
        except Exception as e:
            error_payload = ResponsePayload(
                code=500, error=f"发送请求失败: {str(e)}", data=None)
            RequestHandler.resolve_request(request_id, error_payload)
            self._cleanup_handler(request_id)
            temp_handler.deleteLater()

    def _cleanup_handler(self, request_id: str):
        with self._temp_lock:
            if request_id in self._temp:
                self._temp.pop(request_id)


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP 请求处理器"""
    _path_to_html: Dict[str, str] = {}
    _pending_requests: Dict[str, Dict[str, Any]] = {}
    _pending_lock = threading.Lock()

    _html_lock = threading.Lock()

    def log_message(self, format: str, *args: Any):
        return

    @classmethod
    def set_html_content(cls, html_content: str):
        cls.add_html_route("/", html_content)

    @classmethod
    def add_html_route(cls, path: str, html_content: str):
        with cls._html_lock:
            cls._path_to_html[path] = html_content

    @classmethod
    def resolve_request(cls, request_id: str, payload: ResponsePayload):
        with cls._pending_lock:
            if request_id in cls._pending_requests:
                request_info = cls._pending_requests[request_id]
                request_info['response'] = payload
                request_info['event'].set()

    def do_GET(self):
        with self._html_lock:
            html_content = self._path_to_html.get(self.path)

        if html_content is not None:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        else:
            error_message = f"<html><body><h1>404 Not Found</h1><p>The path '{self.path}' was not found on this server.</p></body></html>"
            self.send_response(404)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(error_message.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self._add_cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            json_data = orjson.loads(post_data.decode('utf-8'))

            method_name = json_data.get("method")
            params = json_data.get("params", {})

            if not method_name:
                self.send_json_response(
                    {"error": "请求体中缺少 'method' 字段"}, status_code=400)
                return

            self._handle_post(method_name, params)
        except orjson.JSONDecodeError:
            self.send_json_response({"error": "JSON 解析失败"}, status_code=400)
        except Exception:
            traceback.print_exc()
            self.send_json_response({"error": "服务器内部错误"}, status_code=500)

    def _handle_post(self, method: str, params: Dict):
        request_id = str(uuid.uuid4())

        event = threading.Event()
        with self._pending_lock:
            self._pending_requests[request_id] = {
                'event': event, 'response': None}

        try:
            dispatcher = TalkerDispatcher.get_instance()
            dispatcher.request_received.emit(method, params, request_id)

            event_was_set = event.wait(timeout=10.0)

            if not event_was_set:
                self.send_json_response({"error": "处理请求超时"}, status_code=504)
                dispatcher._cleanup_handler(request_id)
                return

            with self._pending_lock:
                payload = self._pending_requests.get(
                    request_id, {}).get('response')

            if payload:
                self.send_json_response(payload.data)
            else:
                self.send_json_response({"error": "未知内部错误"}, status_code=500)
        finally:
            with self._pending_lock:
                self._pending_requests.pop(request_id, None)

    def _add_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers',
                         'Content-Type, Authorization, X-Requested-With')
        self.send_header('Access-Control-Max-Age', '86400')

    def send_json_response(self, content: dict, status_code: int = 200):
        try:
            if not self.wfile.closed:
                self.send_response(status_code)
                self.send_header('Content-type', 'application/json')
                self._add_cors_headers()
                self.end_headers()
                self.wfile.write(orjson.dumps(content))
            else:
                logger.error(f"连接已关闭，无法发送JSON响应 for {content}")
        except Exception as e:
            logger.error(f"发送JSON响应失败: {e}")


class ServerThread(QThread):

    def __init__(self, server: "ControllableServer"):
        super().__init__()
        self.server = server
        self.httpd: Optional[http.server.HTTPServer] = None
        QApplication.instance().aboutToQuit.connect(self.stop_server)  # type: ignore

    def run(self):
        try:
            self.httpd = http.server.ThreadingHTTPServer(
                ("", self.server.port), self.server.handler)
            self.httpd.allow_reuse_address = True
            self.server.httpd = self.httpd
            self.httpd.serve_forever()
        except Exception as e:
            if "Interrupted" not in str(e) and "cannot switch to a different thread" not in str(e):
                logger.error(f"服务器运行错误: {e}")

    def stop_server(self):
        if self.httpd:
            threading.Thread(target=self.httpd.shutdown).start()


class ControllableServer:
    _instance: Optional["ControllableServer"] = None
    _lock = threading.Lock()

    def __init__(self, port=portpicker.pick_unused_port(), handler=RequestHandler, html_content=""):

        TalkerDispatcher.get_instance()

        self.port = port
        self.handler = handler
        self.httpd: Optional[http.server.HTTPServer] = None
        self.server_thread: Optional[ServerThread] = None

        self.handler.set_html_content(html_content)

        self._state_lock = threading.Lock()

    @classmethod
    def get_instance(cls, port: int = portpicker.pick_unused_port(), html_content: str = "") -> "ControllableServer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(port, RequestHandler, html_content)
        return cls._instance

    def set_path(self, path: str, html_content: str):
        self.handler.add_html_route(path, html_content)

    def start(self) -> bool:
        with self._state_lock:
            if self.server_thread and self.server_thread.isRunning():
                return False
            self.server_thread = ServerThread(self)
            self.server_thread.start()
            time.sleep(0.1)
            return True

    def stop(self):
        thread_to_stop = None
        with self._state_lock:
            if self.server_thread and self.server_thread.isRunning():
                thread_to_stop = self.server_thread
                self.server_thread = None

        if not thread_to_stop:
            return

        try:
            thread_to_stop.stop_server()
            if thread_to_stop.wait(5000):
                logger.info("服务器线程已正常结束")
            else:
                logger.warning("警告：服务器线程等待超时")
        except Exception as e:
            logger.error(f"停止服务器时发生错误: {e}")
        finally:
            with ControllableServer._lock:
                if ControllableServer._instance is self:
                    ControllableServer._instance = None
