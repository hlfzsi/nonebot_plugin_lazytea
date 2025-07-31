__all__ = ["NoWheelSpinBox", "NoWheelDoubleSpinBox",
           "NoWheelComboBox", "NonScrollingTextBrowser"]
from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox, QComboBox, QTextBrowser
from PySide6.QtGui import QWheelEvent
from PySide6.QtCore import Qt


class NoWheelSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NonScrollingTextBrowser(QTextBrowser):
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()
