import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                             QSizePolicy, QSpacerItem)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QLinearGradient, QBrush, QPainter
import re
import asyncio
from typing import Dict, Optional

import qasync

from .base_page import PageBase
from .utils.version_check import VersionUtils


class VersionCard(QWidget):
    """可复用的信息卡片组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._border_color = QColor(220, 220, 220)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制渐变背景
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(245, 245, 245))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)

        # 绘制边框
        painter.setPen(self._border_color)
        painter.drawRoundedRect(0, 0, self.width()-1, self.height()-1, 12, 12)


class CardManager(QObject):
    """卡片布局管理器"""
    updateSignal = pyqtSignal(str, str)  # (key, content)

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
    """优化后的概览页面"""
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
            "content": "2024-4-19",
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
            "content": "<a href='https://github.com/example'>GitHub仓库</a>",
            "is_link": True
        }
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = os.getenv("UIVERSION")
        self._refresh_timer: Optional[QTimer] = None
        self._fetch_task: Optional[asyncio.Task] = None
        self.card_manager = CardManager(self)
        self._init_ui()

    def _init_ui(self):
        """初始化界面布局"""
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(15)

        # 标题
        title = QLabel("系统概览")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont("Microsoft YaHei", 18, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #2c3e50;")

        self.layout.addWidget(title)
        self.layout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 动态创建卡片
        for config in self.CARD_CONFIGS:
            card_config = config.copy()
            if "{version}" in card_config["content"]:
                card_config["content"] = card_config["content"].format(
                    version=self.current_version)
            self.layout.addWidget(self.card_manager.create_card(card_config))

        self.layout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.setLayout(self.layout)

        # 背景渐变
        self.setAutoFillBackground(True)
        palette = self.palette()
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(246, 249, 255))
        gradient.setColorAt(1, QColor(233, 240, 255))
        palette.setBrush(self.backgroundRole(), QBrush(gradient))
        self.setPalette(palette)

    async def _fetch_remote_version(self):
        """获取远程版本信息"""
        try:
            # 模拟网络请求
            await asyncio.sleep(1)
            return "1.1.0"
        except Exception as e:
            self.card_manager.update_content("version", f"版本检查失败: {str(e)}")
            return None

    async def _check_version_task(self):
        """版本检查任务"""
        while True:
            remote_version = await self._fetch_remote_version()
            if not remote_version:
                await asyncio.sleep(60)
                continue

            cmp_result = VersionUtils.compare_versions(
                remote_version, self.current_version)
            if cmp_result > 0:
                self.card_manager.update_content(
                    "version",
                    f"v{self.current_version} <a href='https://example.com/update' style='color:#e74c3c;'>"
                    f"（新版本 {remote_version} 可用）</a>"
                )
            else:
                self.card_manager.update_content(
                    "version",
                    f"v{self.current_version} <span style='color:#27ae60;'>（已是最新）</span>"
                )
            await asyncio.sleep(300)

    async def on_enter(self):
        """进入页面时启动检查任务"""
        if not hasattr(self, '_check_task'):
            self._check_task = asyncio.create_task(self._check_version_task())

    @qasync.asyncSlot()
    async def on_leave(self):
        """离开页面时清理资源"""
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
