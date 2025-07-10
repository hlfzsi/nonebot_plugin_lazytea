import html
import os
import re
import weakref
from typing import Optional, Dict, Tuple

from bs4 import BeautifulSoup, Tag
from PySide6.QtCore import (
    Qt,
    QSize,
    QObject,
    QUrl,
    QEvent,
    QDir,
    QFileInfo,
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QWidget,
    QFrame,
    QTextEdit,
    QSizePolicy,
    QSpacerItem,
    QDialog,
    QScrollArea,
    QGraphicsDropShadowEffect,
    QTextBrowser,
)
from PySide6.QtGui import (
    QColor,
    QTextOption,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPixmap,
    QImage,
    QBitmap,
    QRegion,
    QDesktopServices,
    QMouseEvent,
    QCloseEvent
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

import markdown2

from ..utils.tealog import logger

MetadataType = Dict[str, Tuple[str, str]]  # Dict[元数据类型, (元数据内容, 元数据样式)]
# Tuple[头像URL, 头像位置]
AvatarInfoType = Tuple[str, "MessageBubble.AvatarPosition"]


class MessageDetailDialog(QDialog):
    __slots__ = [
        'network_images', 'pending_replies', '_is_closing', '_content_loaded',
        'container', 'title_bar', 'close_button', 'content_browser', 'scroll',
        'drag_pos', 'current_html', 'image_loader'
    ]

    def __init__(self, content: str, network_images: list, base_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("消息详情")
        self.setMinimumSize(680, 500)
        self.resize(800, 600)
        self.network_images = network_images
        self.pending_replies = []
        self._is_closing = False
        self._content_loaded = False
        self.current_html = ""

        # 窗口样式设置
        self.setWindowFlags(self.windowFlags() |
                            Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        """)

        # 主容器
        self.container = QFrame(self)
        self.container.setObjectName("dialogContainer")
        self.container.setStyleSheet("""
            #dialogContainer {
                background: #FFFFFF;
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)

        # 圆角蒙版
        self.setMask(self._create_rounded_mask(12))

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        # 标题栏
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("titleBar")
        self.title_bar.setStyleSheet("""
            #titleBar {
                background: #FFFFFF;
                padding: 14px 20px;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid #F0F0F0;
            }
        """)
        self.title_bar.setFixedHeight(52)

        # 标题布局
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(0, 0, 12, 0)
        title_layout.setSpacing(12)

        self.title_label = QLabel("消息详情")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #333333;
                padding: 2px 0;
            }
        """)

        self.close_button = QLabel("×")
        self.close_button.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #999999;
                padding: 0 10px;
                qproperty-alignment: AlignCenter;
            }
            QLabel:hover {
                color: #333333;
                background: #F5F5F5;
                border-radius: 6px;
            }
        """)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.mousePressEvent = lambda e: self._safe_close()

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        # 内容浏览器
        self.content_browser = QTextBrowser()
        self.content_browser.setObjectName("messageContent")
        self.content_browser.setOpenLinks(False)
        self.content_browser.anchorClicked.connect(self._handle_link_click)
        self.content_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                padding: 20px;
            }
        """)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                background: #FFFFFF; 
                border: none; 
                border-radius: 12px;
            }
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 8px;
                border-radius: 4px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #D1D1D1;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.scroll_area)

        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.addWidget(self.container)

        # 加载内容
        self._load_content(content, base_dir)

    def resizeEvent(self, event):
        """窗口大小改变时更新圆角蒙版"""
        super().resizeEvent(event)
        self.setMask(self._create_rounded_mask(12))

    def _create_rounded_mask(self, radius):
        bitmap = QBitmap(self.size())
        bitmap.fill(Qt.GlobalColor.color0)
        painter = QPainter(bitmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.GlobalColor.color1)
        painter.drawRoundedRect(self.rect(), radius, radius)
        painter.end()
        return QRegion(bitmap)

    def _load_content(self, content: str, base_dir: str):
        """加载并预处理内容"""
        self.current_html = self._wrap_html(content)
        self.content_browser.setHtml(self.current_html)
        self.scroll_area.setWidget(self.content_browser)
        self._content_loaded = True

    def _wrap_html(self, content: str) -> str:
        """生成带样式的HTML"""
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
                }}
                pre {{
                    background: #F8F9FA;
                    padding: 16px;
                    border-radius: 6px;
                    overflow-x: auto;
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
                }}
                .base64-image-notice {{
                    display: inline-block;
                    padding: 8px 12px;
                    background: #FFF0F0;
                    border-radius: 4px;
                    margin: 8px 0;
                    color: #E74C3C;
                }}
                a {{
                    color: #4A90E2;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                blockquote {{
                    border-left: 3px solid #4A90E2;
                    padding-left: 12px;
                    margin: 16px 0;
                    color: #666666;
                    background-color: #F8F9FA;
                    padding: 12px;
                    border-radius: 0 6px 6px 0;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 16px 0;
                }}
                th, td {{
                    border: 1px solid #E0E0E0;
                    padding: 8px 12px;
                }}
                th {{
                    background-color: #F5F5F5;
                }}
                hr {{
                    border: none;
                    height: 1px;
                    background-color: #E0E0E0;
                    margin: 24px 0;
                }}
                .error-container {{
                    background: #FFF0F0;
                    padding: 16px;
                    color: #E74C3C;
                    border-radius: 8px;
                    margin: 16px 0;
                }}
            </style>
        </head>
        <body>{content}</body>
        </html>
        """

    def _safe_close(self):
        """安全关闭"""
        self._is_closing = True
        for reply in self.pending_replies:
            reply.abort()
            reply.deleteLater()
        self.pending_replies.clear()
        super().close()

    def _handle_link_click(self, url: QUrl):
        """处理链接点击"""
        if url.scheme() in ["http", "https", "file"]:
            QDesktopServices.openUrl(url)

    def closeEvent(self, event: QCloseEvent):
        """关闭事件"""
        self._safe_close()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """释放鼠标"""
        self.drag_pos = None
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        """窗口拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """窗口拖动"""
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()


class MessageBubble(QFrame):
    __slots__ = [
        'avatar_position', 'accent_color', 'list_widget', 'list_item',
        'original_content', 'metadata', 'avatar_info', 'network_manager',
        'pending_replies', 'network_images', 'base_dir', 'avatar_label',
        'decor', 'content', 'header', 'cached_image_files'
    ]

    class AvatarPosition:
        # 仅实现了左侧头像
        LEFT_OUTSIDE = 0
        RIGHT_OUTSIDE = 1
        TOP_CENTER = 2

    LINE_HEIGHT_RATIO = 1.35
    COLLAPSE_LINES = 5

    def __init__(
        self,
        metadata: MetadataType,
        content: str,
        accent_color: str,
        list_widget: QListWidget,
        list_item: QListWidgetItem,
        qnam: QNetworkAccessManager,
        avatar_position: int = AvatarPosition.LEFT_OUTSIDE,
        base_dir: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.network_manager: QNetworkAccessManager = qnam
        self._initialize_properties(
            metadata, content, accent_color, list_widget, list_item, avatar_position, base_dir)
        self._setup_ui()
        self._connect_signals()

    def _initialize_properties(
        self,
        metadata: MetadataType,
        content: str,
        accent_color: str,
        list_widget: QListWidget,
        list_item: QListWidgetItem,
        avatar_position: int,
        base_dir: Optional[str],
    ) -> None:
        self.avatar_position = avatar_position
        self.accent_color = QColor(accent_color)
        self.list_widget = list_widget
        self.list_item = list_item
        self.original_content = content
        self.metadata = metadata.copy()
        self.avatar_info: Optional[AvatarInfoType] = self.metadata.pop(
            "avatar", None)  # type: ignore
        self.pending_replies = []
        self.network_images = []
        self.base_dir = base_dir if base_dir is not None else QDir.currentPath()
        if not self.base_dir.endswith(os.sep):
            self.base_dir += os.sep

    def _setup_ui(self) -> None:
        self.setObjectName("messageBubble")
        self._setup_base_style()
        self._setup_layout()
        self._update_content_display()
        self.content.viewport().installEventFilter(self)

    def _setup_base_style(self) -> None:
        self.setContentsMargins(12, 8, 12, 8)
        self.setStyleSheet(f"""
            #messageBubble {{
                background: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E0E0E0;
            }}
            #messageBubble:hover {{
                background: #F5F5F5;
                border-color: #{self.accent_color.lighter(150).name()[1:]};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_layout(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        self._setup_avatar(main_layout)
        self._setup_decorative_bar(main_layout)
        self._setup_content_layout(main_layout)

    def _setup_avatar(self, main_layout: QHBoxLayout) -> None:
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(36, 36)
        self.avatar_label.setStyleSheet("""
            border-radius: 4px;
            border: 1px solid rgba(0, 0, 0, 0.1);
        """)
        self.avatar_label.hide()

        if self.avatar_info and self.avatar_info[0]:
            self._position_avatar(main_layout)
            self._load_avatar(self.avatar_info[0])
        else:
            pass

    def _position_avatar(self, main_layout: QHBoxLayout) -> None:
        if self.avatar_position == self.AvatarPosition.LEFT_OUTSIDE:
            main_layout.insertWidget(0, self.avatar_label)
        elif self.avatar_position == self.AvatarPosition.RIGHT_OUTSIDE:
            main_layout.addWidget(self.avatar_label)

    def _setup_decorative_bar(self, main_layout: QHBoxLayout) -> None:
        self.decor = QLabel()
        self.decor.setFixedWidth(4)
        self.decor.setStyleSheet(
            f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {self.accent_color.name()}, stop:1 {self.accent_color.lighter(150).name()});
            border-radius: 2px;
        """
        )
        main_layout.addWidget(self.decor)

    def _setup_content_layout(self, main_layout: QHBoxLayout) -> None:
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        self._setup_header(content_layout)
        self._setup_content_text(content_layout)

        main_layout.addLayout(content_layout, stretch=1)

    def _setup_header(self, content_layout: QVBoxLayout) -> None:
        self.header = QWidget()
        header_bg_color = self.accent_color.lighter(180)
        self.header.setStyleSheet(
            f"""
            background-color: {header_bg_color.name()};
            border-radius: 4px;
            padding: 4px 8px;
        """
        )
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        for key, (value, style) in self.metadata.items():
            if style != "hidden":
                label = QLabel(str(value))
                label.setStyleSheet(
                    f"""
                    {style};
                    margin: 0;
                    padding: 0;
                    background-color: transparent;
                """
                )
                header_layout.addWidget(label)

        header_layout.addItem(QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        content_layout.addWidget(self.header)

    def _setup_content_text(self, content_layout: QVBoxLayout) -> None:
        self.content = QTextEdit()
        self.content.setObjectName("messageContent")
        self.content.setReadOnly(True)
        self.content.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.content.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content.document().setBaseUrl(QUrl.fromLocalFile(self.base_dir))

        accent_color = self.accent_color.name()
        code_bg = self.accent_color.lighter(200).name()

        self.content.setStyleSheet(
            f"""
            QTextEdit {{
                color: #424242;
                font-size: 14px;
                border: none;
                background: transparent;
                padding: 0;
                line-height: {self.LINE_HEIGHT_RATIO};
            }}
            pre {{
                background-color: {code_bg};
                border: 1px solid {self.accent_color.darker(150).name()};
                color: {self.accent_color.darker().name()};
                padding: 10px;
                border-radius: 4px;
                margin: 10px 0;
                overflow-x: auto;
                white-space: pre-wrap;
            }}
            code {{
                font-family: monospace;
                background-color: {code_bg};
                color: {self.accent_color.darker(200).name()};
                padding: 2px 4px;
                border-radius: 4px;
            }}
            blockquote {{
                border-left: 3px solid {accent_color};
                padding-left: 10px;
                color: {self.accent_color.darker(150).name()};
                margin: 10px 0;
                font-style: italic;
                background-color: {self.accent_color.lighter(180).name()};
            }}
            hr {{
                height: 2px;
                background-color: {accent_color};
                border: none;
                margin: 15px 0;
            }}
        """
        )
        content_layout.addWidget(self.content)

    def _connect_signals(self) -> None:
        pass

    def _load_avatar(self, url: str) -> None:
        request = QNetworkRequest(QUrl(url))
        reply = self.network_manager.get(request)
        self.pending_replies.append(reply)
        weak_self = weakref.ref(self)

        def handle_avatar_reply():
            if not url:
                return
            self_instance = weak_self()
            if not self_instance:
                reply.deleteLater()
                return

            try:
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    data = reply.readAll().data()
                    if not data:
                        raise ValueError("空头像数据")

                    # 尝试多种解码方式
                    pixmap = QPixmap()
                    if not pixmap.loadFromData(data):
                        image = QImage()
                        if image.loadFromData(data):
                            pixmap = QPixmap.fromImage(image)
                        else:
                            raise ValueError("头像数据解码失败")

                    # 裁剪和圆角处理
                    pixmap = pixmap.scaled(
                        36, 36,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    rounded = QPixmap(36, 36)
                    rounded.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHints(QPainter.RenderHint.Antialiasing |
                                           QPainter.RenderHint.SmoothPixmapTransform)
                    path = QPainterPath()
                    path.addRoundedRect(0, 0, 36, 36, 4, 4)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.end()

                    self_instance.avatar_label.setPixmap(rounded)
                    self_instance.avatar_label.show()
                else:
                    raise ConnectionError(
                        f"网络错误[{reply.error()}]: {reply.errorString()}")
            except Exception as e:
                import traceback
                logger.error(f"头像加载失败 | URL: {url}\n{traceback.format_exc()}")
            finally:
                reply.deleteLater()
                if self_instance and reply in self_instance.pending_replies:
                    self_instance.pending_replies.remove(reply)

        reply.finished.connect(handle_avatar_reply)

    def _process_markdown(self) -> str:
        try:
            html = markdown2.markdown(
                self.original_content,
                extras=[
                    "break-on-newline",
                    "fenced-code-blocks",
                    "tables",
                    "code-friendly",
                    "strike",
                    "footnotes",
                    "cuddled-lists",
                    "task_list",
                    "highlightjs-lang",
                ],
                safe_mode="replace"
            )
            soup = BeautifulSoup(html, "html.parser")
            self._process_image_tags(soup)
            return str(soup)
        except Exception as e:
            import traceback
            logger.error(
                f"Markdown处理失败 | 内容: {self.original_content[:50]}...\n{traceback.format_exc()}")
            return f"<pre>内容渲染错误: {str(e)}</pre>"

    def _process_image_tags(self, soup: BeautifulSoup) -> None:
        """处理HTML中的所有图片标签，替换为链接或提示"""
        for img in soup.find_all("img"):
            if isinstance(img, Tag):
                src = img.get("src", "")
                if not src:
                    continue

                try:
                    if re.match(r'^(?:data:image/[a-zA-Z]+;base64,|base64://)',
                                src,  # type: ignore
                                flags=re.IGNORECASE):
                        img.replace_with(BeautifulSoup(
                            '<div class="base64-image-notice">[图片: Base64编码内容已忽略]</div>',
                            "html.parser"
                        ))
                    # 处理网络图片
                    elif not isinstance(src, str):
                        continue

                    elif src.startswith(("http://", "https://")):
                        link = soup.new_tag("a", href=src)
                        link.string = f"[图片链接: {src[:50] + ('...' if len(src) > 50 else '')}]"
                        link["class"] = "image-link"
                        img.replace_with(link)
                    # 处理本地文件
                    else:
                        if not src.startswith("file://"):
                            file_info = QFileInfo(QDir(self.base_dir), src)
                            if file_info.exists():
                                src = QUrl.fromLocalFile(
                                    file_info.absoluteFilePath()).toString()
                        link = soup.new_tag("a", href=src)
                        link.string = f"[本地图片: {os.path.basename(src)}]"
                        link["class"] = "image-link"
                        img.replace_with(link)

                except Exception as e:
                    error_html = f'''
                    <div class="image-error">
                        <p>⚠️ 图片处理失败</p>
                        <details>
                            <pre>{html.escape(str(e))}</pre>
                        </details>
                    </div>
                    '''
                    img.replace_with(BeautifulSoup(error_html, "html.parser"))

    def _update_content_display(self) -> None:
        try:
            html = self._process_markdown()
            self.content.setHtml(html)
            self._update_content_height()
            self._update_item_height()
        except Exception as e:
            logger.error(f"内容显示更新失败: {str(e)}")

    def _update_content_height(self) -> None:
        try:
            doc = self.content.document()
            doc.setTextWidth(self.content.width() - 2)
            line_height = self._calculate_line_height()
            max_height = line_height * self.COLLAPSE_LINES
            doc_height = doc.size().height()

            if doc_height > max_height:
                self.content.setFixedHeight(int(max_height))
            else:
                self.content.setFixedHeight(int(doc_height))
        except Exception as e:
            logger.error(f"更新内容高度失败: {str(e)}")

    def _calculate_line_height(self) -> int:
        fm = QFontMetrics(self.content.font())
        return int(fm.lineSpacing() * self.LINE_HEIGHT_RATIO)

    def _update_item_height(self) -> None:
        try:
            margins = self.contentsMargins()
            header_height = self.header.sizeHint().height()
            content_height = self.content.height()
            total_height = header_height + content_height + margins.top() + margins.bottom()
            self.list_item.setSizeHint(QSize(0, total_height + 8))
        except Exception as e:
            logger.error(f"Update item height error: {str(e)}")

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.content.viewport() and event.type() == QEvent.Type.MouseButtonDblClick:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                self._show_detail_dialog()
            return True
        return super().eventFilter(obj, event)

    def _show_detail_dialog(self):
        try:
            html = self._process_markdown()
            dialog = MessageDetailDialog(
                html,
                [], 
                self.base_dir,
                self
            )
            dialog.exec_()
        except Exception as e:
            logger.error(f"打开详情窗口失败: {str(e)}")

    def cleanup(self) -> None:
        try:
            self.network_images.clear()
            for reply in self.pending_replies:
                try:
                    if reply.isRunning():
                        reply.abort()
                    reply.deleteLater()
                except Exception as e:
                    logger.error(f"Error aborting reply: {e}")
            self.pending_replies.clear()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

    def deleteLater(self):
        self.cleanup()
        super().deleteLater()
