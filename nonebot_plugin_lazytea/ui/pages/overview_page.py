import os
from PySide6.QtWidgets import (QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSpacerItem,
                               QSizePolicy, QApplication)
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QThread, Slot
from PySide6.QtGui import QColor, QLinearGradient, QBrush, QPainter, QFont
from typing import Dict

from .base_page import PageBase
from .utils.version_check import VersionUtils
from .utils.Qcomponents.networkmanager import ReleaseNetworkManager
from .utils.tealog import logger

class VersionCheckWorker(QObject):
    version_result = Signal(str, str)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
        self.network_manager = ReleaseNetworkManager()
        self.network_manager.request_finished.connect(
            self._handle_version_response)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_version)

    def start_checking(self):
        # 立即检查一次，然后每5分钟检查一次
        self.check_version()
        self.timer.start(5 * 60 * 1000)

    @Slot()
    def stop_checking(self):
        if self.timer.isActive():
            self.timer.stop()

    def check_version(self):
        try:
            self.network_manager.get_github_release(
                "hlfzsi",
                "nonebot_plugin_lazytea",
                "lazytea"
            )
        except Exception as e:
            self.version_result.emit(
                "version", f"版本检查失败: {str(e)}")

    def _handle_version_response(self, request_type: str, response_data: dict, plugin_name: str):
        """处理版本检查响应"""
        if request_type != "github_release" or plugin_name != "lazytea":
            return

        if not response_data.get("success"):
            error = response_data.get("error", "未知错误")
            self.version_result.emit(
                "version", f"版本检查失败: {error}")
            return

        remote_version = response_data.get("version", "")
        if not remote_version:
            self.version_result.emit(
                "version", f"v{self.current_version} (获取版本信息失败)")
            return

        cmp_result = VersionUtils.compare_versions(
            remote_version, str(self.current_version))

        if cmp_result > 0:
            version_text = (
                f"v{self.current_version} <a href='https://github.com/hlfzsi/nonebot_plugin_lazytea/releases' "
                f"style='color:#e74c3c;'>（新版本 {remote_version} 可用）</a>"
            )
        else:
            version_text = (
                f"v{self.current_version} "
                f"<span style='color:#27ae60;'>（已是最新）</span>"
            )

        self.version_result.emit("version", version_text)


class VersionCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self._border_color = QColor(220, 220, 220)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(245, 245, 245))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.setPen(self._border_color)
        painter.drawRoundedRect(0, 0, self.width()-1, self.height()-1, 12, 12)


class CardManager(QObject):
    updateSignal = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: Dict[str, QWidget] = {}
        self.labels: Dict[str, QLabel] = {}
        self.updateSignal.connect(self._handle_update)

    @Slot(str, str)
    def _handle_update(self, key: str, content: str):
        if key in self.labels:
            self.labels[key].setText(content)

    def create_card(self, config: dict) -> QWidget:
        card = VersionCard()
        card_layout = QHBoxLayout()
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(20)
        title_label = QLabel(f"{config['title']}：")
        title_style = f"QLabel {{ font: bold 14px 'Microsoft YaHei'; color: #34495e; min-width: {config.get('title_width', 100)}px; }}"
        title_label.setStyleSheet(title_style)
        content_label = QLabel(config["content"])
        content_style = f"QLabel {{ font: 14px 'Microsoft YaHei'; color: #7f8c8d; }} QLabel a {{ {config.get('link_style', 'color: #3498db;')} text-decoration: none; }}"
        content_label.setStyleSheet(content_style)
        content_label.setOpenExternalLinks(config.get("is_link", False))
        content_label.setWordWrap(True)
        self.cards[config["key"]] = card
        self.labels[config["key"]] = content_label
        card_layout.addWidget(title_label)
        card_layout.addWidget(content_label)
        card.setLayout(card_layout)
        return card

    def update_content(self, key: str, content: str):
        self.updateSignal.emit(key, content)

class OverviewPage(PageBase):
    """概览页面"""
    request_stop_worker = Signal()

    CARD_CONFIGS = [
        {
            "key": "version",
            "title": "版本信息",
            "content": "v{version}",
            "title_width": 100,
            "link_style": "color: #3498db;",
            "dynamic": True
        },
        {
            "key": "update_date",
            "title": "更新日期",
            "content": "2025-7-29",  # 这个日期由开发者手动提供
            "dynamic": False
        },
        {
            "key": "developer",
            "title": "开发者",
            "content": os.getenv("UIAUTHOR"),
        },
        {
            "key": "thanks",
            "title": "鸣谢",
            "content": "感谢NoneBot成员为本插件审核的付出, 特别感谢<a href='https://github.com/yanyongyu'>@yanyongyu</a>",
            "is_link": True
        },
        {
            "key": "repository",
            "title": "项目地址",
            "content": "<a href='https://github.com/hlfzsi/nonebot_plugin_lazytea'>GitHub仓库</a> 点个star谢谢喵",
            "is_link": True
        }
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.card_manager = CardManager(self)
        self.current_version = os.getenv("UIVERSION", "0.0.0")  # 添加默认值以防万一
        self.worker = None
        self.worker_thread = None
        self._init_ui()
        if app := QApplication.instance():
            app.aboutToQuit.connect(self._cleanup_worker)

    def _init_ui(self):
        """初始化界面布局"""
        self.qvlayout = QVBoxLayout()
        self.qvlayout.setContentsMargins(30, 30, 30, 30)
        self.qvlayout.setSpacing(15)

        # 标题
        title = QLabel("系统概览")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Microsoft YaHei", 18, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #2c3e50;")

        self.qvlayout.addWidget(title)
        self.qvlayout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # 动态创建卡片
        for config in self.CARD_CONFIGS:
            card_config = config.copy()
            if "{version}" in card_config["content"]:
                card_config["content"] = card_config["content"].format(
                    version=self.current_version)
            self.qvlayout.addWidget(self.card_manager.create_card(card_config))

        self.qvlayout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.setLayout(self.qvlayout)

        # 背景渐变
        self.setAutoFillBackground(True)
        palette = self.palette()
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(246, 249, 255))
        gradient.setColorAt(1, QColor(233, 240, 255))
        palette.setBrush(self.backgroundRole(), QBrush(gradient))
        self.setPalette(palette)

    def on_enter(self):
        """当页面进入时，启动后台线程进行版本检查"""
        if not self.worker_thread:
            self.worker_thread = QThread()
            self.worker = VersionCheckWorker(self.current_version)
            self.worker.moveToThread(self.worker_thread)

            self.worker.version_result.connect(
                self.card_manager.update_content)
            self.worker_thread.started.connect(self.worker.start_checking)
            self.worker_thread.finished.connect(self.worker.deleteLater)

            self.request_stop_worker.connect(self.worker.stop_checking)

            self.worker_thread.start()

    def _cleanup_worker(self):
        """
        停止工作线程。
        """
        if self.worker_thread and self.worker_thread.isRunning():
            self.request_stop_worker.emit()
            self.worker_thread.quit()
            if not self.worker_thread.wait(500):
                self.worker_thread.terminate()
                self.worker_thread.wait()

        self.worker_thread = None
        self.worker = None
        logger.debug("overview线程停止")

    def on_leave(self):
        self._cleanup_worker()
