import time
from typing import Dict, List, Literal, Optional, Tuple

import orjson
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QMutex
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QCheckBox, QListWidget,
                               QListWidgetItem, QLabel, QWidget, QApplication,
                               QMenu, QScrollBar, QPushButton)

from .utils.client import talker
from .utils.token import tokenize
from .utils.BotTools import BotToolKit
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


class SearchBar(QWidget):
    """搜索状态条带"""

    def __init__(self, keywords: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet("""
            background: #E3F2FD;
            padding: 8px;
            border-radius: 4px;
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)

        search_label = QLabel(f"{','.join(keywords)}")
        search_label.setStyleSheet("font-size: 13px; color: #0D47A1;")

        self.exit_button = QPushButton("退出搜索")
        self.exit_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #0D47A1;
                color: #0D47A1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #BBDEFB;
            }
        """)

        layout.addWidget(search_label)
        layout.addStretch()
        layout.addWidget(self.exit_button)

        self.setLayout(layout)


class MessagePage(PageBase):
    """消息主页面"""

    MAX_AUTO_SCROLL_MESSAGES = 50  # 自动滚动模式下的最大消息数
    LOAD_COUNT = 20    # 每次加载消息数
    ACCENT_COLOR = "#38A5FD"
    msg_call_signal = Signal(str, dict)

    class _StateManager:
        __slots__ = ("_page", "_lock")

        def __init__(self, page_instance: "MessagePage"):
            self._page = page_instance
            self._lock = page_instance._lock

        def __enter__(self):
            self._lock.lock()
            return self._page

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._lock.unlock()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._auto_scroll = True
        # 状态枚举: 显示中、隐藏、搜索中、加载更早消息、进入页面拉取消息
        self.state: Literal["on_show", "hidden", "searching",
                            "loading_earlier", "loading"] = "hidden"
        self._lock = QMutex()

        # 时间戳范围追踪
        self.earliest_loaded_ts = None  # 当前加载的最早时间戳
        self.earliest_loaded_id = None  # 当前加载的最早消息ID
        self.search_keywords = []       # 搜索关键词
        self.sorted_search_ids = []     # 记录搜索id顺序

        self.reached_earliest = False  # 是否已到达最早消息

        self.search_bar = None  # 搜索状态条带

        self._setup_ui()
        self._setup_context_menu()
        self._connect_signals()

        # 监听滚动事件
        self.list_widget.verticalScrollBar().valueChanged.connect(
            self._handle_scroll
        )

    def state_manager(self):
        """
        提供一个上下文管理器来安全地访问和修改页面状态。
        ``` python
        with self.state_manager() as page:
            if page.state == "on_show":
                page.state = "loading_earlier"
        ```
        """
        return MessagePage._StateManager(self)

    def _connect_signals(self):
        """连接信号"""
        self.msg_call_signal.connect(self.set_message)
        talker.subscribe("message", "call_api", signal=self.msg_call_signal)

    def _handle_scroll(self, value):
        should_load = False
        with self.state_manager() as page:
            if page.state not in ["loading_earlier", "searching"]:
                should_load = True

        if not should_load:
            return

        scrollbar = self.list_widget.verticalScrollBar()
        if scrollbar.value() <= scrollbar.maximum() * 0.1:
            self._load_earlier_messages()

    def _load_earlier_messages(self):
        with self.state_manager() as page:
            if page.state != "on_show" or page.reached_earliest or page.earliest_loaded_id is None:
                return

            page.state = "loading_earlier"

        signal = AsyncQuerySignal()
        signal.finished.connect(self._handle_earlier_messages)

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
        # 在处理UI之前，先原子性地更新状态
        with self.state_manager() as page:
            if error:
                page.state = "on_show"
                return

            if not results:
                page.reached_earliest = True
                page.state = "on_show"
                return

            page.earliest_loaded_id = results[-1][0]

        scrollbar = self.list_widget.verticalScrollBar()
        current_scroll = scrollbar.value()
        first_visible_item = self.list_widget.itemAt(0, 0)

        for _, meta, content, bot, _ in reversed(results):
            meta = orjson.loads(meta)
            item = QListWidgetItem()
            bubble = MessageBubble(meta, content,
                                   BotToolKit.color.get(bot),
                                   self.list_widget, item)
            self.list_widget.insertItem(0, item)
            self.list_widget.setItemWidget(item, bubble)

        QTimer.singleShot(100, lambda: self._adjust_scroll_position(
            current_scroll, first_visible_item, len(results)))
        with self.state_manager() as page:
            page.state = "on_show"

    def _adjust_scroll_position(self, previous_position: int, first_visible_item: QListWidgetItem, added_count: int):
        """调整滚动位置以保持视觉连续性"""
        if not first_visible_item:
            return

        total_height = 0
        for i in range(added_count):
            item = self.list_widget.item(i)
            if item:
                total_height += self.list_widget.visualItemRect(
                    item).height() + self.list_widget.spacing()

        scrollbar = self.list_widget.verticalScrollBar()
        if first_visible_item and self.list_widget.row(first_visible_item) >= 0:
            self.list_widget.scrollToItem(
                first_visible_item, QListWidget.ScrollHint.PositionAtTop)
        else:
            new_scroll_position = previous_position + total_height
            scrollbar.setValue(new_scroll_position)

    def _clear_message_list(self):
        """
        清空消息列表。
        必须手动遍历、获取控件、然后销毁。
        """
        while self.list_widget.count() > 0:
            item = self.list_widget.item(0)
            widget = self.list_widget.itemWidget(item)
            self.list_widget.takeItem(0)
            if widget:
                if isinstance(widget, MessageBubble):
                    widget.cleanup()
                widget.deleteLater()
        self.list_widget.clear()

    def search_messages(self, keywords: List[str]):
        """
        搜索消息。
        该方法首先通过 FTS 和 BM25 分数从数据库中获取一个候选消息池，
        然后在 Python 中计算每个消息的 'richness'（关键词匹配数），并进行最终排序。
        """
        if not keywords:
            return

        # 清理并验证关键词
        clean_keywords = [kw.strip() for kw in keywords if kw.strip()]
        if not clean_keywords:
            return

        with self.state_manager() as page:
            page.search_keywords = clean_keywords
            page.state = "searching"
        self._clear_message_list()
        self._add_search_bar(self.search_keywords)

        escaped_keywords = [
            '"{}"'.format(kw.replace('"', '""')) for kw in self.search_keywords]
        fts_query = ' OR '.join(escaped_keywords)

        query = f"""
            SELECT
                m.id,
                m.meta,
                m.content,
                m.bot,
                bm25(f.message_for_fts) AS score
            FROM
                message_for_fts AS f
            JOIN
                Message AS m ON f.rowid = m.id
            WHERE
                f.message_for_fts MATCH ?
            ORDER BY
                score DESC
            LIMIT 300
        """

        signal = AsyncQuerySignal()
        signal.finished.connect(self._handle_search_results)

        get_database().execute_async(
            query,
            (fts_query,),
            callback_signal=signal,
            for_write=False
        )

    def _add_search_bar(self, keywords: List[str]):
        """添加搜索状态条带"""
        if self.search_bar:
            self.main_layout.removeWidget(self.search_bar)
            self.search_bar.deleteLater()

        keywords = ["正在搜索...", "结果按照相关性排序"]    # 不再显示关键词
        self.search_bar = SearchBar(keywords, self)
        self.search_bar.exit_button.clicked.connect(self.exit_search)

        self.main_layout.insertWidget(1, self.search_bar)

    def _handle_search_results(self, results: List[Tuple], error: Exception):
        if error or not results:
            if self.search_bar:
                self.exit_search()
            return
        processed_results = []
        lower_keywords = [kw.lower() for kw in self.search_keywords]

        for row in results:
            msg_content = row[2]
            lower_content = msg_content.lower()

            richness = sum(
                1 for keyword in lower_keywords if keyword in lower_content)

            processed_results.append({
                "data": row[:-1],
                "richness": richness,
                "score": row[-1]
            })

        final_sorted_list = sorted(
            processed_results,
            key=lambda x: (x['richness'], x['score']),
            reverse=True
        )

        top_results = final_sorted_list[:50]

        self.sorted_search_ids = [res['data'][0] for res in top_results]
        final_data_tuples = [res['data'] for res in top_results]

        self._show_search_results(final_data_tuples, None)

    def _show_search_results(self, results: List[Tuple], error: Exception):
        """处理搜索结果"""
        if error:
            if self.search_bar:
                self.exit_search()
            return

        order_map = {msg_id: index for index,
                     msg_id in enumerate(self.sorted_search_ids)}
        sorted_results = sorted(
            results, key=lambda r: order_map.get(r[0], float('inf')))
        self._clear_message_list()
        for _, meta, content, bot in sorted_results:
            meta = orjson.loads(meta)
            self.add_message(meta, content, BotToolKit.color.get(bot))

    def exit_search(self):
        if self.search_bar:
            self.main_layout.removeWidget(self.search_bar)
            self.search_bar.deleteLater()
            self.search_bar = None

        with self.state_manager() as page:
            page.search_keywords = []
            page.state = "on_show"
            page.earliest_loaded_id = None
            page.reached_earliest = False

        self._clear_message_list()
        self.get_and_set_recent_msg(1, self.LOAD_COUNT)

    def _setup_ui(self) -> None:
        """初始化页面UI"""
        self.setStyleSheet("background: #FAFAFA;")
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 15, 20, 15)
        self.main_layout.setSpacing(15)

        self._add_title(self.main_layout)
        self._setup_message_list(self.main_layout)
        self._setup_control_bar(self.main_layout)

        self.setLayout(self.main_layout)

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
                margin: 8px 0 8px 15px; 
                padding: 0 50px 0 0; 
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
                color: #000000;
                font-size: 13px;
                border: 1px solid #000000;
                border-radius: 4px; 
                padding: 2px 4px;
            }
            QCheckBox::indicator { 
                width: 16px; 
                height: 16px; 
                border: 1px solid #000000;
            }
            QCheckBox::indicator:checked {
                background-color: #87CEFA;
            }
            QCheckBox:hover {
                background-color: #F0F0F0;
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
        search_action = menu.addAction("💬话题追踪")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == copy_action:
            self._copy_content(item)
        elif action == search_action:
            self._search(item)

    def _copy_content(self, item: QListWidgetItem) -> None:
        """复制消息内容"""
        if widget := self.list_widget.itemWidget(item):  # type: ignore
            widget: MessageBubble
            QApplication.clipboard().setText(widget.original_content)

    def _search(self, item: QListWidgetItem) -> None:
        if widget := self.list_widget.itemWidget(item):  # type: ignore
            widget: MessageBubble
            content = widget.content.toPlainText()

            words = tokenize(content)
            words = list(set(words))
            # 向内存占用的妥协
            """
            pos_mapping = {
                'n': 'n', 'vn': 'v', 'v': 'v', 'a': 'a', 'i': 'i', 'l': 'i',
                'j': 'ws', 'nr': 'ws', 'ns': 'ws', 'nt': 'ws', 'nz': 'ws',
            }

            important_pos = {'n': 4, 'v': 3, 'ws': 5, 'a': 2, 'i': 1, 'l': 1}
            keywords_with_weight = {}

            for word, flag in words:
                mapped_pos = pos_mapping.get(flag)
                if not mapped_pos:
                    continue
                word = word.strip()
                if not word:
                    continue

                weight = important_pos[mapped_pos] + len(word) / 10
                keywords_with_weight[word] = max(
                    keywords_with_weight.get(word, 0), weight)
            
            
            if not keywords_with_weight:
                self.search_messages([content])
                return

            sorted_keywords = sorted(
                keywords_with_weight.items(), key=lambda x: x[1], reverse=True)
            top_keywords = [kw[0] for kw in sorted_keywords[:5]]

            if not top_keywords or not all(kw.strip() for kw in top_keywords):
                return
            """
            if not words:
                return
            else:
                top_keywords = words
            self.search_messages(top_keywords)

    def add_message(self, metadata: MetadataType, content: str,
                    accent_color: Optional[str] = None) -> None:
        """添加新消息"""
        metadata = metadata.copy()
        if bot := metadata.get("bot"):
            metadata["bot"] = (bot[0], bot[1].replace(
                "{bot_color}", BotToolKit.color.get(bot[0])))

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
        """安全添加消息行，并正确处理旧消息的销毁"""

        if self._auto_scroll:

            while self.list_widget.count() >= self.MAX_AUTO_SCROLL_MESSAGES:

                item_to_remove = self.list_widget.item(0)
                widget_to_remove = self.list_widget.itemWidget(item_to_remove)

                if widget_to_remove:
                    if isinstance(widget_to_remove, MessageBubble):
                        widget_to_remove.cleanup()
                    widget_to_remove.deleteLater()

                self.list_widget.takeItem(0)

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

    def set_message(self, type_: str, data: Dict) -> None:
        """设置消息"""
        bot = data.get('bot', "")
        userid = data.get("userid") or bot
        timestamps = data["time"]
        content = ""
        plaintext = ""
        avatar = data.get("avatar")

        metadata = {
            "bot": ("{bot}", "color: {bot_color}; font-weight: bold;"),
            "time": (timestamps, "color: #757575; font-size: 12px;"),
            "session": (f"会话：{data.get('session', '')}", "color: #616161; font-style: italic;"),
            "avatar": (avatar, MessageBubble.AvatarPosition.LEFT_OUTSIDE),
            "timestamps": (timestamps, "hidden")
        }
        metadata["bot"] = (bot, metadata["bot"][1])

        if type_ == "message":
            BotToolKit.counter.add_event(bot, "receive")
            segments = data.get("content", [])
            content_parts, plaintext_parts = [], []
            for seg_type, seg_data in segments:
                if seg_type == "text":
                    content_parts.append(seg_data.replace(
                        "*", r"\*").replace("`", r"\`"))
                    plaintext_parts.append(seg_data)
                else:
                    content_parts.append(seg_data)
            content, plaintext = "".join(
                content_parts), "".join(plaintext_parts)
            if not content:
                return

        elif type_ == "call_api":
            api = data["api"]
            metadata["avatar"] = (
                avatar, MessageBubble.AvatarPosition.RIGHT_OUTSIDE)
            if api in {"send_msg", "post_c2c_messages", "post_group_messages", "send_message"}:
                BotToolKit.counter.add_event(bot, "send")
                segments = data.get("content", [])
                content_parts = [f"`calling api: {api}`\n"]
                plaintext_parts = []
                for seg_type, seg_data in segments:
                    if seg_type == "text":
                        content_parts.append(seg_data)
                        plaintext_parts.append(seg_data)
                    else:
                        content_parts.append(seg_data)
                content, plaintext = "".join(
                    content_parts), "".join(plaintext_parts)

        with self.state_manager() as page:
            if page.state == "on_show":
                self.add_message(metadata, content, BotToolKit.color.get(bot))
            elif page.state == "searching":
                if all(kw.lower() in plaintext.lower() for kw in page.search_keywords):
                    self.add_message(metadata, content,
                                     BotToolKit.color.get(bot))

        groupid = data.get("groupid") or "私聊"
        self.insert(type_, [userid, groupid, bot,
                    timestamps, content, metadata.copy(), plaintext])

    def insert(self, type_: str, params: List):
        """插入消息到数据库"""
        params[5] = orjson.dumps(params[5])
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
        if error or not results:
            return

        with self.state_manager() as page:
            ids = [r[0] for r in results]
            if ids:
                page.earliest_loaded_id = min(ids)

        for msg_id, meta, content, bot, _ in reversed(results):
            meta = orjson.loads(meta)
            self.add_message(meta, content, BotToolKit.color.get(bot))

    def on_enter(self):
        self._clear_message_list()

        with self.state_manager() as page:
            page.state = "on_show"
            page.earliest_loaded_id = None
            page.reached_earliest = False

        self.get_and_set_recent_msg(1, self.LOAD_COUNT)

    def on_leave(self):
        with self.state_manager() as page:
            page.state = "hidden"

        self._clear_message_list()
        if self.search_bar:
            self.main_layout.removeWidget(self.search_bar)
            self.search_bar.deleteLater()
            self.search_bar = None
