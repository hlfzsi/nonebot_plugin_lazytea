from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QLineEdit,
                               QComboBox, QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox)
from PySide6.QtGui import QLinearGradient, QPalette, QColor,QBrush
from PySide6.QtWidgets import QGraphicsDropShadowEffect


class StyleManager:
    """统一管理所有控件的样式"""

    @staticmethod
    @staticmethod
    def apply_base_style(widget: QWidget) -> None:
        """应用基础渐变背景"""
        # 创建一个线性渐变
        gradient = QLinearGradient(0, 0, widget.width(), widget.height())
        gradient.setColorAt(0, QColor(255, 182, 193))  # 粉色
        gradient.setColorAt(0.5, QColor(173, 216, 230))  # 淡蓝色
        gradient.setColorAt(1, QColor(240, 248, 255))  # 更淡的蓝色

        brush = QBrush(gradient)

        palette = widget.palette()
        palette.setBrush(QPalette.ColorRole.Window, brush)

        widget.setAutoFillBackground(True) 
        widget.setPalette(palette)

    @staticmethod
    def apply_style(widget: QWidget) -> None:
        """应用控件特定样式"""
        if isinstance(widget, QLabel):
            StyleManager.style_label(widget)
        elif isinstance(widget, QPushButton):
            StyleManager.style_button(widget)
        elif isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
            StyleManager.style_input_field(widget)
        elif isinstance(widget, QComboBox):
            StyleManager.style_combo_box(widget)
        elif isinstance(widget, QCheckBox):
            StyleManager.style_check_box(widget)
        elif isinstance(widget, QRadioButton):
            StyleManager.style_radio_button(widget)

    @staticmethod
    def style_label(label: QLabel) -> None:
        """标签样式"""
        label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 14px;
                padding: 2px 0;
                background: transparent;
            }
            QLabel.description {
                color: #6c757d;
                font-size: 13px;
                padding: 2px 0 8px 0;
            }
            QLabel.error-label {
                color: #dc3545;
                font-size: 12px;
                padding: 4px 0 0 0;
            }
            QLabel.type-hint {
            color: #4a6fa5;
            font-size: 13px;
            font-weight: 500;
            padding: 8px 0 12px 15px;
            background: rgba(234, 241, 247, 0.6);
            border-radius: 8px;
            margin: 5px 0;
            }
            QLabel.type-hint::before {
                content: "🛈 ";
                color: #6c8ebf;
            }
        """)

    @staticmethod
    def style_button(button: QPushButton) -> None:
        """按钮样式"""
        button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.8);
                color: #212529;
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 15px;
                padding: 8px 16px;
                min-width: 80px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.9);
                border-color: rgba(173, 181, 189, 0.8);
            }
            QPushButton:pressed {
                background-color: rgba(206, 212, 218, 0.9);
            }
            QPushButton:disabled {
                background-color: rgba(248, 249, 250, 0.7);
                color: #adb5bd;
            }
            QPushButton[special="true"] {
                border: 1px dashed rgba(108, 117, 125, 0.7);
                background-color: rgba(255, 255, 255, 0.5);
            }
            QPushButton[action="true"] {
                background-color: rgba(77, 171, 247, 0.9);
                color: white;
                border: 1px solid rgba(51, 154, 240, 0.9);
            }
            QPushButton[action="true"]:hover {
                background-color: rgba(51, 154, 240, 0.9);
            }
            QPushButton[action="true"]:pressed {
                background-color: rgba(34, 139, 230, 0.9);
            }
        """)

        # 添加按钮阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 3)
        button.setGraphicsEffect(shadow)

    @staticmethod
    def style_input_field(field: QWidget) -> None:
        """通用输入框样式（包括QLineEdit、QSpinBox、QDoubleSpinBox）"""
        field.setStyleSheet("""
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 120px;
                selection-background-color: #d0ebff;
                selection-color: #212529;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid rgba(77, 171, 247, 0.9);
                background-color: rgba(248, 249, 250, 0.9);
            }
            QLineEdit[invalid="true"], QSpinBox[invalid="true"], QDoubleSpinBox[invalid="true"] {
                border: 2px solid rgba(255, 107, 107, 0.9);
                background-color: rgba(255, 245, 245, 0.9);
            }
            QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
                background-color: rgba(248, 249, 250, 0.7);
                color: #adb5bd;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid rgba(206, 212, 218, 0.7);
                border-top-right-radius: 11px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                border-left: 1px solid rgba(206, 212, 218, 0.7);
                border-bottom-right-radius: 11px;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                image: none;
                width: 10px;
                height: 10px;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                image: none;
                width: 10px;
                height: 10px;
            }
        """)

        # 添加输入框阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(6)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        field.setGraphicsEffect(shadow)

    @staticmethod
    def style_combo_box(combo: QComboBox) -> None:
        """下拉框样式"""
        combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 120px;
            }
            QComboBox:focus {
                border: 2px solid rgba(77, 171, 247, 0.9);
            }
            QComboBox[invalid="true"] {
                border: 2px solid rgba(255, 107, 107, 0.9);
                background-color: rgba(255, 245, 245, 0.9);
            }
            QComboBox:disabled {
                background-color: rgba(248, 249, 250, 0.7);
                color: #adb5bd;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right;
                width: 20px;
                border-left: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 0 12px 12px 0;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 12px;
                padding: 4px;
                background-color: white;
                selection-background-color: #d0ebff;
            }
        """)

        # 添加下拉框阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(6)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        combo.setGraphicsEffect(shadow)

    @staticmethod
    def style_check_box(check_box: QCheckBox) -> None:
        """复选框样式"""
        check_box.setStyleSheet("""
            QCheckBox {
                spacing: 10px;
                font-size: 14px;
                color: #2c3e50;
                padding: 8px 0;
                background: transparent;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(173, 181, 189, 0.7);
                border-radius: 6px;
                background-color: rgba(255, 255, 255, 0.9);
            }
            QCheckBox::indicator:checked {
                border: 2px solid rgba(77, 171, 247, 0.9);
                background-color: rgba(255, 255, 255, 0.9);
            }
            QCheckBox::indicator:checked:hover {
                border: 2px solid rgba(77, 171, 247, 0.9);
            }
            QCheckBox::indicator:hover {
                border: 2px solid rgba(77, 171, 247, 0.9);
            }
            QCheckBox::indicator:pressed {
                border: 2px solid rgba(77, 171, 247, 0.9);
                background-color: rgba(230, 240, 250, 0.9);
            }
            QCheckBox[invalid="true"]::indicator {
                border: 2px solid rgba(255, 107, 107, 0.9);
                background-color: rgba(255, 245, 245, 0.9);
            }
            QCheckBox:disabled {
                color: #95a5a6;
            }
            QCheckBox::indicator:disabled {
                background-color: #ecf0f1;
                border: 2px solid #bdc3c7;
            }
        """)

    @staticmethod
    def style_radio_button(radio: QRadioButton) -> None:
        """单选按钮样式"""
        radio.setStyleSheet("""
            QRadioButton {
                spacing: 10px;
                font-size: 14px;
                color: #495057;
                background: transparent;
                margin-left: 10px;
                padding: 6px 0;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(173, 181, 189, 0.7);
                border-radius: 10px;
                background-color: rgba(255, 255, 255, 0.9);
            }
            QRadioButton::indicator:checked {
                border: 6px solid rgba(77, 171, 247, 0.9);
                background-color: rgba(255, 255, 255, 0.9);
            }
            QRadioButton::indicator:hover {
                border: 2px solid rgba(77, 171, 247, 0.9);
            }
            QRadioButton[invalid="true"]::indicator {
                border: 2px solid rgba(255, 107, 107, 0.9);
            }
        """)

    @staticmethod
    def style_group_box(group_box: QWidget) -> None:
        """组框样式"""
        group_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(222, 226, 230, 0.7);
                border-radius: 15px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 15px;
                font-weight: 500;
                color: #343a40;
                background-color: rgba(255, 255, 255, 0.7);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: transparent;
            }
        """)

        # 添加组框阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 3)
        group_box.setGraphicsEffect(shadow)

    @staticmethod
    def style_scroll_area(scroll_area: QWidget) -> None:
        """滚动区域样式"""
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(248, 249, 250, 0.7);
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(206, 212, 218, 0.7);
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(173, 181, 189, 0.7);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
