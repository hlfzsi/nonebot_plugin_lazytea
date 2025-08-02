import threading
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QListWidget, QListWidgetItem
import sys
import html
import os
import re
import time
import weakref
from typing import Callable, Optional, Dict, Tuple, List

from bs4 import BeautifulSoup, Tag
from PySide6.QtCore import (
    Qt,
    QObject,
    QUrl,
    QEvent,
    QDir,
    QFileInfo,
    QPoint,
    QTimer,
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QWidget,
    QFrame,
    QSizePolicy,
    QDialog,
    QScrollArea,
    QGraphicsDropShadowEffect,
    QTextBrowser,
    QScrollBar
)
from PySide6.QtGui import (
    QColor,
    QTextOption,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPixmap,
    QDesktopServices,
    QMouseEvent,
    QCloseEvent,
    QResizeEvent,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

import markdown2

from ..utils.tealog import logger
from ..utils.Qcomponents.nonwheel import NonScrollingTextBrowser


MetadataType = Dict[str, Tuple[str, str]]  # 格式: Dict[元数据类型, (元数据内容, 元数据样式)]
AvatarInfoType = Tuple[str, int]  # 格式: Tuple[头像URL, 头像位置]


class AvatarCache:
    """
    头像缓存管理器
    - 引用计数：用于管理内存，当没有气泡使用某个头像时，立即释放。
    - 时间过期：用于确保头像数据的新鲜度。
    - 请求锁：防止对同一URL的并发网络请求。
    """
    _instance = None
    CACHE_EXPIRATION_SECONDS = 20 * 60  # 缓存过期时间: 20分钟
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super(AvatarCache, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_cache'):
            return

        self._cache: Dict[str, Tuple[QPixmap, float, int]] = {}
        self._qnam: Optional[QNetworkAccessManager] = None
        self._pending_requests: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    @property
    def qnam(self) -> QNetworkAccessManager:
        if self._qnam is None:
            self._qnam = QNetworkAccessManager()
        return self._qnam

    def get(self, url: str) -> Optional[QPixmap]:
        """
        从缓存中获取头像。如果头像存在且未过期，则返回它。
        """
        with self._lock:
            if url in self._cache:
                pixmap, timestamp, ref_count = self._cache[url]
                if (time.time() - timestamp) < self.CACHE_EXPIRATION_SECONDS:
                    return pixmap
                else:
                    logger.debug(f"头像缓存已过期，从缓存中移除 {url}")
                    del self._cache[url]
        return None

    def put(self, url: str, pixmap: QPixmap):
        """
        将新下载的头像存入或更新到缓存。
        """
        with self._lock:
            if url in self._cache:
                _, _, old_ref_count = self._cache[url]
                self._cache[url] = (pixmap, time.time(), old_ref_count)
            else:
                self._cache[url] = (pixmap, time.time(), 0)

    def increment_ref(self, url: str):
        """
        增加一个头像的引用计数。
        """
        with self._lock:
            if url in self._cache:
                pixmap, timestamp, ref_count = self._cache[url]
                self._cache[url] = (pixmap, timestamp, ref_count + 1)
            else:
                logger.warning(f"尝试增加一个不在缓存中的头像的引用 | URL: {url}")

    def decrement_ref(self, url: str):
        """
        减少一个头像的引用计数。如果引用计数降为0，则从缓存中删除。
        """
        with self._lock:
            if url in self._cache:
                pixmap, timestamp, ref_count = self._cache[url]
                new_count = ref_count - 1
                if new_count <= 0:
                    del self._cache[url]
                    logger.debug(f"头像引用计数为0，已从缓存移除 | URL: {url}")
                else:
                    self._cache[url] = (pixmap, timestamp, new_count)

    def request_avatar(self, url: str, callback: Callable):
        """
        请求一个头像。此方法处理缓存、锁定和网络获取。
        :param url: 头像的URL
        :param callback: 一个函数，当获取到QPixmap时被调用，如 callback(pixmap: QPixmap)
        """
        cached_pixmap = self.get(url)
        if cached_pixmap:
            callback(cached_pixmap)
            return

        with self._lock:
            if url in self._pending_requests:
                self._pending_requests[url].append(callback)
                logger.debug(f"命中正在进行的下载，加入等待列表 | URL: {url}")
                return

            logger.debug(f"缓存未命中，发起新网络请求 | URL: {url}")
            self._pending_requests[url] = [callback]

        request = QNetworkRequest(QUrl(url))
        reply = self.qnam.get(request)

        reply.finished.connect(lambda: self._on_fetch_finished(reply, url))

    def _on_fetch_finished(self, reply: QNetworkReply, url: str):
        """
        处理已完成的网络下载。
        """
        try:
            with self._lock:
                subscribers = self._pending_requests.pop(url, [])

            if not subscribers:
                return

            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll().data()
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    pixmap = pixmap.scaled(
                        36, 36, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    rounded = QPixmap(36, 36)
                    rounded.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    path = QPainterPath()
                    path.addRoundedRect(0, 0, 36, 36, 4, 4)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.end()

                    self.put(url, rounded)

                    for callback in subscribers:
                        callback(rounded)
                else:
                    raise ValueError("无法从接收到的数据加载头像图片")
            else:
                raise ConnectionError(f"网络错误: {reply.errorString()}")
        except Exception as e:
            logger.error(f"加载头像失败 | URL: {url}\n{e}")
        finally:
            reply.deleteLater()


class MessageDetailDialog(QDialog):
    """
    消息详情对话框，用于完整显示被折叠的消息内容。
    """

    def __init__(self, content_html: str, base_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("消息详情")
        self.setMinimumSize(680, 500)
        self.resize(800, 600)

        self._is_closing = False
        self.drag_pos: Optional[QPoint] = None
        self.current_html = content_html

        self.setWindowFlags(self.windowFlags() |
                            Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(
            "font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;")

        self.container = QFrame(self)
        self.container.setObjectName("dialogContainer")
        self.container.setStyleSheet("""
            #dialogContainer {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        self.title_bar = self._create_title_bar()

        self.content_browser = QTextBrowser()
        self.content_browser.setObjectName("messageContent")
        self.content_browser.setOpenLinks(False)
        self.content_browser.anchorClicked.connect(self._handle_link_click)
        self.content_browser.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                padding: 20px;
                background-color: transparent;
            }
        """)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.content_browser)
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                background: transparent; 
                border: none; 
            }
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #D1D1D1;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)
        container_layout.addWidget(self.title_bar)
        container_layout.addWidget(self.scroll_area)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.addWidget(self.container)

        self._load_content(content_html, base_dir)

    def _create_title_bar(self) -> QWidget:
        """创建自定义标题栏"""
        title_bar = QWidget(self.container)
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("""
            #titleBar {
                background-color: #FDFDFD;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid #F0F0F0;
            }
        """)

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 0, 12, 0)
        title_layout.setSpacing(12)

        title_label = QLabel("消息详情")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #333333;
            }
        """)

        close_button = QLabel("×")
        close_button.setFixedSize(28, 28)
        close_button.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #999999;
                qproperty-alignment: AlignCenter;
            }
            QLabel:hover {
                color: #333333;
                background-color: #F5F5F5;
                border-radius: 6px;
            }
        """)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.mousePressEvent = lambda e: self.accept()

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_button)
        return title_bar

    def _load_content(self, content_html: str, base_dir: str):
        """加载并预处理HTML内容"""
        full_html = self._wrap_html(content_html)
        self.content_browser.setHtml(full_html)
        self.content_browser.document().setBaseUrl(QUrl.fromLocalFile(base_dir))

    def _wrap_html(self, content: str) -> str:
        """为内容包裹HTML模板和通用样式，确保显示效果一致"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    color: #333333;
                    margin: 0;
                    padding: 0;
                    word-wrap: break-word;
                }}
                pre {{
                    background: #F8F9FA;
                    padding: 16px;
                    border-radius: 6px;
                    border: 1px solid #EAECEE;
                    overflow-x: auto;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
                code {{
                    background: #F3F3F3;
                    padding: 2px 4px;
                    border-radius: 4px;
                    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
                }}
                .image-link {{
                    display: inline-block;
                    padding: 8px 12px;
                    background: #F0F0F0;
                    border-radius: 4px;
                    margin: 8px 0;
                    color: #4A90E2;
                    border: 1px solid #E0E0E0;
                }}
                .base64-image-notice {{
                    display: inline-block;
                    padding: 8px 12px;
                    background: #FFF0F0;
                    border-radius: 4px;
                    margin: 8px 0;
                    color: #E74C3C;
                    border: 1px solid #FADBD8;
                }}
                a {{ color: #4A90E2; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                blockquote {{
                    border-left: 3px solid #4A90E2;
                    padding: 12px;
                    margin: 16px 0;
                    color: #666666;
                    background-color: #F8F9FA;
                    border-radius: 0 6px 6px 0;
                }}
                table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
                th, td {{ border: 1px solid #E0E0E0; padding: 8px 12px; }}
                th {{ background-color: #F5F5F5; }}
                hr {{ border: none; height: 1px; background-color: #E0E0E0; margin: 24px 0; }}
            </style>
        </head>
        <body>{content}</body>
        </html>
        """

    def _handle_link_click(self, url: QUrl):
        """处理链接点击，使用系统默认程序打开外部链接"""
        if url.scheme() in ["http", "https", "file"]:
            QDesktopServices.openUrl(url)

    def closeEvent(self, event: QCloseEvent):
        """关闭事件，确保安全地终止所有操作"""
        self._is_closing = True
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标按下事件，实现窗口拖动"""
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.underMouse():
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理鼠标移动事件，实现窗口拖动"""
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """处理鼠标释放事件，结束窗口拖动"""
        self.drag_pos = None
        event.accept()


