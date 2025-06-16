import os
import ujson
import threading
from PySide6.QtCore import QObject, QStandardPaths, QDir, Signal, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkRequest, QNetworkReply

from ..tealog import logger


QNETWORK_ACCESS_MANAGER = None


def get_network_manager():
    global QNETWORK_ACCESS_MANAGER
    if not QNETWORK_ACCESS_MANAGER:
        QNETWORK_ACCESS_MANAGER = QNetworkAccessManager()
    return QNETWORK_ACCESS_MANAGER


class BubbleNetworkManager(QObject):
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
            super().__init__()
            self._init_manager()
            self._initialized = True

    def _init_manager(self):
        self.manager = get_network_manager()

        cache = QNetworkDiskCache()
        cache_dir = os.getenv("UIDATADIR") or QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation
        )
        logger.debug(f"GUI资源缓存路径 {cache_dir}")
        QDir().mkpath(cache_dir)
        cache.setCacheDirectory(cache_dir)
        cache.setMaximumCacheSize(100 * 1024 * 1024)  # 100 MB
        self.manager.setCache(cache)

    @property
    def qnam(self):
        return self.manager


class ReleaseNetworkManager(QObject):
    # (request_type, response_data, plugin_name)
    request_finished = Signal(str, dict, str)
    _execute_request = Signal(str, str, str)  # 新增信号，用于主线程执行请求

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
        if not getattr(self, '_is_initialized', False):
            super().__init__()
            self.nam = get_network_manager()
            self._execute_request.connect(
                self._execute_get_github_release)
            self._is_initialized = True

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
