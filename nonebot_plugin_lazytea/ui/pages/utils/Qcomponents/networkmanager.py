import os
import ujson
import threading
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

QNETWORK_ACCESS_MANAGER = None
QNETWORK_ACCESS_MANAGER_LOCK = threading.Lock()


def get_network_manager():
    """
    获取全局的 QNetworkAccessManager 实例。
    """
    global QNETWORK_ACCESS_MANAGER
    if QNETWORK_ACCESS_MANAGER is None:
        with QNETWORK_ACCESS_MANAGER_LOCK:
            if QNETWORK_ACCESS_MANAGER is None:
                QNETWORK_ACCESS_MANAGER = QNetworkAccessManager()
    return QNETWORK_ACCESS_MANAGER


class ReleaseNetworkManager(QObject):
    # (request_type, response_data, plugin_name)
    request_finished = Signal(str, dict, str)
    _execute_request = Signal(str, str, str)

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self.__class__._lock:
                if not self._initialized:
                    super().__init__()
                    self.nam = get_network_manager()
                    self._execute_request.connect(
                        self._execute_get_github_release)
                    self._initialized = True

    def get_github_release(self, owner: str, repo: str, plugin_name: str):
        """获取GitHub release信息"""
        self._execute_request.emit(owner, repo, plugin_name)

    def _execute_get_github_release(self, owner: str, repo: str, plugin_name: str):
        """在主线程中实际执行GitHub release请求"""
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,
                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

        reply = self.nam.get(request)
        reply.finished.connect(
            lambda: self._handle_github_response(reply, plugin_name))

    def _handle_github_response(self, reply: QNetworkReply, plugin_name: str):
        """处理GitHub API响应"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = bytes(reply.readAll().data()).decode()
            try:
                response = ujson.loads(data)
                self.request_finished.emit("github_release", {
                    "success": True,
                    "version": response.get("tag_name", "").lstrip("v")
                },
                    plugin_name)
            except Exception as e:
                self.request_finished.emit("github_release", {
                    "success": False,
                    "error": str(e)
                },
                    plugin_name)
        else:
            self.request_finished.emit("github_release", {
                "success": False,
                "error": reply.errorString()
            },
                plugin_name)
        reply.deleteLater()
