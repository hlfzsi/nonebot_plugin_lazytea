import os
from pathlib import Path
from typing import ClassVar, Dict, List, Optional
from nonebot import logger
import qasync
import asyncio
import sys
import httpx

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QSizePolicy, QSpacerItem, QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtGui import (QPixmap, QColor, QIcon, QFont, QPainter,
                         QBrush, QCursor, QPainterPath, QBitmap)
from PyQt5.QtCore import (
    Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint,
    QParallelAnimationGroup, QEvent, pyqtSignal, QPointF, QRectF
)
from .pages import OverviewPage, BotInfoPage, MessagePage, SettingsPage, PageBase, PluginPage
from .pages.utils.client import talker


def create_icon_from_unicode(unicode_char: str, size: int = 24) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setFont(QFont("Segoe UI Emoji", 16))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, unicode_char)
    painter.end()
    return QIcon(pixmap)


class NavButton(QPushButton):
    _BASE_PADDING_RATIO = (0.5, 1.0)
    _ICON_SIZE_RATIO = 2.0
    _ACTIVE_ICON_MULTIPLIER = 1.25

    def __init__(self, icon: QIcon, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._base_font_size = 14
        self._base_icon_size = QSize(24, 24)
        self._active_icon_size = QSize(28, 28)
        self._original_pos = QPoint()

        self._init_ui(icon)
        self._setup_animations()

    def _init_ui(self, icon: QIcon) -> None:
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setIcon(icon)
        self.setIconSize(self._base_icon_size)
        self.update_style()

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setOffset(3, 3)
        self.shadow.setColor(QColor(100, 100, 100, 80))
        self.setGraphicsEffect(self.shadow)

    def _setup_animations(self) -> None:
        self.enter_anim = QParallelAnimationGroup(self)

        self.icon_anim = QPropertyAnimation(self, b"iconSize")
        self.icon_anim.setDuration(120)
        self.icon_anim.setEasingCurve(QEasingCurve.OutBack)

        self.shadow_anim = QPropertyAnimation(self.shadow, b"blurRadius")
        self.shadow_anim.setDuration(120)

        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(120)
        self.pos_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.enter_anim.addAnimation(self.icon_anim)
        self.enter_anim.addAnimation(self.shadow_anim)
        self.enter_anim.addAnimation(self.pos_anim)

        self.shadow_offset_anim = QPropertyAnimation(self.shadow, b"offset")
        self.shadow_offset_anim.setDuration(120)
        self.enter_anim.addAnimation(self.shadow_offset_anim)

    def enterEvent(self, event: QEvent) -> None:
        super().enterEvent(event)
        self._original_pos = self.pos()
        self.raise_()

        if self.enter_anim.state() == QPropertyAnimation.Running:
            self.enter_anim.stop()

        self.icon_anim.setStartValue(self.iconSize())
        self.icon_anim.setEndValue(self._active_icon_size)

        self.shadow_anim.setStartValue(0)
        self.shadow_anim.setEndValue(25)
        self.shadow_offset_anim.setStartValue(QPointF(3, 3))
        self.shadow_offset_anim.setEndValue(QPointF(8, 8))

        self.pos_anim.setStartValue(self._original_pos)
        self.pos_anim.setEndValue(self._original_pos + QPoint(3, -3))

        self.enter_anim.start()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        if self.enter_anim.state() == QPropertyAnimation.Running:
            self.enter_anim.stop()

        self.setIconSize(self._base_icon_size)
        self.shadow.setOffset(3, 3)
        self.shadow.setBlurRadius(0)
        self.move(self._original_pos)

    def update_style(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self.background};
                color: {self.color};
                border: 1px solid {self.border_color};
                border-radius: 15px;
                padding: 12px 20px;
                font: 500 {self._base_font_size}px 'Microsoft YaHei';
                text-align: left;
                min-height: {int(self._base_font_size * 2.618)}px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255, 255, 255, 0.35),
                    stop:1 rgba(255, 215, 225, 0.3)
                );
            }}
            QPushButton:checked {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255, 255, 255, 0.45),
                    stop:1 rgba(255, 235, 240, 0.4)
                );
                border-color: rgba(255, 255, 255, 0.6);
                color: #222222;
            }}
        """)

    @property
    def background(self) -> str:
        return "rgba(255, 255, 255, 0.15)" if not self.isChecked() else "rgba(255, 255, 255, 0.25)"

    @property
    def color(self) -> str:
        # Darker text for better contrast
        return "#222222" if self.isChecked() else "#333333"

    @property
    def border_color(self) -> str:
        return "rgba(255, 255, 255, 0.2)" if not self.isChecked() else "rgba(255, 255, 255, 0.35)"


class AnimatedStack(QStackedWidget):
    animation_finished = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.animation_duration: int = 320
        self._current_animation: Optional[QParallelAnimationGroup] = None
        self.easing_curve: QEasingCurve = QEasingCurve.OutCubic
        self.setAttribute(Qt.WA_StyledBackground)

    def slide_fade(self, new_index: int) -> None:
        if not 0 <= new_index < self.count():
            raise IndexError(f"Invalid index: {new_index}")
        if self.currentIndex() == new_index or not self.isVisible():
            return

        old_widget = self.currentWidget()
        new_widget = self.widget(new_index)

        self._setup_animation(old_widget, new_widget)
        self._current_animation.start()

    def _setup_animation(self, old: QWidget, new: QWidget) -> None:
        new.setGeometry(0, 0, self.width(), self.height())
        new.move(self.width(), 0)
        new.setWindowOpacity(0.0)
        new.show()
        new.raise_()

        self._current_animation = QParallelAnimationGroup()

        old_pos_anim = QPropertyAnimation(old, b"pos")
        old_pos_anim.setDuration(self.animation_duration)
        old_pos_anim.setStartValue(QPoint(0, 0))
        old_pos_anim.setEndValue(QPoint(-self.width()//3, 0))

        old_opacity_anim = QPropertyAnimation(old, b"windowOpacity")
        old_opacity_anim.setStartValue(1.0)
        old_opacity_anim.setEndValue(0.5)

        new_pos_anim = QPropertyAnimation(new, b"pos")
        new_pos_anim.setStartValue(QPoint(self.width(), 0))
        new_pos_anim.setEndValue(QPoint(0, 0))

        new_opacity_anim = QPropertyAnimation(new, b"windowOpacity")
        new_opacity_anim.setStartValue(0.0)
        new_opacity_anim.setEndValue(1.0)

        for anim in [old_pos_anim, old_opacity_anim, new_pos_anim, new_opacity_anim]:
            anim.setDuration(self.animation_duration)
            anim.setEasingCurve(self.easing_curve)
            self._current_animation.addAnimation(anim)

        self._current_animation.finished.connect(
            lambda: self._handle_animation_finish(old, new))

    def _handle_animation_finish(self, old: QWidget, new: QWidget) -> None:
        self.setCurrentWidget(new)
        old.hide()
        old.setWindowOpacity(1.0)
        old.move(0, 0)
        self._current_animation = None
        self.animation_finished.emit(self.indexOf(new))


class MainWindow(QWidget):
    PAGE_NAMES: ClassVar[List[str]] = ["概览", "Bot", "信息", "插件"]
    ICON_NAMES: ClassVar[List[str]] = ["📊", "🤖", "📨", "🔌"]  # "⚙️"
    DECORATION_IMAGE: ClassVar[str] = "https://t.alcy.cc/mp"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.pages: Dict[int, QWidget] = {}
        self.buttons: List[NavButton] = []
        self.current_index: int = 0
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setup_shadows()
        self.init_ui()
        self.setWindowTitle("菜鸟UI")
        self.resize_to_desktop_ratio(0.618)
        self.setup_styles()
        self.stack.setObjectName("mainStack")

        self.dragging = False
        self.drag_position = QPoint()

        self.bg_decoration = QLabel(self.sidebar)
        self.bg_decoration.setAttribute(Qt.WA_TranslucentBackground)
        self.bg_decoration.setScaledContents(True)
        self.bg_decoration.lower()

        asyncio.ensure_future(self.load_decoration_image())
        asyncio.ensure_future(talker.start())

    def resize_to_desktop_ratio(self, ratio: float = 0.618):
        desktop = QApplication.desktop()
        screen_rect = desktop.screenGeometry()
        width, height = int(screen_rect.width() *
                            ratio), int(screen_rect.height() * ratio)
        self.resize(width, height)

    async def load_decoration_image(self):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.DECORATION_IMAGE, follow_redirects=True, timeout=30)
                if response.status_code == 200:
                    image_data = response.content
                    pixmap = QPixmap()
                    pixmap.loadFromData(image_data)

                    scaled_pixmap = pixmap.scaled(
                        self.sidebar.width(),
                        self.sidebar.height(),
                        Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation
                    )

                    transparent_pixmap = QPixmap(scaled_pixmap.size())
                    transparent_pixmap.fill(Qt.transparent)
                    painter = QPainter(transparent_pixmap)
                    painter.setOpacity(0.32)
                    painter.drawPixmap(0, 0, scaled_pixmap)
                    painter.end()

                    self.bg_decoration.setPixmap(transparent_pixmap)
                    self.bg_decoration.setGeometry(0, 0,
                                                   self.sidebar.width(),
                                                   self.sidebar.height())
        except:
            raise

    def init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar, stretch=3)
        main_layout.addWidget(self.create_page_container(), stretch=7)

        self.window_shadow = QGraphicsDropShadowEffect(self)
        self.window_shadow.setBlurRadius(30)
        self.window_shadow.setXOffset(0)
        self.window_shadow.setYOffset(0)
        self.window_shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.window_shadow)

    def setup_shadows(self):
        self.sidebar_shadow = QGraphicsDropShadowEffect()
        self.sidebar_shadow.setBlurRadius(48)
        self.sidebar_shadow.setXOffset(3)
        self.sidebar_shadow.setYOffset(3)
        self.sidebar_shadow.setColor(QColor(255, 182, 193, 60))

        self.page_shadow = QGraphicsDropShadowEffect()
        self.page_shadow.setBlurRadius(64)
        self.page_shadow.setXOffset(3)
        self.page_shadow.setYOffset(3)
        self.page_shadow.setColor(QColor(12, 18, 28, 25))

    def create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WA_StyledBackground)
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(300)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)

        brand = QLabel()
        brand_pixmap = QPixmap(64, 64)
        brand_pixmap.fill(Qt.transparent)
        painter = QPainter(brand_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 64, 64)
        painter.setFont(QFont("Segoe UI Emoji", 18))
        painter.setPen(QColor(50, 50, 50))
        painter.drawText(brand_pixmap.rect(), Qt.AlignCenter, "🐦")
        painter.end()
        brand.setPixmap(brand_pixmap)
        brand.setAlignment(Qt.AlignCenter)

        title = QLabel("NOOB UI")
        title.setObjectName("title")
        title_effect = QGraphicsDropShadowEffect()
        title_effect.setBlurRadius(10)
        title_effect.setColor(QColor(255, 182, 193, 180))
        title_effect.setOffset(2, 2)
        title.setGraphicsEffect(title_effect)
        title.setAlignment(Qt.AlignCenter)

        layout.addWidget(brand)
        layout.addWidget(title)
        layout.addSpacing(10)

        line = QLabel()
        line.setFixedHeight(2)
        line.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0.5, x2:1, y2:0.5,
                stop:0 rgba(255,255,255,0), 
                stop:0.5 rgba(255,255,255,0.9),
                stop:1 rgba(255,255,255,0));
        """)
        layout.addWidget(line)
        layout.addSpacerItem(QSpacerItem(
            0, 40, QSizePolicy.Minimum, QSizePolicy.Fixed))

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(15)

        for idx, (name, icon) in enumerate(zip(self.PAGE_NAMES, self.ICON_NAMES)):
            btn = self.create_nav_button(f"{icon}   {name}", idx)
            self.buttons.append(btn)
            button_layout.addWidget(btn)

        button_layout.addStretch()
        layout.addWidget(button_container)
        version = QLabel(f"✨ Version {os.getenv('UIVERSION')}")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("""
            color: #222222;  
            font: italic 12px 'Comic Sans MS';
            background: rgba(255, 255, 255, 0.25);
            border-radius: 12px;
            padding: 6px 16px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        """)
        layout.addSpacerItem(QSpacerItem(
            0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addWidget(version)

        layout.addSpacerItem(QSpacerItem(
            0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addWidget(self.create_window_controls())

        sidebar.setGraphicsEffect(self.sidebar_shadow)
        return sidebar

    def create_window_controls(self) -> QWidget:
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)
        control_layout.addStretch()

        self.min_btn = self.create_control_button("−", "#FFB6C1")
        self.max_btn = self.create_control_button("□", "#87CEFA")
        self.close_btn = self.create_control_button("×", "#FF69B4")

        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.close)

        control_layout.addWidget(self.min_btn)
        control_layout.addWidget(self.max_btn)
        control_layout.addWidget(self.close_btn)
        return control_widget

    def create_control_button(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(32, 32)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                color: white;
                font: bold 16px 'Arial';
                border-radius: 16px;
                background: {color};
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }}
            QPushButton:hover {{
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5,
                    fx:0.5, fy:0.5,
                    stop:0 {color},
                    stop:1 rgba(255,255,255,0.4)
                );
            }}
        """)
        return btn

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
        else:
            self.showMaximized()
            self.max_btn.setText("🗖")
        self.update_mask()

    def paintEvent(self, event):
        if not self.isVisible():
            return

        painter = QPainter(self)
        if not painter.isActive():
            return

        try:
            painter.setRenderHint(QPainter.Antialiasing)
            target_rect = self.rect().adjusted(5,  5, -5, -5)

            path = QPainterPath()
            path.addRoundedRect(QRectF(target_rect),  15.0, 15.0)
            painter.fillPath(path,  QColor(255, 255, 255, 255))

            shadow_path = QPainterPath()
            shadow_rect = target_rect.adjusted(-5,  -5, 5, 5)
            shadow_path.addRoundedRect(QRectF(shadow_rect),  15.0, 15.0)
            shadow_region = shadow_path.subtracted(path)
            painter.fillPath(shadow_region,  QColor(0, 0, 0, 30))
        except:
            import traceback
            traceback.print_exc()
        finally:
            painter.end()

    def create_nav_button(self, text: str, index: int) -> NavButton:
        icon = create_icon_from_unicode(self.ICON_NAMES[index])
        btn = NavButton(icon, self.PAGE_NAMES[index])
        btn.setProperty("page_index", index)
        btn.clicked.connect(lambda: self.switch_page(index))
        return btn

    def create_page_container(self) -> AnimatedStack:
        self.stack = AnimatedStack()
        self.pages = {
            0: OverviewPage(),
            1: BotInfoPage(),
            2: MessagePage(),
            3: PluginPage(),
            # 4: SettingsPage()
        }
        for idx, page in self.pages.items():
            page.setAttribute(Qt.WA_StyledBackground)
            self.stack.addWidget(page)
        return self.stack

    @qasync.asyncSlot()
    async def switch_page(self, index: int) -> None:
        if not 0 <= index < len(self.PAGE_NAMES):
            raise IndexError(f"无效页面索引: {index}")
        if index == self.current_index:
            return

        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)

        self.stack.slide_fade(index)
        self.current_index = index

    def setup_styles(self) -> None:
        self.setStyleSheet("""
        #sidebar {
             background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 245, 245, 0.98),
            stop:1 rgba(255, 255, 255, 0.95));
            margin: 0px;
            border-top-left-radius: 15px;
            border-bottom-left-radius: 15px;
        }

        #title {
            font: bold 28px 'Comic Sans MS';
            color: #222222;  /* Darker text for better contrast */
            padding: 24px 0;
            margin: 16px 0;
            letter-spacing: 2px;
        }

        QWidget#mainStack {
            background: white;
            margin: 0px;
            border: 2px solid rgba(0, 0, 0, 0.1);
            border-top-right-radius: 15px;
            border-bottom-right-radius: 15px;
        }
       MainWindow {
            background: transparent;
            border: 1px solid rgba(127, 127, 127, 0.3);
        }
        """)

    def closeEvent(self, event) -> None:
        for page in self.pages.values():
            if isinstance(page, PageBase):
                page.on_leave()
                page.on_inactive()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        event.accept()

    def update_mask(self):
        if self.isMaximized() or self.isFullScreen():
            self.clearMask()
        else:
            bitmap = QBitmap(self.size())
            bitmap.fill(Qt.color0)

            painter = QPainter(bitmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.color1)
            painter.drawRoundedRect(self.rect().adjusted(
                1, 1, -1, -1), 15, 15)
            painter.end()
            self.setMask(bitmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg_decoration.setGeometry(0, 0,
                                       self.sidebar.width(),
                                       self.sidebar.height())
        self.update_mask()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_mask()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            self.update_mask()
        super().changeEvent(event)


def run(*args):
    def main(*args):
        app = QApplication(sys.argv)
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent
        ico_path = base_path / "resources" / "app.ico"
        if not ico_path.exists():
            logger.warning(f"图标文件不存在！{ico_path}")
        else:
            app.setWindowIcon(QIcon(str(ico_path)))
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        window = MainWindow()
        window.show()
        with loop:
            sys.exit(loop.run_forever())

    main(*args)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
