from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QLineEdit,
                               QComboBox, QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox)
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


class StyleManager:
    """统一管理所有控件的样式"""

    @staticmethod
    def apply_base_style(widget: QWidget) -> None:
        """应用基础背景（纯白色确保兼容性）"""
        palette = widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
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
                background-color: white;
                color: #495057;
                font-size: 14px;
                padding: 2px 0;
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
                background-color: white;
                color: #212529;
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 15px;
                padding: 8px 16px;
                min-width: 80px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(248, 249, 250, 0.9);
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
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 3)
        button.setGraphicsEffect(shadow)

    @staticmethod
    def style_input_field(field: QWidget) -> None:
        """输入框样式"""
        field.setStyleSheet("""
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: white;
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 120px;
                color: #000000;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid rgba(77, 171, 247, 0.9);
                background-color: rgba(248, 249, 250, 0.9);
                color: #000000;
            }
        """)

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
                background-color: white;
                border: 1px solid rgba(206, 212, 218, 0.7);
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 120px;
                color: #000000;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid rgba(206, 212, 218, 0.7);
                color: #000000;
            }
        """)

    @staticmethod
    def style_check_box(check_box: QCheckBox) -> None:
        """复选框样式"""
        check_box.setStyleSheet("""
            QCheckBox {
                background-color: white;
                spacing: 10px;
                font-size: 14px;
                color: #2c3e50;
                padding: 8px 0;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                color: #000000;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(173, 181, 189, 0.7);
                border-radius: 6px;
                background-color: white;
                color: #000000;
            }
            QCheckBox::indicator:checked {
                border: 2px solid rgba(77, 171, 247, 0.9);
                background-color: white;
                color: #000000;
            }
        """)

    @staticmethod
    def style_radio_button(radio: QRadioButton) -> None:
        """单选按钮样式"""
        radio.setStyleSheet("""
            QRadioButton {
                background-color: white;
                spacing: 10px;
                font-size: 14px;
                color: #495057;
                margin-left: 10px;
                padding: 6px 0;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(173, 181, 189, 0.7);
                border-radius: 10px;
                background-color: white;
            }
        """)

    @staticmethod
    def style_group_box(group_box: QWidget) -> None:
        """组框样式"""
        group_box.setStyleSheet("""
            QGroupBox {
                background-color: white;
                border: 1px solid rgba(222, 226, 230, 0.7);
                border-radius: 15px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 15px;
                font-weight: 500;
                color: #343a40;
            }
        """)

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
                background-color: white;
                border: none;
            }
            QScrollBar:vertical {
                background: white;
                width: 10px;
            }
        """)
