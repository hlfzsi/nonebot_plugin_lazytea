import os
import time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                               QSizePolicy, QSpacerItem)
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtGui import QFont, QColor, QLinearGradient, QBrush, QPainter
from typing import Dict

from .base_page import PageBase
from .utils.version_check import VersionUtils
from .utils.Qcomponents.networkmanager import ReleaseNetworkManager


class VersionCheckWorker(QRunnable):
    def __init__(self, signals, current_version):
        super().__init__()
        self.signals: WorkerSignals = signals
        self.current_version = current_version
        self.is_running = True
        self.network_manager = ReleaseNetworkManager()
        self.network_manager.request_finished.connect(
            self._handle_version_response)

    def run(self):
        while self.is_running:
            try:
                self.network_manager.get_github_release(
                    "hlfzsi",
                    "nonebot_plugin_lazytea",
                    "lazytea"
                )
            except Exception as e:
                self.signals.version_result.emit(
                    "version", f"版本检查失败: {str(e)}")

            # 等待5分钟后再检查
            for _ in range(300):  # 300秒 = 5分钟
                if not self.is_running:
                    return
                time.sleep(1)

    def _handle_version_response(self, request_type: str, response_data: dict, plugin_name: str):
        """处理版本检查响应"""
        if request_type != "github_release" or plugin_name != "main_app":
            return

        if not response_data.get("success"):
            error = response_data.get("error", "未知错误")
            self.signals.version_result.emit(
                "version", f"版本检查失败: {error}")
            return

        remote_version = response_data.get("version", "")
        if not remote_version:
            self.signals.version_result.emit(
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

        self.signals.version_result.emit("version", version_text)

    def stop(self):
        self.is_running = False


class WorkerSignals(QObject):
    version_result = Signal(str, str)  # (key, content)


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

        # 绘制渐变背景
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(245, 245, 245))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)

        # 绘制边框
        painter.setPen(self._border_color)
        painter.drawRoundedRect(0, 0, self.width()-1, self.height()-1, 12, 12)


class CardManager(QObject):
    """卡片布局管理器"""
    updateSignal = Signal(str, str)  # (key, content)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: Dict[str, QWidget] = {}
        self.labels: Dict[str, QLabel] = {}
        self.updateSignal.connect(self._handle_update)

    def _handle_update(self, key: str, content: str):
        """处理更新信号的槽函数"""
        if key in self.labels:
            self.labels[key].setText(content)

    def create_card(self, config: dict) -> QWidget:
        """根据配置创建卡片"""
        card = VersionCard()
        card_layout = QHBoxLayout()
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(20)

        # 标题部分
        title_label = QLabel(f"{config['title']}：")
        title_style = f"""
            QLabel {{
                font: bold 14px 'Microsoft YaHei';
                color: #34495e;
                min-width: {config.get('title_width', 100)}px;
            }}
        """
        title_label.setStyleSheet(title_style)

        # 内容部分
        content_label = QLabel(config["content"])
        content_style = """
            QLabel {{
                font: 14px 'Microsoft YaHei';
                color: #7f8c8d;
            }}
            QLabel a {{
                {link_style}
                text-decoration: none;
            }}
        """.format(link_style=config.get("link_style", "color: #3498db;"))
        content_label.setStyleSheet(content_style)
        content_label.setOpenExternalLinks(config.get("is_link", False))
        content_label.setWordWrap(True)

        # 注册组件
        self.cards[config["key"]] = card
        self.labels[config["key"]] = content_label

        card_layout.addWidget(title_label)
        card_layout.addWidget(content_label)
        card.setLayout(card_layout)
        return card

    def update_content(self, key: str, content: str):
        """更新指定卡片内容"""
        self.updateSignal.emit(key, content)


class OverviewPage(PageBase):
    """概览页面"""
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
            "content": "2025-6-16",  # 这个日期由开发者手动提供
            "dynamic": False
        },
        {
            "key": "developer",
            "title": "开发者",
            "content": os.getenv("UIAUTHOR"),
        },
        {
            "key": "repository",
            "title": "项目地址",
            "content": "<a href='https://github.com/hlfzsi/nonebot_plugin_lazytea'>GitHub仓库</a>",
            "is_link": True
        }
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.card_manager = CardManager(self)
        self.current_version = os.getenv("UIVERSION")
        self.worker_signals = WorkerSignals()
        self.worker_signals.version_result.connect(
            self.card_manager.update_content)
        self.version_worker = None
        self._init_ui()

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
        """进入页面时启动检查任务"""
        if not self.version_worker:
            self.version_worker = VersionCheckWorker(
                self.worker_signals,
                self.current_version
            )
            QThreadPool.globalInstance().start(self.version_worker)

    def on_leave(self):
        """离开页面时清理资源"""
        if self.version_worker:
            self.version_worker.stop()
            self.version_worker = None