class MessageBubble(QFrame):
    """
    一个可自定义的消息气泡控件，支持Markdown、头像、元数据等。
    经过重构，将头像移出气泡，使布局更清晰、灵活。
    """
    avatar_cache = AvatarCache()

    # 定义头像的位置
    class AvatarPosition:
        LEFT_OUTSIDE = 0   # 头像在气泡外部左侧
        RIGHT_OUTSIDE = 1  # 头像在气泡外部右侧
        TOP_CENTER = 2     # 头像在气泡上部居中

    COLLAPSE_LINES = 5     # 内容超过此行数时折叠
    VERTICAL_PADDING = 5   # 内容区域的垂直内边距

    def __init__(
        self,
        metadata: MetadataType,
        content: str,
        accent_color: str,
        list_widget: QListWidget,
        list_item: QListWidgetItem,
        base_dir: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._is_closing = False
        self._is_layout_connected = False
        self._updating_height = False

        self._initialize_properties(
            metadata, content, accent_color, list_widget, list_item, base_dir)

        self._setup_ui()

        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)  # 50毫秒延迟防抖
        self._update_timer.timeout.connect(self._update_heights)

    def _initialize_properties(
        self, metadata: MetadataType, content: str, accent_color: str,
        list_widget: QListWidget, list_item: QListWidgetItem, base_dir: Optional[str]
    ) -> None:
        """初始化所有实例属性"""
        avatar_raw = metadata.get("avatar")
        self.avatar_info: Optional[AvatarInfoType] = None
        if avatar_raw:
            try:
                self.avatar_info = (avatar_raw[0], int(avatar_raw[1]))
                self.avatar_position = self.avatar_info[1]
            except Exception as e:
                logger.warning(f"头像元数据格式错误: {avatar_raw} | {e}")
                self.avatar_position = self.AvatarPosition.LEFT_OUTSIDE
        else:
            self.avatar_position = self.AvatarPosition.LEFT_OUTSIDE
        self.accent_color = QColor(accent_color)
        self.list_widget = weakref.ref(list_widget)
        self.list_item = weakref.ref(list_item)
        self.original_content = content

        self.metadata = metadata.copy()
        if "avatar" in self.metadata:
            del self.metadata["avatar"]

        self.base_dir = base_dir if base_dir is not None else QDir.currentPath()
        if not self.base_dir.endswith(os.sep):
            self.base_dir += os.sep

    def _setup_ui(self) -> None:
        """构建UI界面"""
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)

        self.avatar_label = self._create_avatar_label()
        self.bubble_container = self._create_bubble_container()
        self.decor = self._create_decorative_bar()
        (self.header, self.content) = self._create_content_area(
            self.bubble_container)

        self._setup_layout()

        self._update_content_display()
        if self.avatar_info and self.avatar_info[0]:
            self._load_avatar(self.avatar_info[0])

        self.content.viewport().installEventFilter(self)

    def resizeEvent(self, event: QResizeEvent):
        """
        当控件大小改变时触发，这是实现响应式布局的关键。
        通过定时器延迟执行，避免在拖动窗口时频繁更新。
        """
        super().resizeEvent(event)
        self._update_timer.start()

    def _create_avatar_label(self) -> QLabel:
        """创建头像标签"""
        label = QLabel()
        label.setFixedSize(36, 36)
        label.setStyleSheet(
            "border-radius: 4px; background-color: #E0E0E0;")
        label.hide()
        return label

    def _create_bubble_container(self) -> QFrame:
        """创建气泡的主体框架"""
        container = QFrame(self)
        container.setObjectName("bubbleContainer")
        container.setStyleSheet(f"""
            #bubbleContainer {{
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E0E0E0;
            }}
            #bubbleContainer:hover {{
                border-color: {self.accent_color.name()};
            }}
        """)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        return container

    def _create_decorative_bar(self) -> QLabel:
        """创建颜色装饰条"""
        decor = QLabel()
        return decor

    def _setup_layout(self) -> None:
        """根据头像位置设置主布局"""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        content_layout.addWidget(self.header)
        content_layout.addWidget(self.content)

        if self.avatar_position == self.AvatarPosition.TOP_CENTER:
            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(8)
            main_layout.setContentsMargins(0, 0, 0, 0)
            avatar_container = QWidget()
            avatar_layout = QHBoxLayout(avatar_container)
            avatar_layout.setContentsMargins(0, 0, 0, 0)
            avatar_layout.addStretch()
            avatar_layout.addWidget(self.avatar_label)
            avatar_layout.addStretch()
            main_layout.addWidget(avatar_container)
            main_layout.addWidget(self.bubble_container)
            bubble_layout = QVBoxLayout(self.bubble_container)
            self.decor.setFixedHeight(4)
            self.decor.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.accent_color.name()}, stop:1 {self.accent_color.lighter(130).name()});
                border-top-left-radius: 2px; border-top-right-radius: 2px;
            """)
            bubble_layout.addWidget(self.decor)
            bubble_layout.addWidget(content_widget)

        else:  # 统一处理 LEFT_OUTSIDE 和 RIGHT_OUTSIDE
            main_layout = QHBoxLayout(self)
            main_layout.setSpacing(12)
            main_layout.setContentsMargins(0, 0, 0, 0)

            bubble_layout = QHBoxLayout(self.bubble_container)
            bubble_layout.setSpacing(8)

            self.decor.setFixedWidth(4)
            self.decor.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.accent_color.name()}, stop:1 {self.accent_color.lighter(130).name()});
                border-radius: 2px;
            """)

            if self.avatar_position == self.AvatarPosition.LEFT_OUTSIDE:
                # 左侧头像布局
                main_layout.addWidget(self.avatar_label)
                main_layout.addWidget(self.bubble_container, 1)
                main_layout.addStretch(0)
                bubble_layout.addWidget(self.decor)
                bubble_layout.addWidget(content_widget, 1)

            else:  # RIGHT_OUTSIDE
                main_layout.addStretch(0)
                main_layout.addWidget(self.bubble_container, 1)
                main_layout.addWidget(self.avatar_label)

                bubble_layout.addWidget(content_widget, 1)
                bubble_layout.addWidget(self.decor)

        bubble_layout.setContentsMargins(8, 8, 8, 8)

    def _create_content_area(self, parent) -> Tuple[QWidget, QTextBrowser]:
        """创建元数据头部和内容文本区域"""
        header = QWidget(parent)
        header_bg_color = self.accent_color.lighter(185)  # 使用主题色的淡色作为背景
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {header_bg_color.name()};
                border-radius: 4px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(10)

        for key, (value, style) in self.metadata.items():
            if style != "hidden":
                label = QLabel(str(value))
                label.setStyleSheet(
                    f"{style}; background-color: transparent; border: none;")
                header_layout.addWidget(label)
        header_layout.addStretch()

        if header_layout.count() <= 1:
            header.hide()

        content = NonScrollingTextBrowser(parent)
        content.setObjectName("messageContent")
        content.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        content.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        content.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
        content.document().setBaseUrl(QUrl.fromLocalFile(self.base_dir))

        accent_color_str = self.accent_color.name()
        code_bg = self.accent_color.lighter(190).name()

        content.setStyleSheet(f"""
            QTextEdit {{
                color: #424242;
                font-size: 14px;
                border: none;
                background: transparent;
                padding: 0;
            }}
            pre {{
                background-color: {code_bg};
                border: 1px solid {self.accent_color.darker(110).name()};
                padding: 10px;
                border-radius: 4px;
                margin: 8px 0;
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
            code {{
                font-family: monospace;
                background-color: {code_bg};
                padding: 2px 4px;
                border-radius: 4px;
            }}
            blockquote {{
                border-left: 3px solid {accent_color_str};
                padding-left: 10px;
                margin: 8px 0;
                background-color: {self.accent_color.lighter(195).name()};
            }}
            hr {{
                height: 1px;
                background-color: {self.accent_color.lighter(150).name()};
                border: none;
                margin: 10px 0;
            }}
        """)
        return header, content

    def _set_avatar_pixmap(self, pixmap: QPixmap):
        """工具函数：将给定的pixmap设置到头像标签上并显示"""
        self.avatar_label.setPixmap(pixmap)
        self.avatar_label.show()
        self._update_item_height()

    def _load_avatar(self, url: str) -> None:
        """
        通过AvatarCache请求头像，AvatarCache内部处理缓存和并发。
        """
        weak_self = weakref.ref(self)

        def on_avatar_loaded(pixmap: QPixmap):
            """当头像成功获取后的回调函数"""
            self_instance = weak_self()
            if self_instance and not self_instance._is_closing:
                self_instance.avatar_cache.increment_ref(url)
                self_instance._set_avatar_pixmap(pixmap)

        self.avatar_cache.request_avatar(url, on_avatar_loaded)

    def _process_markdown(self) -> str:
        """将Markdown原文转换为带样式的HTML"""
        try:
            html_content = markdown2.markdown(
                self.original_content,
                extras=[
                    "break-on-newline", "fenced-code-blocks", "tables",
                    "strike", "task_list", "highlightjs-lang",
                ],
                safe_mode="replace"
            )

            soup = BeautifulSoup(html_content, "html.parser")
            self._process_image_tags(soup)
            return str(soup)
        except Exception as e:
            logger.error(f"Markdown处理失败: {e}")
            return f"<pre>内容渲染错误: {html.escape(str(e))}</pre>"

    def _process_image_tags(self, soup: BeautifulSoup) -> None:
        """处理HTML中的图片标签，替换为链接或提示，避免在气泡中直接加载大图"""
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue
            src_attr = img.get("src")
            if not isinstance(src_attr, str) or not src_attr:
                continue
            src = src_attr

            try:
                # 忽略Base64编码的图片，防止内容过大
                if re.match(r'^(data:image|base64://)', src, re.IGNORECASE):
                    img.replace_with(BeautifulSoup(
                        '<div class="base64-image-notice">[图片: Base64内容已忽略]</div>', "html.parser"
                    ))
                # 将网络图片替换为可点击的链接
                elif src.startswith(("http://", "https://")):
                    link = soup.new_tag("a", href=src)
                    link.string = f"[网络图片: {src[:50]}{'...' if len(src) > 50 else ''}]"
                    link["class"] = "image-link"
                    img.replace_with(link)
                # 将本地图片替换为可点击的链接
                else:
                    file_path = src
                    if not src.startswith("file://"):
                        file_info = QFileInfo(QDir(self.base_dir), src)
                        if file_info.exists():
                            file_path = QUrl.fromLocalFile(
                                file_info.absoluteFilePath()).toString()
                    link = soup.new_tag("a", href=file_path)
                    link.string = f"[本地图片: {os.path.basename(src)}]"
                    link["class"] = "image-link"
                    img.replace_with(link)
            except Exception as e:
                img.replace_with(BeautifulSoup(
                    f"<p>图片处理失败: {html.escape(str(e))}</p>", "html.parser"))

    def _update_content_display(self) -> None:
        """更新内容显示，并触发高度调整"""
        html_content = self._process_markdown()
        self.content.setHtml(html_content)

        if not self._is_layout_connected:
            doc_layout = self.content.document().documentLayout()
            if doc_layout:
                doc_layout.documentSizeChanged.connect(self._update_heights)
                self._is_layout_connected = True  #
            else:
                logger.warning("QTextDocumentLayout 在连接时不可用。")

        self._update_heights()

    def _update_heights(self):
        """更新内容高度和列表项高度"""
        if self._updating_height:
            return

        self._updating_height = True
        try:
            self._update_content_height()
            self._update_item_height()
        finally:
            self._updating_height = False

    def _update_content_height(self) -> None:
        """根据内容计算并设置QTextEdit的高度，实现折叠效果"""
        doc = self.content.document()
        doc.setTextWidth(self.content.viewport().width())

        fm = QFontMetrics(self.content.font())
        line_height = fm.lineSpacing()
        max_height = line_height * self.COLLAPSE_LINES
        doc_height = doc.size().height()

        new_height = min(doc_height, max_height)

        if abs(self.content.height() - new_height) > 1:
            self.content.setFixedHeight(
                int(new_height) + self.VERTICAL_PADDING)

    def _update_item_height(self) -> None:
        """更新其所在的QListWidgetItem的尺寸"""
        item = self.list_item()
        list_widget = self.list_widget()
        if item and list_widget:
            QTimer.singleShot(0, lambda: item.setSizeHint(self.sizeHint()))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """事件过滤器，用于捕获双击事件以显示详情。"""
        if obj is self.content.viewport() and event.type() == QEvent.Type.MouseButtonDblClick:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                self._show_detail_dialog()
                return True
        return super().eventFilter(obj, event)

    def _show_detail_dialog(self):
        """显示消息详情对话框"""
        try:
            html_content = self._process_markdown()
            dialog = MessageDetailDialog(html_content, self.base_dir, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"打开详情窗口失败: {e}")

    def cleanup(self) -> None:
        """清理资源，在控件被删除前调用"""
        if self._is_closing:
            return
        self._is_closing = True
        self._update_timer.stop()
        if self.avatar_info and self.avatar_info[0]:
            self.avatar_cache.decrement_ref(self.avatar_info[0])

    def deleteLater(self):
        """重写deleteLater，确保在删除前调用cleanup"""
        self.cleanup()
        super().deleteLater()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = QWidget()

    layout = QVBoxLayout()
    layout.setContentsMargins(20, 15, 20, 15)
    layout.setSpacing(15)
    list_widget = QListWidget()
    list_widget.setSpacing(8)
    list_widget.setStyleSheet("""
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

    list_widget.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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

    # 示例元数据
    metadata_left = {
        "avatar": ("https://bpic.588ku.com/element_origin_min_pic/23/07/11/d32dabe266d10da8b21bd640a2e9b611.jpg!r650", MessageBubble.AvatarPosition.LEFT_OUTSIDE),
        "username": ("左侧用户", "color: #1976D2; font-weight: bold;"),
    }
    metadata_right = {
        "avatar": ("https://bpic.588ku.com/element_origin_min_pic/23/07/11/d32dabe266d10da8b21bd640a2e9b611.jpg!r650", MessageBubble.AvatarPosition.RIGHT_OUTSIDE),
        "username": ("右侧用户", "color: #388E3C; font-weight: bold;"),
    }
    metadata_top = {
        "avatar": ("https://bpic.588ku.com/element_origin_min_pic/23/07/11/d32dabe266d10da8b21bd640a2e9b611.jpg!r650", MessageBubble.AvatarPosition.TOP_CENTER),
        "username": ("顶部用户", "color: #F57C00; font-weight: bold;"),
    }

    content = "这是一个**Markdown**消息示例。\n- 支持多行\n- 支持图片\n- 支持代码块\n"
    accent_color = "#4A90E2"

    # 左侧头像
    item_left = QListWidgetItem(list_widget)
    bubble_left = MessageBubble(metadata_left, content,
                                accent_color, list_widget, item_left)
    list_widget.setItemWidget(item_left, bubble_left)

    # 右侧头像
    item_right = QListWidgetItem(list_widget)
    bubble_right = MessageBubble(
        metadata_right, content, accent_color, list_widget, item_right)
    list_widget.setItemWidget(item_right, bubble_right)

    # 顶部居中头像
    list_widget.setVerticalScrollBar(ModernScrollBar())
    item_top = QListWidgetItem(list_widget)
    bubble_top = MessageBubble(metadata_top, content,
                               accent_color, list_widget, item_top)
    list_widget.setItemWidget(item_top, bubble_top)
    list_widget.setMinimumSize(600, 600)
    layout.addWidget(list_widget)
    widget.setLayout(layout)
    widget.show()
    sys.exit(app.exec())
