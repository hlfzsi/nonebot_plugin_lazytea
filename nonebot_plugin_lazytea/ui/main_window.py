import os
from pathlib import Path
import random
from types import ModuleType
import webbrowser
from typing import Any, ClassVar, Dict, List, Optional
import sys
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QGraphicsOpacityEffect,
    QPushButton, QLabel, QSizePolicy, QSpacerItem, QGraphicsDropShadowEffect, QApplication,
    QSystemTrayIcon, QMenu, QFrame
)
from PySide6.QtGui import (QPixmap, QColor, QIcon, QFont, QPainter,
                           QBrush, QCursor, QPainterPath, QBitmap,
                           QGuiApplication, QEnterEvent,
                           QMouseEvent, QResizeEvent
                           )
from PySide6.QtCore import (
    Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint,
    QParallelAnimationGroup, QEvent, Signal, QPointF, QRectF, QTimer
)

from .pages.background.start import PluginInit
from .pages import OverviewPage, BotInfoPage, MessagePage, PageBase, PluginPage
from .pages.background.plugin_recorder import Recorder
from .pages.background.quit import StdinListener
from .pages.utils.client import talker
from .pages.utils.tealog import logger
from .pages.utils.conn import init_db, get_database
from .pages.utils.env import IS_RUN_ALONE


def retroactive_aliasing_patch(entry_file_path: str, package_import_prefix: str):
    """
    允许直接导入LazyTea子进程使用的模块

    :param entry_file_path: 入口脚本的 __file__ 变量。
    :param package_import_prefix: 你的包被外部导入时使用的顶级前缀，
                                  例如 'nonebot_plugin_lazytea'。
    """
    logger.debug(
        f"[retroactive_aliasing_patch] 开始执行，目标包: '{package_import_prefix}'")
    try:
        entry_path = Path(entry_file_path).resolve()

        pkg_dir = entry_path
        while pkg_dir.name != package_import_prefix:
            pkg_dir = pkg_dir.parent
            if pkg_dir == pkg_dir.parent:
                raise FileNotFoundError(
                    f"无法在 '{entry_file_path}' 的父路径中找到包目录 '{package_import_prefix}'")

        if package_import_prefix not in sys.modules:
            fake_module = ModuleType(package_import_prefix)
            fake_module.__path__ = [str(pkg_dir)]
            sys.modules[package_import_prefix] = fake_module
            logger.debug(
                f"[Hyper-Precise Patch] 成功伪造父包 '{package_import_prefix}'")

    except Exception as e:
        logger.error(f"严重错误: 补丁初始化失败，无法定位包目录: {e}")
        return

    loaded_modules = list(sys.modules.values())

    for module in loaded_modules:
        if not hasattr(module, '__file__') or not module.__file__:
            continue

        try:
            module_path = Path(module.__file__).resolve()
        except (TypeError, ValueError):
            continue

        try:
            is_our_module = module_path.is_relative_to(pkg_dir)
        except AttributeError:
            is_our_module = str(module_path).startswith(
                str(pkg_dir) + os.path.sep)

        if is_our_module:
            relative_to_pkg_dir = module_path.relative_to(pkg_dir)

            module_parts = list(relative_to_pkg_dir.parts)
            if module_parts[-1].lower() == '__init__.py':
                module_parts.pop()
            else:
                module_parts[-1] = module_parts[-1][:-3]

            module_suffix = '.'.join(module_parts)

            if module_suffix:
                canonical_name = f"{package_import_prefix}.{module_suffix}"
            else:
                canonical_name = package_import_prefix

            if canonical_name not in sys.modules:
                sys.modules[canonical_name] = module
                original_name = module.__name__
                logger.debug(
                    f"[retroactive_aliasing_patch] 成功关联: '{original_name}' => '{canonical_name}'")


