from typing import Optional
from PySide6.QtWidgets import QWidget, QLineEdit, QPushButton


class Style:
    """QSS样式表"""
    MAIN_BACKGROUND = "#F6F8FA"
    PANEL_BACKGROUND = "#FFFFFF"
    BORDER_COLOR = "#D0D7DE"
    TEXT_COLOR_PRIMARY = "#1F2328"
    TEXT_COLOR_SECONDARY = "#57606A"
    ACCENT_COLOR = "#0969DA"
    DANGER_COLOR = "#CF222E"
    SUCCESS_COLOR = "#1A7F37"

    @staticmethod
    def get_main_style() -> str:
        return f"""
            QWidget {{
                background-color: {Style.MAIN_BACKGROUND};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 10pt;
            }}
            QLabel {{
                color: {Style.TEXT_COLOR_PRIMARY};
            }}
            QToolTip {{
                background-color: {Style.PANEL_BACKGROUND};
                color: {Style.TEXT_COLOR_PRIMARY};
                border: 1px solid {Style.BORDER_COLOR};
                padding: 5px;
                border-radius: 4px;
            }}
        """

    TREE_WIDGET_STYLE = f"""
        QTreeWidget {{
            background-color: transparent;
            border: none;
            font-size: 13px;
            color: {TEXT_COLOR_PRIMARY};
            outline: 0;
        }}
        QTreeWidget::item {{
            min-height: 28px;
            padding: 4px 8px;
            border-radius: 6px;
            margin: 1px 0;
        }}
        QTreeWidget::item:hover {{
            background-color: #F3F4F6;
        }}
        QTreeWidget::item:selected {{
            background-color: {ACCENT_COLOR};
            color: white;
        }}
        QTreeWidget::branch {{
            background: transparent;
        }}
    """

    GROUP_BOX_STYLE = f"""
        QGroupBox {{
            background-color: transparent;
            border: 1px solid {BORDER_COLOR};
            border-radius: 8px;
            margin-top: 15px;
            padding: 25px 15px 15px 15px;
            font-size: 14px;
            font-weight: 600;
            color: {TEXT_COLOR_PRIMARY};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 15px;
            padding: 0 5px;
            background-color: {PANEL_BACKGROUND};
        }}
    """

    LIST_WIDGET_STYLE = f"""
        QListWidget {{
            background-color: #FFFFFF;
            border: 1px solid {BORDER_COLOR};
            border-radius: 6px;
            padding: 4px;
            font-size: 13px;
            color: {TEXT_COLOR_PRIMARY};
        }}
        QListWidget::item {{
            padding: 8px 10px;
            border-radius: 4px;
        }}
        QListWidget::item:hover {{
            background-color: {MAIN_BACKGROUND};
        }}
        QListWidget::item:selected {{
            background-color: #DDEDFF;
            color: {ACCENT_COLOR};
            font-weight: 500;
        }}
    """

    SCROLL_AREA_STYLE = f"""
        QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            border: none;
            background: {MAIN_BACKGROUND};
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: #C9D1D9;
            min-height: 25px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            border: none; background: none; height: 0;
        }}
    """


class StyledLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Style.PANEL_BACKGROUND};
                border: 1px solid {Style.BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: {Style.TEXT_COLOR_PRIMARY};
                min-height: 28px;
            }}
            QLineEdit:hover {{
                border-color: #88929D;
            }}
            QLineEdit:focus {{
                border: 2px solid {Style.ACCENT_COLOR};
                padding: 7px 11px;
            }}
        """)


class StyledButton(QPushButton):
    def __init__(self, text: str, role: str = "default", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        base_style = """
            QPushButton {
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                min-width: 70px;
            }
        """
        if role == "primary":
            self.setStyleSheet(base_style + f"""
                QPushButton {{
                    background-color: {Style.SUCCESS_COLOR};
                    border: 1px solid {Style.SUCCESS_COLOR};
                    color: white;
                }}
                QPushButton:hover {{ background-color: #1A7431; }}
                QPushButton:pressed {{ background-color: #15612A; }}
                QPushButton:disabled {{ background-color: #87C596; border-color: #87C596; }}
            """)
        else:
            self.setStyleSheet(base_style + f"""
                QPushButton {{
                    background-color: #F6F8FA;
                    border: 1px solid #D0D7DE;
                    color: {Style.TEXT_COLOR_PRIMARY};
                }}
                QPushButton:hover {{ background-color: #F3F4F6; }}
                QPushButton:pressed {{ background-color: #EDEFF2; }}
                QPushButton:disabled {{ background-color: #F6F8FA; color: #8B949E; }}
            """)
