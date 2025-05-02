from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        form = QFormLayout()
        
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        
        layout.addLayout(form)
        layout.addStretch()
        self.setLayout(layout)