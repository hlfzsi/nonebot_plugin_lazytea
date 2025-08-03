from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QLineEdit,
    QPushButton, QWidget, QCheckBox, QFormLayout,
    QApplication, QHBoxLayout
)
from PySide6.QtCore import Signal, Slot, Qt

from .config_manager import ConnectionDetails
from typing import Optional


class LoginDialog(QDialog):
    connect_requested = Signal(str, int, str, bool)

    def __init__(self, parent: Optional[QWidget] = None, initial_details: Optional[ConnectionDetails] = None):
        super().__init__(parent)
        self.setWindowTitle("连接设置")
        self.setWindowFlags(self.windowFlags() & ~
                            Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(400)

        self._initial_details = initial_details

        self._init_ui()
        self._apply_styles()
        self._connect_signals()

        if self._initial_details and self._initial_details.remember:
            self.populate_fields(self._initial_details)

    def _init_ui(self):
        """初始化UI控件"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("独立客户端")
        title.setObjectName("titleLabel")

        description = QLabel("请提供WebSocket服务器的地址和端口。")
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        self.host_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("8080")
        self.token_input = QLineEdit("疯狂星期四V我50")
        form_layout.addRow("服务器地址 (Host):", self.host_input)
        form_layout.addRow("端口 (Port):", self.port_input)
        form_layout.addRow("令牌 (Token):", self.token_input)

        self.remember_checkbox = QCheckBox("记住此连接")
        self.remember_checkbox.setChecked(True)

        self.error_label = QLabel()
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)

        # 为按钮创建一个水平布局
        button_layout = QHBoxLayout()
        self.close_button = QPushButton("关闭")
        self.close_button.setObjectName("closeButton")
        self.connect_button = QPushButton("连接")
        self.connect_button.setObjectName("connectButton")

        button_layout.addWidget(self.close_button)
        button_layout.addStretch()
        button_layout.addWidget(self.connect_button)

        main_layout.addWidget(title)
        main_layout.addWidget(description)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.remember_checkbox)
        main_layout.addStretch()
        main_layout.addWidget(self.error_label)
        main_layout.addLayout(button_layout)

    def _apply_styles(self):
        """应用QSS样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
                font-family: "Segoe UI", "Microsoft YaHei";
                color: #000000; 
            }
            QLabel {
                color: #000000; 
            }
            #titleLabel {
                font-size: 20px;
                font-weight: 600;
                color: #000000;
            }
            #descriptionLabel {
                color: #000000;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #CED4DA;
                border-radius: 6px;
                background-color: white;
                color: #000000; 
            }
            QLineEdit:focus {
                border-color: #80BDFF;
            }
            QCheckBox {
                color: #000000; 
            }
            #errorLabel {
                color: #000000; 
                background-color: #F8D7DA;
                border: 1px solid #F5C6CB;
                border-radius: 6px;
                padding: 10px;
            }
            #connectButton {
                background-color: #007BFF;
                color: #000000; 
                font-weight: 500;
                padding: 10px;
                border: none;
                border-radius: 6px;
                min-width: 80px;
            }
            #connectButton:hover {
                background-color: #0056b3;
            }
            #connectButton:disabled {
                background-color: #6C757D;
            }
            #closeButton {
                background-color: #6C757D;
                color: #FFFFFF; 
                font-weight: 500;
                padding: 10px;
                border: none;
                border-radius: 6px;
                min-width: 80px;
            }
            #closeButton:hover {
                background-color: #5a6268;
            }
        """)

    def _connect_signals(self):
        """连接信号和槽"""
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.close_button.clicked.connect(self._close_application)

    def populate_fields(self, details: ConnectionDetails):
        """使用已有的配置信息填充输入框"""
        self.host_input.setText(details.host)
        self.port_input.setText(str(details.port))
        self.token_input.setText(details.token)
        self.remember_checkbox.setChecked(details.remember)

    @Slot()
    def _on_connect_clicked(self):
        """处理连接按钮点击事件"""
        host = self.host_input.text().strip()
        port_str = self.port_input.text().strip()
        token = self.token_input.text()

        # 基本校验
        if not host or not port_str:
            self.show_error("服务器地址和端口不能为空。")
            return

        try:
            port = int(port_str)
        except ValueError:
            self.show_error("端口必须是一个有效的数字。")
            return

        self.connect_button.setText("正在连接...")
        self.connect_button.setEnabled(False)
        self.error_label.setVisible(False)

        self.connect_requested.emit(
            host,
            port,
            token,
            self.remember_checkbox.isChecked()
        )

    @Slot(str)
    def show_error(self, message: str):
        """在对话框上显示错误信息，并恢复按钮状态"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.connect_button.setText("连接")
        self.connect_button.setEnabled(True)

    @Slot()
    def _close_application(self):
        """关闭应用程序"""
        app = QApplication.instance()
        if app:
            app.quit()

    @Slot()
    def connection_successful(self):
        """连接成功时调用的槽，关闭对话框"""
        self.accept()
