from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QLineEdit,
                               QComboBox, QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox,
                               QGroupBox, QScrollArea)
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


class StyleManager:
    """统一管理所有控件的样式"""

    @staticmethod
    def apply_base_style(widget: QWidget) -> None:
        palette = widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
        widget.setAutoFillBackground(True)
        widget.setPalette(palette)

    @staticmethod
    def apply_style(widget: QWidget) -> None:
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
        elif isinstance(widget, QGroupBox):
            StyleManager.style_group_box(widget)
        elif isinstance(widget, QScrollArea):
            StyleManager.style_scroll_area(widget)

    @staticmethod
    def style_label(label: QLabel) -> None:
        label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                color: #495057;
                font-size: 14px;
                padding: 2px 0px;
            }
            QLabel[class="description"] {
                color: #6c757d;
                font-size: 13px;
                padding: 2px 0px 8px 0px;
            }
            QLabel[class="error-label"] {
                color: #dc3545;
                font-size: 12px;
                padding: 4px 0px 0px 0px;
            }
            QLabel[class="type-hint"] {
                color: #4a6fa5;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 0px 12px 15px;
                background-color: rgba(234, 241, 247, 153);
                border-radius: 8px;
                margin: 5px 0px;
            }
        """)

    @staticmethod
    def style_button(button: QPushButton) -> None:
        button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #212529;
                border: 1px solid rgba(206, 212, 218, 179);
                border-radius: 15px;
                padding: 8px 16px;
                min-width: 80px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(248, 249, 250, 230);
                border-color: rgba(173, 181, 189, 204);
            }
            QPushButton:pressed {
                background-color: rgba(206, 212, 218, 230);
            }
            QPushButton:disabled {
                background-color: rgba(248, 249, 250, 179);
                color: #adb5bd;
            }
            QPushButton[special="true"] {
                border: 1px dashed rgba(108, 117, 125, 179);
                background-color: rgba(255, 255, 255, 128);
            }
            QPushButton[action="true"] {
                background-color: rgba(77, 171, 247, 230);
                color: #ffffff;
                border: 1px solid rgba(51, 154, 240, 230);
            }
        """)

        shadow = QGraphicsDropShadowEffect(button)
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 3)
        button.setGraphicsEffect(shadow)

    @staticmethod
    def style_input_field(field: QWidget) -> None:
        field.setStyleSheet("""
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 120px;
                color: #000000;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #4dabf7;
                background-color: #f8f9fa;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(field)
        shadow.setBlurRadius(6)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        field.setGraphicsEffect(shadow)

    @staticmethod
    def style_combo_box(combo: QComboBox) -> None:
        combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 120px;
                color: #000000;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 1px;
                border-left-color: #ced4da;
                border-left-style: solid;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                selection-background-color: #4dabf7;
                selection-color: #ffffff;
                outline: 0px;
                color: #000000;
            }
        """)

    @staticmethod
    def style_check_box(check_box: QCheckBox) -> None:
        check_box.setStyleSheet("""
            QCheckBox {
                background-color: #ffffff;
                spacing: 10px;
                font-size: 14px;
                color: #2c3e50;
                padding: 8px 0px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #adb5bd;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4dabf7;
            }
            QCheckBox::indicator:disabled {
                border: 2px solid #e9ecef;
            }
        """)

    @staticmethod
    def style_radio_button(radio: QRadioButton) -> None:
        radio.setStyleSheet("""
            QRadioButton {
                background-color: #ffffff;
                spacing: 10px;
                font-size: 14px;
                color: #495057;
                margin-left: 10px;
                padding: 6px 0px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #adb5bd;
                border-radius: 10px;
                background-color: #ffffff;
            }
            QRadioButton::indicator:checked {
                background-color: #4dabf7;
                border: 2px solid #4dabf7;
            }
            QRadioButton::indicator:disabled {
                border: 2px solid #e9ecef;
            }
        """)

    @staticmethod
    def style_group_box(group_box: QGroupBox) -> None:
        group_box.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 15px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 15px;
                font-weight: 500;
                color: #343a40;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0px 5px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(group_box)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 3)
        group_box.setGraphicsEffect(shadow)

    @staticmethod
    def style_scroll_area(scroll_area: QScrollArea) -> None:
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            QScrollBar:vertical {
                background: #ffffff;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #ced4da;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
