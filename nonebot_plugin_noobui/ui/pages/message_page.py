import asyncio
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QCheckBox, QListWidget,
                             QListWidgetItem, QLabel, QWidget, QApplication,
                             QMenu, QScrollBar)

from .utils.client import talker
from .utils.BotTools import BotToolKit
from .Bubble.MessageBubble import MessageBubble, MetadataType
from .base_page import PageBase


class ModernScrollBar(QScrollBar):
    """现代风格滚动条组件"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_style()

    def _setup_style(self) -> None:
        """初始化滚动条样式"""
        self.setStyleSheet("""
            QScrollBar:vertical {
                background: #F5F5F5;
                width: 10px;
                margin: 2px 0 2px 0;
            }
            QScrollBar::handle:vertical {
                background: #C0C0C0;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)


class MessagePage(PageBase):
    """消息中心主页面"""

    MAX_ROWS = 300
    ACCENT_COLOR = "#2196F3"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._auto_scroll = True
        self._setup_ui()
        self._setup_context_menu()
        asyncio.ensure_future(self.get_message())

    def _setup_ui(self) -> None:
        """初始化页面UI"""
        self.setStyleSheet("background: #FAFAFA;")
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)

        self._add_title(main_layout)
        self._setup_message_list(main_layout)
        self._setup_control_bar(main_layout)

        self.setLayout(main_layout)

    def _add_title(self, layout: QVBoxLayout) -> None:
        """添加标题"""
        title = QLabel("消息中心")
        title.setStyleSheet(
            f"color: {self.ACCENT_COLOR}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

    def _setup_message_list(self, layout: QVBoxLayout) -> None:
        """设置消息列表"""
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollBar(ModernScrollBar())
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setStyleSheet("""
            QListWidget { 
                background: transparent; 
                border: none; 
            }
            QListWidget::item { 
                border: none; 
                margin: 8px 0; 
                padding: 0; 
            }
        """)
        self.list_widget.setSpacing(8)
        layout.addWidget(self.list_widget)

    def _setup_control_bar(self, layout: QVBoxLayout) -> None:
        """设置控制栏"""
        control_bar = QWidget()
        control_bar.setStyleSheet(
            "background: #FFFFFF; border-radius: 8px; padding: 6px;")
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(12, 6, 12, 6)

        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setStyleSheet("""
            QCheckBox { 
                color: #616161; 
                font-size: 13px; 
            }
            QCheckBox::indicator { 
                width: 16px; 
                height: 16px; 
            }
        """)
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self._handle_auto_scroll)

        control_layout.addStretch()
        control_layout.addWidget(self.auto_scroll_check)
        layout.addWidget(control_bar)

    def _setup_context_menu(self) -> None:
        """设置上下文菜单"""
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(
            self._show_context_menu)

    def _show_context_menu(self, pos: QEvent) -> None:
        """显示上下文菜单"""
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { 
                background: #FFFFFF; 
                border: 1px solid #E0E0E0; 
                padding: 8px; 
                border-radius: 4px; 
            }
            QMenu::item { 
                color: #424242; 
                padding: 8px 24px; 
                font-size: 13px; 
                min-width: 120px; 
            }
            QMenu::item:selected { 
                background: #2196F3; 
                color: white; 
                border-radius: 4px; 
            }
        """)
        copy_action = menu.addAction("📋 复制内容")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == copy_action:
            self._copy_content(item)

    def _copy_content(self, item: QListWidgetItem) -> None:
        """复制消息内容"""
        if widget := self.list_widget.itemWidget(item):
            QApplication.clipboard().setText(widget.original_content)

    def add_message(
        self,
        metadata: MetadataType,
        content: str,
        accent_color: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> None:
        """添加新消息"""
        if avatar_url:
            metadata = metadata.copy()
            metadata['avatar'] = (avatar_url, "")

        QTimer.singleShot(0, lambda: self._safe_add_row(
            metadata, content, accent_color or self.ACCENT_COLOR))

    def _safe_add_row(
        self,
        metadata: MetadataType,
        content: str,
        accent_color: str
    ) -> None:
        """安全添加消息行"""
        while self.list_widget.count() >= self.MAX_ROWS:
            oldest_item = self.list_widget.takeItem(0)
            if oldest_widget := self.list_widget.itemWidget(oldest_item):
                oldest_widget.cleanup()

        item = QListWidgetItem()
        bubble = MessageBubble(metadata, content, accent_color,
                               self.list_widget, item)
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, bubble)

        if self._auto_scroll:
            self.list_widget.scrollToBottom()

    def _handle_auto_scroll(self, checked: bool) -> None:
        """处理自动滚动开关"""
        self._auto_scroll = checked

    async def get_message(self) -> None:
        """获取消息数据并处理"""
        while True:
            msg_type, data = await talker.get_message("message", "call_api")
            bot = data['bot']
            # 构建元数据
            metadata = {
                "bot": (
                    data["bot"],
                    f"color: {BotToolKit.color.get(bot)}; font-weight: bold;",
                ),
                "time": (
                    data.get("time", ""),
                    "color: #757575; font-size: 12px;",
                ),
                "session": (
                    f"会话：{data.get('session', "")}",
                    "color: #616161; font-style: italic;",
                ),
                "avatar": (data.get("avatar"), MessageBubble.AvatarPosition.LEFT_OUTSIDE)
            }
            # 根据消息类型处理
            if msg_type == "message":
                BotToolKit.counter.add_event(bot, "receive")
                content = data["content"]
            elif msg_type == "call_api":
                api = data["api"]
                if api == "send_msg":
                    BotToolKit.counter.add_event(bot, "send")
                content = f"`calling api: {api}`\n" + \
                    data.get("message", "")
            else:
                continue  # 忽略未知消息类型

            # 添加消息
            self.add_message(metadata, content,
                             BotToolKit.color.get(bot))
