import time
import ujson
from typing import Dict, List, Literal, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QPoint, Signal
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QCheckBox, QListWidget,
                               QListWidgetItem, QLabel, QWidget, QApplication,
                               QMenu, QScrollBar)

from .utils.client import talker
from .utils.BotTools import BotToolKit
from .utils.Qcomponents.networkmanager import BubbleNetworkManager
from .utils.conn import get_database, AsyncQuerySignal
from .Bubble.MessageBubble import MessageBubble, MetadataType
from .utils.tealog import logger
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
    """消息主页面"""

    MAX_AUTO_SCROLL_MESSAGES = 50  # 自动滚动模式下的最大消息数
    LOAD_COUNT = 20    # 每次加载消息数
    ACCENT_COLOR = "#38A5FD"
    msg_call_signal = Signal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._auto_scroll = True
        # 状态枚举: 显示中、隐藏、搜索中、加载更早消息、进入页面拉取消息
        self.state: Literal["on_show", "hidden", "searching",
                            "loading_earlier", "loading"] = "hidden"
        self.qnam = BubbleNetworkManager().qnam

        # 时间戳范围追踪
        self.earliest_loaded_ts = None  # 当前加载的最早时间戳
        self.earliest_loaded_id = None  # 当前加载的最早消息ID
        self.search_keywords = []       # 搜索关键词

        self.reached_earliest = False  # 是否已到达最早消息

        self._setup_ui()
        self._setup_context_menu()
        self._connect_signals()

        # 监听滚动事件
        self.list_widget.verticalScrollBar().valueChanged.connect(
            self._handle_scroll
        )

    def _connect_signals(self):
        """连接信号"""
        self.msg_call_signal.connect(self.set_message)
        talker.subscribe("message", "call_api", signal=self.msg_call_signal)

    def _handle_scroll(self, value):
        """处理滚动事件"""
        if self.state in ["loading_earlier", "searching"]:
            return

        scrollbar = self.list_widget.verticalScrollBar()
        # 当滚动到顶部附近时加载更早消息
        if scrollbar.value() <= scrollbar.maximum() * 0.1:
            self._load_earlier_messages()

    def _load_earlier_messages(self):
        """加载更早的消息"""
        if self.state != "on_show" or self.reached_earliest:
            return

        if self.earliest_loaded_id is None:
            # 如果还没有加载任何消息，则不执行加载更早消息的操作
            return

        self.state = "loading_earlier"
        signal = AsyncQuerySignal()
        signal.finished.connect(self._handle_earlier_messages)

        # 修改查询以确保正确的时间顺序
        get_database().execute_async(
            """
            SELECT id, meta, content, bot, timestamps 
            FROM Message
            WHERE id < ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.earliest_loaded_id, self.LOAD_COUNT),
            callback_signal=signal,
            for_write=False
        )

    def _handle_earlier_messages(self, results: List[Tuple], error: Exception):
        """处理较早消息的加载结果"""
        if error:
            self.state = "on_show"
            return

        if not results:
            self.reached_earliest = True
            self.state = "on_show"
            return

        # 更新最早时间戳和ID
        new_earliest_id = results[-1][0]  # 使用最后一条消息的ID
        self.earliest_loaded_id = new_earliest_id

        # 保存当前滚动位置和可视区域顶部项
        scrollbar = self.list_widget.verticalScrollBar()
        current_scroll = scrollbar.value()
        first_visible_item = self.list_widget.itemAt(0, 0)

        # 添加新消息到顶部
        for _, meta, content, bot, _ in results:
            meta = ujson.loads(meta)
            item = QListWidgetItem()
            bubble = MessageBubble(meta, content,
                                   BotToolKit.color.get(bot),
                                   self.list_widget, item, self.qnam)
            self.list_widget.insertItem(0, item)
            self.list_widget.setItemWidget(item, bubble)

        # 等待布局更新
        QTimer.singleShot(100, lambda: self._adjust_scroll_position(
            current_scroll, first_visible_item, len(results)))
        self.state = "on_show"

    def _adjust_scroll_position(self, previous_position: int, first_visible_item: QListWidgetItem, added_count: int):
        """调整滚动位置以保持视觉连续性"""
        if not first_visible_item:
            return

        # 计算新增消息的总高度
        total_height = 0
        for i in range(added_count):
            item = self.list_widget.item(i)
            if item:
                total_height += self.list_widget.visualItemRect(
                    item).height() + self.list_widget.spacing()

        # 设置新的滚动条位置，保持视觉连续性
        scrollbar = self.list_widget.verticalScrollBar()
        new_scroll_position = previous_position + total_height
        scrollbar.setValue(new_scroll_position)

        # 确保原来的顶部项仍然可见
        if first_visible_item and self.list_widget.row(first_visible_item) >= 0:
            self.list_widget.scrollToItem(
                first_visible_item, QListWidget.ScrollHint.PositionAtTop)

    def search_messages(self, keywords: List[str]):
        """搜索消息"""
        if not keywords:
            return

        self.search_keywords = keywords
        self.state = "searching"
        self.list_widget.clear()

        fts_query = ' OR '.join(keywords)

        query = """
            SELECT rowid, bm25(message_for_fts) as score
            FROM message_for_fts
            WHERE plaintext MATCH ?
            AND bm25(message_for_fts) < ?
            ORDER BY bm25(message_for_fts) DESC
            LIMIT 300
        """

        signal = AsyncQuerySignal()
        signal.finished.connect(self._handle_search_results)

        get_database().execute_async(
            query,
            (fts_query, 0.75),
            callback_signal=signal,
            for_write=False
        )

    def _handle_search_results(self, results: List[Tuple], error: Exception):
        if error or not results:
            return

        rowids = [rowid[0] for rowid in results]

        placeholders = ','.join('?' * len(rowids))
        query = f"""
            SELECT meta, content, bot
            FROM Message
            WHERE id IN ({placeholders})
        """

        signal = AsyncQuerySignal()
        signal.finished.connect(self._show_search_results)

        get_database().execute_async(
            query,
            tuple(rowids),
            callback_signal=signal,
            for_write=False
        )

    def _show_search_results(self, results: List[Tuple], error: Exception):
        """处理搜索结果"""
        if error:
            self.state = "on_show"
            return

        self.list_widget.clear()
        for meta, content, bot in results:
            meta = ujson.loads(meta)
            self.add_message(meta, content, BotToolKit.color.get(bot))

    def exit_search(self):
        """退出搜索模式"""
        self.search_keywords = []
        self.list_widget.clear()
        self.state = "on_show"
        self.earliest_loaded_ts = None
        self.earliest_loaded_id = None
        self.reached_earliest = False
        self.get_and_set_recent_msg(1, self.LOAD_COUNT)

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
        """添加标题，并在右侧添加一个样式相同的 QLabel"""
        title_layout = QHBoxLayout()

        title = QLabel("消息")
        title.setStyleSheet(
            f"color: {self.ACCENT_COLOR}; font-size: 18px; font-weight: bold;")
        title_layout.addWidget(title)

        right_label = QLabel("-请不要在此页面挂机")
        right_label.setStyleSheet(
            f"color: {self.ACCENT_COLOR}; font-size: 10px; font-weight: bold;")

        title_layout.addStretch()
        title_layout.addWidget(right_label)

        layout.addLayout(title_layout)

    def _setup_message_list(self, layout: QVBoxLayout) -> None:
        """设置消息列表"""
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollBar(ModernScrollBar())
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self.list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(
            self._show_context_menu)

    def _show_context_menu(self, pos: QPoint) -> None:
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
        if widget := self.list_widget.itemWidget(item):  # type: ignore
            widget: MessageBubble
            QApplication.clipboard().setText(widget.original_content)

    def add_message(self, metadata: MetadataType, content: str,
                    accent_color: Optional[str] = None) -> None:
        """添加新消息"""
        metadata = metadata.copy()
        if time_ := metadata.get("time"):
            try:
                if time_[0]:
                    local_time = time.localtime(int(time_[0]))
                    formatted_time = time.strftime(
                        "%m-%d %H:%M:%S", local_time)
            except Exception as e:
                logger.warning(f"添加消息时发生错误 {e}")
                import traceback
                traceback.print_exc()
            else:
                metadata["time"] = (formatted_time, time_[1])  # type: ignore

        QTimer.singleShot(0, lambda: self._safe_add_row(
            metadata, content, accent_color or self.ACCENT_COLOR))

    def _safe_add_row(self, metadata: MetadataType, content: str,
                      accent_color: str) -> None:
        """安全添加消息行"""
        # 在自动滚动模式下才限制消息数量
        if self._auto_scroll:
            while self.list_widget.count() >= self.MAX_AUTO_SCROLL_MESSAGES:
                oldest_item = self.list_widget.takeItem(0)
                if oldest_widget := self.list_widget.itemWidget(oldest_item):
                    if isinstance(oldest_widget, MessageBubble):
                        oldest_widget.cleanup()

        item = QListWidgetItem()
        bubble = MessageBubble(metadata, content, accent_color,
                               self.list_widget, item, self.qnam)
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, bubble)

        if self._auto_scroll:
            self.list_widget.scrollToBottom()

    def _handle_auto_scroll(self, checked: bool) -> None:
        """处理自动滚动开关"""
        self._auto_scroll = checked

    def set_message(self, type_: str, data: Dict) -> None:
        """设置消息"""
        bot = data['bot']
        userid = data.get("userid") or bot
        timestamps = data["time"]
        content = ""
        plaintext = ""
        avatar = data.get("avatar")

        # 构建元数据
        metadata = {
            "bot": (
                bot,
                f"color: {BotToolKit.color.get(bot)}; font-weight: bold;",
            ),
            "time": (
                timestamps,
                "color: #757575; font-size: 12px;",
            ),
            "session": (
                f"会话：{data.get('session', "")}",
                "color: #616161; font-style: italic;",
            ),
            "avatar": (avatar, MessageBubble.AvatarPosition.LEFT_OUTSIDE),
            "timestamps": (timestamps, "hidden")
        }

        # 根据消息类型处理
        if type_ == "message":
            BotToolKit.counter.add_event(bot, "receive")
            segments = data.get("content", [])
            content_parts = []
            plaintext_parts = []
            for seg_type, seg_data in segments:
                if seg_type == "text":
                    content_parts.append(seg_data.replace(
                        "*", r"\*").replace("`", r"\`"))
                    plaintext_parts.append(seg_data)
                else:
                    content_parts.append(seg_data)
            content = "".join(content_parts)
            plaintext = "".join(plaintext_parts)

        elif type_ == "call_api":
            api = data["api"]
            if api == "send_msg":
                BotToolKit.counter.add_event(bot, "send")
                segments = data.get("content", [])
                content_parts = [f"`calling api: {api}`\n"]
                plaintext_parts = []
                for seg_type, seg_data in segments:
                    if seg_type == "text":
                        content_parts.append(seg_data.replace(
                            "*", r"\*").replace("`", r"\`"))
                        plaintext_parts.append(seg_data)
                    else:
                        content_parts.append(seg_data)
                content = "".join(content_parts)
                plaintext = "".join(plaintext_parts)

        # 根据状态处理消息
        if self.state == "on_show":
            self.add_message(metadata, content, BotToolKit.color.get(bot))
        elif self.state == "searching":
            if all(kw.lower() in plaintext.lower() for kw in self.search_keywords):
                self.add_message(metadata, content, BotToolKit.color.get(bot))

        # 保存到数据库
        groupid = data["groupid"] or "私聊"
        self.insert(type_, [userid, groupid, bot, timestamps, content,
                            metadata, plaintext])

    def insert(self, type_: str, params: List):
        """插入消息到数据库"""
        params[5] = ujson.dumps(params[5])
        final_params = tuple(params)

        get_database().execute_async("""
            INSERT INTO Message (user, group_id, bot, timestamps, content, meta, plaintext)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, final_params, for_write=True)

    def get_and_set_recent_msg(self, start: int, end: int):
        """获取最近的消息"""
        if start < 1 or end < start:
            raise ValueError("start 和 end 参数不合法")

        limit = end - start + 1
        offset = start - 1
        signal = AsyncQuerySignal()
        signal.finished.connect(self._handle_recent_messages)

        get_database().execute_async(
            """
            SELECT id, meta, content, bot, timestamps 
            FROM Message
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
            callback_signal=signal,
            for_write=False
        )

    def _handle_recent_messages(self, results: List[Tuple], error: Exception):
        """处理最近消息的加载结果"""
        if error:
            return

        if not results:
            return

        # 更新时间戳和ID范围
        ids = [r[0] for r in results]
        self.earliest_loaded_id = min(ids)

        # 显示消息
        for msg_id, meta, content, bot, _ in reversed(results):
            meta = ujson.loads(meta)
            self.add_message(meta, content, BotToolKit.color.get(bot))

    def on_enter(self):
        """进入页面时调用"""
        self.list_widget.clear()
        self.state = "on_show"
        self.earliest_loaded_id = None
        self.reached_earliest = False
        self.get_and_set_recent_msg(1, self.LOAD_COUNT)

    def on_leave(self):
        """离开页面时调用"""
        self.state = "hidden"
        self.list_widget.clear()
