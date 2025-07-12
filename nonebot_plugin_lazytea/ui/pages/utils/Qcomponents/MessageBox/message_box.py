import sys
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QApplication,
    QPushButton, QTextEdit, QWidget, QSizePolicy, QStyle
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QRect,
    QSize, Property, QEvent
)
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QFont, QLinearGradient, QPaintEvent, QEnterEvent,
    QMouseEvent, QPixmap
)

from typing import List, Optional, Any, Literal, Union, TypedDict

from .model import MessageBoxConfig, ButtonConfig


class MessageBoxConfigType(TypedDict):
    title: str
    content: str
    icon_type: MessageBoxConfig.IconType
    icon_pixmap: Optional[QPixmap]
    icon_size: QSize
    buttons: List[ButtonConfig]
    animation_color: QColor
    animation_duration: Optional[int]
    click_mode: MessageBoxConfig.ButtonMode
    size: QSize
    default_button: Optional[MessageBoxConfig.ButtonType]
    use_html: bool
    button_layout: Literal['horizontal', 'vertical']
    content_margins: tuple[int, int, int, int]
    spacing: int
    background_color: str
    text_color: str
    corner_radius: int
    icon_bg_color: Optional[str]
    custom_widget: Optional[QWidget]


class AnimatedButton(QPushButton):
    """
    自定义动画按钮组件，支持多种交互模式和动画效果

    Signals:
        animationFinished: 动画完成时触发 

    Properties:
        fill_progress (int): 填充动画进度 (0-100)
    """
    animationFinished = Signal()

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        config: ButtonConfig = ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.OK,
            text="OK"
        )
    ):
        """
        初始化动画按钮

        Args:
            text (str): 按钮文本
            parent (Optional[QWidget]): 父组件
            config (ButtonConfig): 按钮配置
        """
        super().__init__(text, parent)
        self._config = config
        self._fill_progress = 0
        self._target_progress = 0
        self._animation_enabled = True
        self._animation = None
        self._apply_configuration()
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        # 设置按钮大小约束
        if config.min_width:
            self.setMinimumWidth(config.min_width)
        if config.max_width:
            self.setMaximumWidth(config.max_width)
        if config.fixed_size:
            self.setFixedSize(config.fixed_size)

    def _apply_configuration(self) -> None:
        """应用配置参数，初始化动画相关设置"""
        # 处理动画颜色和透明度
        self._fill_color = QColor(
            self._config.animation_color or QColor("#4299E1"))
        self._fill_color.setAlpha(self._config.animation_opacity)

        # 判断是否启用动画 (None或0表示禁用)
        self._animation_enabled = bool(self._config.animation_duration)
        self._animation_duration = self._config.animation_duration or 300 if self._animation_enabled else 0

        # 正确处理 click_mode 的默认值逻辑
        self._click_mode = (self._config.click_mode
                            if self._config.click_mode is not None
                            else MessageBoxConfig.ButtonMode.Always)

        if self._animation_enabled and not self._animation:
            self._setup_animation()

        self._update_availability()

    def _setup_animation(self) -> None:
        """初始化动画系统，设置动画属性和回调"""
        self._animation = QPropertyAnimation(self, b"fill_progress", self)
        self._animation.setStartValue(0)
        self._animation.setEndValue(100)
        self._animation.finished.connect(self._on_animation_finished)
        self._animation_running = False

    def enterEvent(self, event: QEnterEvent) -> None:
        """
        鼠标进入事件处理

        Args:
            event (QEnterEvent): 鼠标进入事件
        """
        if not self._animation_enabled:
            return super().enterEvent(event)

        self._target_progress = 100
        self._start_animation(forward=True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """
        鼠标离开事件处理

        Args:
            event (QEnterEvent): 鼠标离开事件
        """
        if event.type() == QEvent.Type.Leave:
            if not self._animation_enabled:
                return super().leaveEvent(event)

            self._target_progress = 0
            self._start_animation(forward=False, max_duration=500)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        鼠标点击事件处理

        Args:
            event (QMouseEvent): 鼠标点击事件
        """
        if self._click_mode == MessageBoxConfig.ButtonMode.AfterAnimation and self._fill_progress < 100:
            event.ignore()
            return
        super().mousePressEvent(event)

    def _start_animation(self, forward: bool, max_duration: int = 9999) -> None:
        """
        启动填充动画

        Args:
            forward (bool): 是否正向动画 (True表示填充，False表示清空)
            max_duration (int): 最大动画持续时间 (ms)
        """
        if not self._animation_enabled or not self._animation:
            return

        remaining_distance = abs(self._target_progress - self._fill_progress)
        distance_ratio = remaining_distance / 100.0

        if forward:
            duration = int(self._animation_duration * distance_ratio)
        else:
            duration = min(int(self._animation_duration *
                               distance_ratio), max_duration)

        if self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()

        self._animation.setDuration(duration)
        self._animation.setStartValue(self._fill_progress)
        self._animation.setEndValue(self._target_progress)

        self._animation.start()
        self._animation_running = forward

    def _on_animation_finished(self) -> None:
        """动画完成回调，处理自动点击和状态更新"""
        self.animationFinished.emit()
        self._update_availability()

        # 自动点击模式处理
        if (self._click_mode == MessageBoxConfig.ButtonMode.AutoPress and
                self._fill_progress == 100):
            self.click()

    def _update_availability(self) -> None:
        """根据点击模式更新按钮状态"""
        if self._click_mode == MessageBoxConfig.ButtonMode.AfterAnimation:
            self.setEnabled(self._fill_progress == 100)

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        自定义绘制方法，实现按钮的动画效果

        Args:
            event (QPaintEvent): 绘制事件
        """
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 绘制背景
            bg_rect = self.rect()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#EDF2F7")))
            painter.drawRoundedRect(bg_rect, 6, 6)

            # 绘制填充层 (仅在动画启用时)
            if self._animation_enabled and self._fill_progress > 0:
                fill_width = int(bg_rect.width() * self._fill_progress / 100)
                fill_rect = QRect(bg_rect.x(), bg_rect.y(),
                                  fill_width, bg_rect.height())

                # 每次绘制时使用当前配置的颜色和透明度
                current_color = QColor(self._fill_color)
                current_color.setAlpha(self._config.animation_opacity)

                gradient = QLinearGradient(0, 0, fill_width, 0)
                gradient.setColorAt(0, current_color)
                gradient.setColorAt(1, current_color.darker(120))
                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(fill_rect, 6, 6)

            # 绘制文本
            painter.setPen(QColor("#2D3748"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        finally:
            painter.end()

    @Property(int)
    def fill_progress(self) -> int:  # type: ignore
        """
        获取当前填充进度

        Returns:
            int: 当前填充进度 (0-100)
        """
        return self._fill_progress

    @fill_progress.setter
    def fill_progress(self, value: int) -> None:
        """
        设置填充进度并更新界面

        Args:
            value (int): 新的填充进度值 (0-100)
        """
        self._fill_progress = max(0, min(100, value))
        self.update()
        self._update_availability()

    def cleanup(self) -> None:
        """清理动画资源"""
        if self._animation:
            self._animation.stop()
            try:
                self._animation.finished.disconnect()
            except TypeError:
                pass
            self._animation.deleteLater()
            self._animation = None


class MessageBoxBuilder:
    """
    消息框建造者类，提供链式API配置对话框参数 

    使用方法：
    >>> dialog = (
            MessageBoxBuilder()
            .set_title("Confirmation")
            .add_button(...)
            .build()
        )
    """

    _DEFAULT_CONFIG: MessageBoxConfigType = {
        "title": "Message",
        "content": "",
        "icon_type": MessageBoxConfig.IconType.Info,
        "icon_pixmap": None,  # 自定义图标
        "icon_size": QSize(64, 64),  # 图标尺寸
        "buttons": [],
        "animation_color": QColor("#4299E1"),  # 默认动画颜色
        "animation_duration": 300,  # 默认300ms动画
        "click_mode": MessageBoxConfig.ButtonMode.Always,
        "size": QSize(400, 200),
        "default_button": None,
        "use_html": False,
        "button_layout": "horizontal",
        "content_margins": (24, 24, 24, 24),  # 内容边距
        "spacing": 16,  # 控件间距
        "background_color": "#EDF2F7",  # 背景色
        "text_color": "#2D3748",  # 文本颜色
        "corner_radius": 12,  # 圆角半径
        "icon_bg_color": None,  # 图标背景色
        "custom_widget": None,
    }

    def __init__(self):
        """初始化消息框建造者"""
        self._config = self._DEFAULT_CONFIG.copy()
        self._buttons: List[ButtonConfig] = []
        self._default_button_set = False

    def set_title(self, title: str) -> 'MessageBoxBuilder':
        """
        设置对话框标题

        Args:
            title (str): 对话框标题文本

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["title"] = title
        return self

    def set_content(self, content: str, use_html: bool = False) -> 'MessageBoxBuilder':
        """
        设置内容文本

        Args:
            content (str): 内容文本
            use_html (bool): 是否使用HTML格式

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["content"] = content
        self._config["use_html"] = use_html
        return self

    def set_icon_type(self, icon_type: MessageBoxConfig.IconType) -> 'MessageBoxBuilder':
        """
        设置消息图标类型

        Args:
            icon_type (MessageBoxConfig.IconType): 图标类型枚举值

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["icon_type"] = icon_type
        return self

    def set_icon_pixmap(self, pixmap: Union[QPixmap, str], size: Optional[QSize] = None) -> 'MessageBoxBuilder':
        """
        设置自定义图标

        Args:
            pixmap (Union[QPixmap, str]): 图标图片，可以是QPixmap或文件路径
            size (Optional[QSize]): 图标尺寸，None表示使用默认尺寸

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        if isinstance(pixmap, str):
            pixmap = QPixmap(pixmap)
        self._config["icon_type"] = MessageBoxConfig.IconType.Custom
        self._config["icon_pixmap"] = pixmap
        if size:
            self._config["icon_size"] = size
        return self

    def add_button(self, config: ButtonConfig) -> 'MessageBoxBuilder':
        """
        添加按钮配置

        Args:
            config (ButtonConfig): 按钮配置对象

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        # 合并全局配置和个体配置
        merged_config = ButtonConfig(
            btn_type=config.btn_type,
            text=config.text,
            custom_id=config.custom_id,
            role=config.role,
            animation_color=config.animation_color if config.animation_color
            else QColor(self._config["animation_color"]),
            animation_opacity=config.animation_opacity,
            animation_duration=config.animation_duration if config.animation_duration is not None
            else self._config["animation_duration"],
            click_mode=config.click_mode if config.click_mode is not None
            else self._config["click_mode"],
            fixed_size=config.fixed_size,
            min_width=config.min_width,
            max_width=config.max_width,
            closes_dialog=config.closes_dialog
        )
        self._buttons.append(merged_config)

        if not self._default_button_set:
            self._config["default_button"] = config.btn_type
            self._default_button_set = True
        return self

    def set_default_button(self, btn_type: MessageBoxConfig.ButtonType) -> 'MessageBoxBuilder':
        """
        设置默认按钮

        Args:
            btn_type (MessageBoxConfig.ButtonType): 默认按钮类型

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["default_button"] = btn_type
        self._default_button_set = True
        return self

    def hide_icon(self) -> 'MessageBoxBuilder':
        """
        启用无图标模式，隐藏图标区域

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["icon_type"] = MessageBoxConfig.IconType.NoIcon
        return self

    def set_button_layout(self, layout: Literal['horizontal', 'vertical']) -> 'MessageBoxBuilder':
        """
        设置按钮布局方向

        Args:
            layout (Literal['horizontal', 'vertical']): 布局方向

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["button_layout"] = layout
        return self

    def set_animation_color(self, color: QColor) -> 'MessageBoxBuilder':
        """
        设置默认动画颜色

        Args:
            color (QColor): 动画颜色

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["animation_color"] = color
        return self

    def set_animation_duration(self, duration: Optional[int]) -> 'MessageBoxBuilder':
        """
        设置默认动画持续时间

        Args:
            duration (Optional[int]): 动画持续时间(ms)，None或0表示禁用动画

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["animation_duration"] = duration
        if duration is None or duration == 0:
            self.set_click_mode(MessageBoxConfig.ButtonMode.Always)
        return self

    def set_click_mode(self, mode: MessageBoxConfig.ButtonMode) -> 'MessageBoxBuilder':
        """
        设置默认点击模式

        Args:
            mode (MessageBoxConfig.ButtonMode): 点击模式枚举值

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["click_mode"] = mode
        if mode != MessageBoxConfig.ButtonMode.Always and (self._config["animation_duration"] is None or self._config["animation_duration"] == 0):
            self._config["click_mode"] = MessageBoxConfig.ButtonMode.Always
        return self

    def set_size(self, width: int, height: int) -> 'MessageBoxBuilder':
        """
        设置对话框初始尺寸

        Args:
            width (int): 宽度
            height (int): 高度

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["size"] = QSize(width, height)
        return self

    def set_content_margins(self, left: int, top: int, right: int, bottom: int) -> 'MessageBoxBuilder':
        """
        设置内容边距

        Args:
            left (int): 左边距
            top (int): 上边距
            right (int): 右边距
            bottom (int): 下边距

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["content_margins"] = (left, top, right, bottom)
        return self

    def set_spacing(self, spacing: int) -> 'MessageBoxBuilder':
        """
        设置控件间距

        Args:
            spacing (int): 间距值(像素)

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["spacing"] = spacing
        return self

    def set_background_color(self, color: str) -> 'MessageBoxBuilder':
        """
        设置背景颜色

        Args:
            color (str): 颜色值(十六进制或颜色名称)

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["background_color"] = color
        return self

    def set_text_color(self, color: str) -> 'MessageBoxBuilder':
        """
        设置文本颜色

        Args:
            color (str): 颜色值(十六进制或颜色名称)

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["text_color"] = color
        return self

    def set_corner_radius(self, radius: int) -> 'MessageBoxBuilder':
        """
        设置圆角半径

        Args:
            radius (int): 圆角半径(像素)

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["corner_radius"] = radius
        return self

    def set_icon_background(self, color: str) -> 'MessageBoxBuilder':
        """
        设置图标背景颜色

        Args:
            color (str): 颜色值(十六进制或颜色名称)

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用
        """
        self._config["icon_bg_color"] = color
        return self

    def build(self) -> 'ModernMessageBox':
        """
        构建并返回配置好的消息框实例

        Returns:
            ModernMessageBox: 配置完成的消息框实例
        """
        full_config = self._config.copy()
        full_config["buttons"] = self._buttons.copy()
        instance = ModernMessageBox(full_config)
        self._config = self._DEFAULT_CONFIG.copy()
        self._buttons.clear()
        return instance

    def build_and_fetch_result(self) -> Optional[MessageBoxConfig.ButtonType | Any]:
        """
        构建消息框并返回结果

        Returns:
            Optional[MessageBoxConfig.ButtonType]: 按钮点击结果
        """
        instance = self.build()
        result = instance.new_exec_()
        return result

    def add_custom_widget(self, widget: QWidget) -> 'MessageBoxBuilder':
        """
        在消息内容和按钮之间添加一个自定义的QWidget。

        Args:
            widget (QWidget): 要添加的自定义控件。

        Returns:
            MessageBoxBuilder: 建造者实例以支持链式调用。
        """
        self._config["custom_widget"] = widget
        return self


class ModernMessageBox(QDialog):
    """
    消息对话框主类 

    Signals:
        buttonClicked(object): 当按钮点击时发射信号 
    """
    buttonClicked = Signal(object)

    def __init__(self, config: MessageBoxConfigType):
        """
        初始化消息对话框

        Args:
            config (Dict[str, Any]): 对话框配置字典
        """
        super().__init__()
        self._config = config
        self._result: Optional[MessageBoxConfig.ButtonType] = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._init_ui()
        self._setup_content()
        self._setup_icon()
        self._setup_buttons()
        self._adjust_dialog()

    def _init_ui(self) -> None:
        """初始化界面基础设置"""
        self.setWindowTitle(self._config["title"])
        self.setWindowFlags(self.windowFlags() & ~
                            Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumSize(self._config["size"])

        # 应用样式
        self.setStyleSheet(f"""    
            QDialog {{
                background-color: {self._config["background_color"]};
                color: {self._config["text_color"]};
            }}
            QTextEdit {{
                background: transparent;
                border: none;
                color: {self._config["text_color"]};
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 14px;
            }}
        """)

        main_layout = QHBoxLayout()
        margins = self._config["content_margins"]
        main_layout.setContentsMargins(*margins)
        main_layout.setSpacing(self._config["spacing"])

        # 图标区域
        if self._config["icon_type"] != MessageBoxConfig.IconType.NoIcon:
            self.icon_label = QLabel()
            self.icon_label.setFixedSize(self._config["icon_size"])
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(self.icon_label, 0,
                                  Qt.AlignmentFlag.AlignTop)
        else:
            self.icon_label = None

        # 内容区域
        content_layout = QVBoxLayout()
        content_layout.setSpacing(self._config["spacing"])

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFrameShape(QTextEdit.Shape.NoFrame)
        content_layout.addWidget(self.text_area)

        if self._config["custom_widget"]:
            content_layout.addWidget(self._config["custom_widget"])

        self.button_container = QWidget()
        content_layout.addWidget(self.button_container)

        main_layout.addLayout(content_layout, 1)
        self.setLayout(main_layout)

    def _adjust_dialog(self) -> None:
        """调整对话框最终尺寸"""
        self.adjustSize()
        self.setMinimumSize(self.size())

    def _setup_icon(self) -> None:
        """设置消息图标"""
        if self._config["icon_type"] == MessageBoxConfig.IconType.NoIcon:
            return

        elif not self.icon_label:
            raise ValueError("图标标签未初始化")

        elif self._config["icon_type"] == MessageBoxConfig.IconType.Custom:
            # 自定义图标处理
            pixmap = self._config["icon_pixmap"]
            if pixmap:
                pixmap = pixmap.scaled(
                    self._config["icon_size"],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.icon_label.setPixmap(pixmap)

            # 自定义图标背景色
            bg_color = self._config["icon_bg_color"] or "#E2E8F0"
            radius = self._config["icon_size"].width() // 2
            self.icon_label.setStyleSheet(f"""    
                QLabel {{
                    background-color: {bg_color};
                    border-radius: {radius}px;
                    padding: 8px;
                }}
            """)
        else:
            # 系统图标处理
            icon_style = {
                MessageBoxConfig.IconType.Info: ("#BEE3F8", QStyle.StandardPixmap.SP_MessageBoxInformation),
                MessageBoxConfig.IconType.Warning: ("#FEFCBF", QStyle.StandardPixmap.SP_MessageBoxWarning),
                MessageBoxConfig.IconType.Critical: ("#FED7D7", QStyle.StandardPixmap.SP_MessageBoxCritical),
                MessageBoxConfig.IconType.Question: (
                    "#E9D8FD", QStyle.StandardPixmap.SP_MessageBoxQuestion)
            }
            color, icon = icon_style.get(
                self._config["icon_type"],
                ("#EDF2F7", QStyle.StandardPixmap.SP_MessageBoxInformation)
            )
            radius = self._config["icon_size"].width() // 2
            self.icon_label.setStyleSheet(f"""    
                QLabel {{
                    background-color: {color};
                    border-radius: {radius}px;
                    padding: 12px;
                }}
            """)
            self.icon_label.setPixmap(
                self.style().standardIcon(icon).pixmap(32, 32)
            )

    def _setup_content(self) -> None:
        """设置内容文本"""
        content = self._config["content"]
        if not content:
            self.text_area.setVisible(False)
            return

        self.text_area.setVisible(True)
        if self._config["use_html"]:
            self.text_area.setHtml(content)
        else:
            self.text_area.setPlainText(content)

    def _create_button(self, config: ButtonConfig) -> AnimatedButton:
        """创建单个按钮实例"""
        button = AnimatedButton(
            text=config.text,
            parent=self,
            config=config
        )

        role_colors = {
            'primary': ("white", self._config["animation_color"]),
            'danger': ("white", QColor("#F56565")),
            'secondary': (self._config["text_color"], QColor("#CBD5E0")),
            'normal': (self._config["text_color"], QColor("#EDF2F7"))
        }
        text_color, bg_color = role_colors.get(
            config.role, (self._config["text_color"], QColor("#EDF2F7")))

        button.setStyleSheet(f"""    
            AnimatedButton {{
                color: {text_color};
                font-weight: 500;
                padding: 8px 16px;
                background: {bg_color.name()};    
                border: none;
                margin: 4px;
                border-radius: {self._config["corner_radius"]}px;
                min-width: {config.min_width or 80}px;
                max-width: {config.max_width or 200}px;
            }}
            AnimatedButton:hover {{
                background: {bg_color.darker(110).name()};    
            }}
        """)

        button.clicked.connect(
            lambda checked, btn=button: self._on_button_clicked(btn)
        )
        return button

    def _setup_buttons(self) -> None:
        """配置按钮布局"""
        if self._config["button_layout"] == "horizontal":
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            for config in self._config["buttons"]:
                btn = self._create_button(config)
                layout.addWidget(btn, stretch=1)
        else:
            layout = QVBoxLayout()
            layout.setSpacing(8)
            for config in self._config["buttons"]:
                btn = self._create_button(config)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Fixed)
                layout.addWidget(btn)

        # 设置默认焦点
        for btn in self.button_container.findChildren(AnimatedButton):
            if btn._config.btn_type == self._config["default_button"]:
                btn.setFocus()
                break

        self.button_container.setLayout(layout)

    def _on_button_clicked(self, button: AnimatedButton) -> None:
        """处理按钮点击事件"""
        config = button._config
        result = (
            config.custom_id
            if config.btn_type == MessageBoxConfig.ButtonType.Custom
            else config.btn_type
        )
        self._result = result
        self.buttonClicked.emit(result)

        if config.closes_dialog:
            for btn in self.findChildren(AnimatedButton):
                btn.cleanup()

            if self.isModal():
                self.accept()
            else:
                self.close()

    def new_exec_(self) -> Optional[MessageBoxConfig.ButtonType | Any]:
        """执行模态对话框并返回结果"""
        super().exec()
        return self._result

    def show(self) -> None:
        """显示非模态对话框"""
        super().show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        """确保在关闭时清理所有动画按钮资源"""
        for button in self.findChildren(AnimatedButton):
            button.cleanup()
        super().closeEvent(event)


# 使用示例
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # 测试1：验证不同点击模式
    dialog_test = (
        MessageBoxBuilder()
        .set_title("点击模式测试")
        .set_content("测试三种点击模式的工作情况")
        .set_icon_type(MessageBoxConfig.IconType.NoIcon)
        .set_animation_duration(1000)  # 1秒动画
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.Yes,
            text="AutoPress模式",
            role='primary',
            click_mode=MessageBoxConfig.ButtonMode.AutoPress,
            # animation_color=QColor("#38B2AC"),
            animation_opacity=50
        ))
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.No,
            text="AfterAnimation模式",
            role='danger',
            click_mode=MessageBoxConfig.ButtonMode.AfterAnimation,
            animation_opacity=255
        ))
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.Cancel,
            text="Always模式",
            click_mode=MessageBoxConfig.ButtonMode.Always
        ))
        .build()
    )
    result = dialog_test.new_exec_()
    print(f"测试结果: {result}")

    # 测试2：验证全局配置和个体配置的优先级
    result = (
        MessageBoxBuilder()
        .set_title("配置优先级测试")
        .set_content("测试全局配置和个体配置的优先级")
        .set_icon_type(MessageBoxConfig.IconType.Info)
        .set_animation_color(QColor("#48BB78"))  # 全局动画颜色
        .set_animation_duration(None)  # 全局动画时间
        .set_click_mode(MessageBoxConfig.ButtonMode.AfterAnimation)  # 全局点击模式
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.OK,
            text="全局配置按钮"  # 使用全局配置
        ))
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.Yes,
            text="个体配置按钮",
            animation_color=QColor("#F56565"),  # 覆盖全局颜色
            animation_duration=700,  # 覆盖全局时间
            click_mode=MessageBoxConfig.ButtonMode.AutoPress  # 覆盖全局模式
        ))
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.Custom,
            text="11",
            custom_id={"1": "test"}
        ))
        .build_and_fetch_result()
    )
    print(f"配置优先级测试结果: {result}")

    sys.exit(app.exec())