def create_icon_from_unicode(unicode_char: str, size: int = 24) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    font = QFont()
    font.setFamily("Segoe UI Emoji")
    font.setPointSize(16)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, unicode_char)
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
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
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
        self.icon_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        self.shadow_anim = QPropertyAnimation(self.shadow, b"blurRadius")
        self.shadow_anim.setDuration(120)

        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(120)
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.enter_anim.addAnimation(self.icon_anim)
        self.enter_anim.addAnimation(self.shadow_anim)
        self.enter_anim.addAnimation(self.pos_anim)

        self.shadow_offset_anim = QPropertyAnimation(self.shadow, b"offset")
        self.shadow_offset_anim.setDuration(120)
        self.enter_anim.addAnimation(self.shadow_offset_anim)

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._original_pos = self.pos()
        self.raise_()

        if self.enter_anim.state() == QPropertyAnimation.State.Running:
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
        if self.enter_anim.state() == QPropertyAnimation.State.Running:
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
    animation_finished = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.animation_duration: int = 320
        self._current_animation: Optional[QParallelAnimationGroup] = None
        self.easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def slide_fade(self, new_index: int) -> None:
        if not 0 <= new_index < self.count():
            raise IndexError(f"Invalid index: {new_index}")
        if self.currentIndex() == new_index or not self.isVisible():
            return

        old_widget = self.currentWidget()
        new_widget = self.widget(new_index)

        self._setup_animation(old_widget, new_widget)
        if self._current_animation:
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

    def __init__(self, icon: QIcon, app: QGuiApplication) -> None:
        super().__init__()
        self.app_icon = icon
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.pages: Dict[int, PageBase] = {}
        self.buttons: List[NavButton] = []
        self.current_index: int = 0
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setup_shadows()
        self.init_ui()
        self.setWindowTitle("TEEEA")
        self.setup_tray()
        self.resize_to_screen_ratio(0.618)
        self.setup_styles()
        self.stack.setObjectName("mainStack")

        self.dragging = False
        self.drag_position = QPoint()

        self.bg_decoration = QLabel(self.sidebar)
        self.bg_decoration.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground)
        self.bg_decoration.setScaledContents(True)
        self.bg_decoration.lower()

        self.overlay_stacks: Dict[int, List['OverlayContainer']] = {}
        self.current_overlay = None

        self.load_decoration_image()

        QTimer.singleShot(0, talker.start)
        self.plugininit = None      # Never call it
        QTimer.singleShot(0, init_db)

        def set_plugininit():
            self.plugininit = PluginInit()  # against GC

        talker.started.connect(set_plugininit)
        QTimer.singleShot(50, lambda: Recorder(parent=self))
        if not IS_RUN_ALONE:
            StdinListener.get_instance().start()
            StdinListener.get_instance().shutdown_requested.connect(app.quit)
        app.aboutToQuit.connect(self.cleanup_overlay)
        app.aboutToQuit.connect(talker.stop)

    def cleanup_overlay(self):
        for page_index in list(self.overlay_stacks.keys()):
            stack = self.overlay_stacks.pop(page_index, [])
            for overlay in stack:
                if hasattr(overlay.content_widget, 'cleanup') and callable(getattr(overlay.content_widget, 'cleanup')):
                    try:
                        overlay.content_widget.cleanup()  # type: ignore
                    except Exception as e:
                        logger.error(f"清理覆盖层内容时出错: {e}")
                overlay.deleteLater()
        self.current_overlay = None
        logger.info("成功清理覆盖层")

    def setup_tray(self) -> None:
        """设置系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)

        tray_menu = QMenu()

        show_action = tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self.show_from_tray)

        web_action = tray_menu.addAction("赏个star")
        web_action.triggered.connect(self._open_url)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _open_url(self):
        webbrowser.open(
            "https://github.com/hlfzsi/nonebot_plugin_lazytea", new=2)
        self.tray_icon.showMessage(
            "TEEEA",
            "非常感谢您的star，每一个star都是我们前进的动力",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def _on_tray_activated(self, reason):
        """处理托盘图标的点击事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        """从托盘显示窗口"""
        self.showNormal()
        self.activateWindow()

    def quit_app(self):
        """完全退出程序"""
        QApplication.quit()

    def show_subpage(self, parent_page: QWidget, widget: QWidget, title: str):
        """显示子页面覆盖层
        :param parent_page: 调用此方法的父页面
        :param widget: 要显示的内容部件
        :param title: 覆盖层标题
        """
        # 获取父页面索引
        page_index = None
        for idx, page in self.pages.items():
            if page == parent_page:
                page_index = idx
                break

        if page_index is None:
            logger.error("无法找到父页面!")
            return

        # 初始化该页面的覆盖层堆栈
        if page_index not in self.overlay_stacks:
            self.overlay_stacks[page_index] = []

        # 创建覆盖层容器
        overlay_container = OverlayContainer(widget, title, self, parent_page)

        # 如果当前已有覆盖层，先隐藏它
        if self.current_overlay:
            self.current_overlay.hide()

        # 添加到堆栈并显示
        self.overlay_stacks[page_index].append(overlay_container)
        self.current_overlay = overlay_container
        overlay_container.show()

        # 调整覆盖层大小以匹配父页面
        overlay_container.resize(parent_page.size())

    def close_overlay(self):
        """关闭当前覆盖层"""
        if not self.current_overlay:
            return

        # 找到当前覆盖层所属的页面索引
        page_index = None
        for idx, stack in self.overlay_stacks.items():
            if self.current_overlay in stack:
                page_index = idx
                break

        if page_index is None:
            return

        # 从堆栈中移除
        stack = self.overlay_stacks[page_index]
        if stack:
            stack.pop()

        # 关闭当前覆盖层
        self.current_overlay.deleteLater()
        self.current_overlay = None

        # 如果有上一级覆盖层，显示它
        if stack:
            self.current_overlay = stack[-1]
            self.current_overlay.show()

    def resize_to_screen_ratio(self, ratio: float = 0.618):
        screen = self.screen()
        if not screen:
            screen = QGuiApplication.primaryScreen()
        screen_rect = screen.geometry()

        height = int(screen_rect.height() * ratio)
        width = int(height * (16 / 9))

        if width > screen_rect.width():
            width = int(screen_rect.width() * ratio)
            height = int(width * (9 / 16))

        self.resize(width, height)

    def load_decoration_image(self) -> None:
        """加载本地背景装饰图片"""
        try:
            bg_folder = None
            import importlib.resources

            try:
                resource_ref = importlib.resources.files(__package__).joinpath( # type: ignore
                    "resources").joinpath("bg")
                with importlib.resources.as_file(resource_ref) as res_path:
                    if res_path.is_dir():
                        bg_folder = res_path
            except Exception as e:
                logger.debug(f"从 package resources 获取失败: {e}")

            if not bg_folder and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                res_path = Path(getattr(sys, '_MEIPASS', '')) / "resources" / \
                    "bg"
                if res_path.is_dir():
                    bg_folder = res_path

            if not bg_folder:
                logger.warning("未找到背景图片文件夹")
                return

            # 获取所有图片文件
            image_files = []
            if hasattr(bg_folder, 'iterdir'): # For Path objects
                for ext in ['.jpg', '.png', '.jpeg']:
                    image_files.extend(bg_folder.glob(f"*{ext}"))
                    image_files.extend(bg_folder.glob(f"*{ext.upper()}"))
            else: # For Nuitka's resource reader
                for item in bg_folder.iterdir():
                    if item.is_file() and item.name.lower().endswith(('.jpg', '.png', '.jpeg')):
                        image_files.append(item)

            if not image_files:
                logger.warning("未找到可用的背景图片")
                return

            # 随机选择一张图片
            image_path_obj = random.choice(image_files)
            
            pixmap = QPixmap()
            with importlib.resources.as_file(image_path_obj) as image_path:
                pixmap.load(str(image_path))

            if pixmap.isNull():
                logger.warning(f"无法加载图片: {image_path}")
                return

            # 缩放图片并创建半透明效果
            scaled_pixmap = pixmap.scaled(
                self.sidebar.width(),
                self.sidebar.height(),
                aspectMode=Qt.AspectRatioMode.IgnoreAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation
            )

            transparent_pixmap = QPixmap(scaled_pixmap.size())
            transparent_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(transparent_pixmap)
            painter.setOpacity(0.72)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()

            # 设置背景
            self.bg_decoration.setPixmap(transparent_pixmap)
            self.bg_decoration.setGeometry(
                0, 0,
                self.sidebar.width(),
                self.sidebar.height()
            )

        except Exception as e:
            logger.error(f"加载背景图片失败: {e}")

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
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(300)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)

        brand = QLabel()
        brand_pixmap = QPixmap(64, 64)
        brand_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(brand_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 64, 64)
        painter.setFont(QFont("Segoe UI Emoji", 18))
        painter.setPen(QColor(50, 50, 50))
        painter.drawText(brand_pixmap.rect(),
                         Qt.AlignmentFlag.AlignCenter, "🍵")
        painter.end()
        brand.setPixmap(brand_pixmap)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("TEEEA")
        title.setObjectName("title")
        title_effect = QGraphicsDropShadowEffect()
        title_effect.setBlurRadius(10)
        title_effect.setColor(QColor(255, 182, 193, 180))
        title_effect.setOffset(2, 2)
        title.setGraphicsEffect(title_effect)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
            0, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

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
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("""
            color: #222222;  
            font: italic 12px 'Comic Sans MS';
            background: rgba(255, 255, 255, 0.25);
            border-radius: 12px;
            padding: 6px 16px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        """)
        layout.addSpacerItem(QSpacerItem(
            0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addWidget(version)

        layout.addSpacerItem(QSpacerItem(
            0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
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
        self.close_btn = self.create_control_button("×", "#FF69B4")

        self.min_btn.clicked.connect(self._hide)
        self.close_btn.clicked.connect(self.quit_app)

        control_layout.addWidget(self.min_btn)
        control_layout.addWidget(self.close_btn)
        return control_widget

    def create_control_button(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(32, 32)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
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

    def paintEvent(self, event):
        if not self.isVisible():
            return

        painter = QPainter(self)
        if not painter.isActive():
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            target_rect = self.rect().adjusted(5,  5, -5, -5)

            path = QPainterPath()
            path.addRoundedRect(QRectF(target_rect),  15.0, 15.0)
            painter.fillPath(path,  QColor(255, 255, 255, 255))
        except:
            import traceback
            traceback.print_exc()
        finally:
            painter.end()

    def create_nav_button(self, text: str, index: int) -> NavButton:
        icon = create_icon_from_unicode(self.ICON_NAMES[index])
        btn = NavButton(icon, self.PAGE_NAMES[index])
        btn.setProperty("page_index", index)
        btn.clicked.connect(lambda checked, idx=index: self.switch_page(idx))
        return btn

    def create_page_container(self) -> AnimatedStack:
        self.stack = AnimatedStack(parent=self)
        self.pages = {
            0: OverviewPage(parent=self),
            1: BotInfoPage(parent=self),
            2: MessagePage(parent=self),
            3: PluginPage(parent=self),
            # 4: SettingsPage(parent=self)
        }
        for idx, page in self.pages.items():
            if not isinstance(page, PageBase):
                raise RuntimeError("主页面必须是PageBase类型")
            page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            self.stack.addWidget(page)
        return self.stack

    def switch_page(self, index: int) -> None:
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

    def _hide(self):
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "TEEEA",
                "TEEEA已最小化到系统托盘",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - \
                self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            event.accept()

    def update_mask(self):
        if self.isMaximized() or self.isFullScreen():
            self.clearMask()
        else:
            bitmap = QBitmap(self.size())
            bitmap.fill(Qt.GlobalColor.color0)

            painter = QPainter(bitmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.GlobalColor.color1)
            painter.drawRoundedRect(self.rect().adjusted(
                1, 1, -1, -1), 15, 15)
            painter.end()
            self.setMask(bitmap)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.bg_decoration.setGeometry(0, 0,
                                       self.sidebar.width(),
                                       self.sidebar.height())
        if self.current_overlay and self.current_overlay.isVisible():
            parent = self.current_overlay.parent()
            if isinstance(parent, QWidget):
                self.current_overlay.resize(parent.size())
        self.update_mask()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_mask()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.update_mask()
        super().changeEvent(event)


class OverlayContainer(QWidget):
    """覆盖层容器，包含标题栏和内容区域"""

    def __init__(self, content_widget: QWidget, title: str,
                 main_window: MainWindow, parent: QWidget):
        super().__init__(parent)
        self.main_window = main_window
        self.content_widget = content_widget
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        # 统一设置所有元素的背景色
        self.setStyleSheet("""
            OverlayContainer, 
            #titleBar, 
            #titleContainer,
            #backButton,
            QLabel {
                background-color: #ffffff;
            }
            OverlayContainer {
                border-left: 1px solid #e0e0e0;
            }
            #titleBar {
                border-bottom: 1px solid #e0e0e0;
            }
        """)

        title_bar = QWidget(self)
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(50)

        back_btn = QPushButton("← 返回", title_bar)
        back_btn.setObjectName("backButton")
        back_btn.setFixedSize(80, 32)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            #backButton {
                font-size: 13px;
                font-weight: 500;
                color: #5e5e5e;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            #backButton:hover {
                background: #f5f5f5;
                border-color: #d0d0d0;
            }
            #backButton:pressed {
                background: #ebebeb;
            }
        """)
        back_btn.clicked.connect(self.close_and_cleanup)

        title_container = QWidget(title_bar)
        title_container.setObjectName("titleContainer")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)

        title_label = QLabel(title, title_container)
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("""
            #titleLabel {
                font-size: 16px;
                font-weight: 600;
                color: #424242;
            }
        """)

        hint_label = QLabel("建议仅对您充分理解的参数进行调整", title_container)
        hint_label.setObjectName("hintLabel")
        hint_label.setStyleSheet("""
            #hintLabel {
                font-size: 13px;
                font-weight: 400;
                color: #9e9e9e;
                font-style: italic;
            }
        """)

        title_layout.addWidget(title_label)
        title_layout.addWidget(hint_label)
        title_layout.addStretch()

        separator = QFrame(title_bar)
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("border-color: #e0e0e0;")
        separator.setFixedHeight(20)

        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 20, 0)
        title_bar_layout.setSpacing(15)
        title_bar_layout.addWidget(back_btn)
        title_bar_layout.addWidget(separator)
        title_bar_layout.addWidget(title_container, 1)

        content_container = QWidget(self)
        content_container.setObjectName("contentContainer")
        content_container.setStyleSheet("""
            #contentContainer {
                background: #f8f9fa;
                border-top: 1px solid #e0e0e0;
            }
        """)

        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(0)
        content_layout.addWidget(content_widget)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(title_bar)
        main_layout.addWidget(content_container)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.start()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parent()
        if isinstance(parent, QWidget):
            self.resize(parent.size())

    def close_and_cleanup(self):
        if hasattr(self.content_widget, 'cleanup') and callable(getattr(self.content_widget, 'cleanup')):
            self.content_widget.cleanup()  # type: ignore
        self.main_window.close_overlay()


def run(*args: Any, **kwargs: Any) -> None:
    def main(*args: Any, **kwargs: Any) -> None:
        app = QApplication(sys.argv)

        from importlib.resources import files, as_file

        try:
            resource_ref = files(__package__).joinpath("resources", "app.ico") # type: ignore
            with as_file(resource_ref) as icon_file:
                _icon_path = str(icon_file) if icon_file.is_file() else ""

        except Exception:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = Path(sys._MEIPASS)  # type: ignore
                _icon_path = str(base_path / "resources" / "app.ico")
                if not Path(_icon_path).is_file():
                    _icon_path = ""
            else:
                base_path = Path(__file__).parent
                _icon_path = str(base_path / "resources" / "app.ico")
                if not Path(_icon_path).is_file():
                    _icon_path = ""

        if _icon_path:
            icon = QIcon(str(_icon_path))
            app.setWindowIcon(icon)
        else:
            logger.warning("未找到图标资源")
            icon = create_icon_from_unicode("🍵")

        try:
            window = MainWindow(icon, app)
            window.show()
        except Exception as e:
            import traceback
            logger.critical("创建主窗口失败", exc_info=True)
            traceback.print_exc()
            sys.exit(1)

        app.aboutToQuit.connect(get_database().shutdown)
        try:
            if not IS_RUN_ALONE:
                retroactive_aliasing_patch(__file__, 'nonebot_plugin_lazytea')
            app.exec()
        except KeyboardInterrupt:
            app.quit()

    try:
        main(*args, **kwargs)
    except Exception as e:
        import traceback
        logger.error("❌ 程序发生未处理异常：")
        traceback.print_exc()
        logger.critical("未处理异常", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
