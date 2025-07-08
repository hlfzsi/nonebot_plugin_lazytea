import sys
import ujson
from typing import Dict, List, Optional, Sequence, TypedDict, Any
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget,
    QTreeWidgetItem, QGroupBox, QCheckBox, QLineEdit, QPushButton, QListWidget,
    QLabel, QMessageBox, QDialogButtonBox, QDialog, QComboBox, QSizePolicy,
    QAbstractItemView, QFrame, QScrollArea, QTextEdit, QGridLayout)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QFont


from ...Qcomponents.MessageBox import MessageBoxBuilder, MessageBoxConfig, ButtonConfig
from ...client import talker, ResponsePayload


class PermissionListDivide(TypedDict):
    user: List[str]
    group: List[str]


class MatcherPermission(TypedDict):
    white_list: PermissionListDivide
    ban_list: PermissionListDivide


class MatcherRuleModel(TypedDict):
    rule: Dict[str, Any]
    permission: MatcherPermission
    is_on: bool


class PluginModel(TypedDict):
    matchers: List[MatcherRuleModel]


class BotModel(TypedDict):
    plugins: Dict[str, PluginModel]


class FullConfigModel(TypedDict):
    bots: Dict[str, BotModel]


class ReadableRoster:
    config: FullConfigModel = {"bots": {}}

    @classmethod
    def check(
        cls,
        bot: str,
        plugin: str,
        matcher_key: str,
        userid: str,
        groupid: Optional[str] = None
    ) -> bool:
        bot_config = cls.config.get("bots", {}).get(bot)
        if not bot_config:
            return True

        plugin_config = bot_config.get("plugins", {}).get(plugin)
        if not plugin_config:
            return True

        for matcher in plugin_config.get("matchers", []):
            if cls._get_rule_display_name(matcher["rule"]) == matcher_key:
                return cls._evaluate_matcher_config(matcher, userid, groupid)

        return True

    @classmethod
    def _evaluate_matcher_config(
        cls,
        matcher_config: MatcherRuleModel,
        userid: str,
        groupid: Optional[str]
    ) -> bool:
        is_on = matcher_config.get("is_on", True)
        white_list = matcher_config["permission"]["white_list"]
        ban_list = matcher_config["permission"]["ban_list"]

        in_white_user = userid in white_list["user"]
        in_white_group = groupid and groupid in white_list["group"]

        in_ban_user = userid in ban_list["user"]
        in_ban_group = groupid and groupid in ban_list["group"]

        if is_on:
            if in_ban_user or in_ban_group:
                return False
            return True
        else:
            if in_white_user or in_white_group:
                return True
            return False

    @classmethod
    def update_config(cls, new_config: FullConfigModel):
        cls.config = new_config

    @classmethod
    def get_config(cls) -> FullConfigModel:
        return cls.config

    @staticmethod
    def _get_rule_display_name(rule_data: dict) -> str:

        if rule_data.get("alconna_commands"):
            cmds = rule_data["alconna_commands"]
            if cmds:
                return f"Alconna: {', '.join(cmds)}"

        if rule_data.get("commands"):
            cmds = rule_data["commands"]
            if cmds:
                return f"命令: {", ".join("/".join(cmd) for cmd in cmds)}"

        if rule_data.get("regex_patterns"):
            patterns = rule_data["regex_patterns"]
            if patterns:
                return f"正则: {','.join(patterns)}..."

        if rule_data.get("keywords"):
            keywords = rule_data["keywords"]
            if keywords:
                return f"关键词: {','.join(keywords)}"

        if rule_data.get("startswith"):
            starts = rule_data["startswith"]
            if starts:
                return f"开头: {','.join(starts)}"

        if rule_data.get("endswith"):
            ends = rule_data["endswith"]
            if ends:
                return f"结尾: {','.join(ends)}"

        if rule_data.get("fullmatch"):
            fullmatches = rule_data["fullmatch"]
            if fullmatches:
                return f"完全匹配: {','.join(fullmatches)}"

        if rule_data.get("event_types"):
            types = rule_data["event_types"]
            if types:
                return f"事件类型: {','.join(types)}"

        if rule_data.get("to_me", False):
            return "@机器人 or 包含机器人名称"

        return "未命名规则"


class StyledTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
                color: #24292E;
                outline: 0;
            }
            QTreeWidget::item {
                height: 30px;
                padding: 4px 6px;
                border-radius: 4px;
                margin: 1px 0;
            }
            QTreeWidget::item:hover {
                background-color: #F6F8FA;
            }
            QTreeWidget::item:selected {
                background-color: #E7F5FF;
                color: #24292E;
                border: 1px solid #D0E3FF;
                margin: 2px 0;
            }
            QTreeWidget::item:selected:active,
            QTreeWidget::item:selected:!active {
                background-color: #E7F5FF;
            }
            QTreeWidget::branch {
                background-color: transparent;
            }
            QTreeWidget::branch:has-siblings:!adjoins-item {
                border-image: none;
            }
            QTreeWidget::branch:has-siblings:adjoins-item {
                border-image: none;
            }
            QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
                border-image: none;
            }
        """)
        self.setIndentation(15)


class StyledGroupBox(QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 24px;
                font-size: 15px;
                font-weight: 500;
                color: #24292E;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)


class StyledListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                padding: 4px;
                font-size: 14px;
                color: #24292E;
            }
            QListWidget::item {
                height: 36px;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #F6F8FA;
            }
            QListWidget::item:selected {
                background-color: #E7F5FF;
                color: #24292E;
                border: 1px solid #D0E3FF;
            }
        """)


class SearchableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_items = []
        self.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                padding: 4px;
                font-size: 14px;
                color: #24292E;
            }
            QListWidget::item {
                height: 36px;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #F6F8FA;
            }
            QListWidget::item:selected {
                background-color: #E7F5FF;
                color: #24292E;
                border: 1px solid #D0E3FF;
            }
        """)

    @property
    def full_items(self):
        return self._full_items.copy()

    def addItems(self, labels: Sequence[str]) -> None:
        super().addItems(labels)
        self._full_items.extend(labels)

    def addItem(self, item) -> None:
        super().addItem(item)
        if isinstance(item, str):
            self._full_items.append(item)
        elif hasattr(item, "text"):
            self._full_items.append(item.text())

    def filter_items(self, text: str):
        super().clear()
        if not text:
            super().addItems(self._full_items)
        else:
            text_lower = text.lower()
            filtered = [item for item in self._full_items
                        if text_lower in item.lower()]
            super().addItems(filtered)


class StyledLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                color: #24292E;
                min-height: 36px;
            }
            QLineEdit:hover {
                border-color: #A8D1FF;
            }
            QLineEdit:focus {
                border: 1px solid #2188FF;
                outline: none;
            }
        """)


class StyledTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                color: #24292E;
            }
            QTextEdit:hover {
                border-color: #A8D1FF;
            }
            QTextEdit:focus {
                border: 1px solid #2188FF;
                outline: none;
            }
        """)


class StyledPushButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #F6F8FA;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                color: #24292E;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #E1E4E8;
                border-color: #D0D7DE;
            }
            QPushButton:pressed {
                background-color: #D0D7DE;
            }
            QPushButton:focus {
                border: 1px solid #A8D1FF;
                outline: none;
            }
            QPushButton:disabled {
                background-color: #F6F8FA;
                color: #8D949E;
            }
        """)


class PrimaryButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2188FF;
                border: 1px solid #2188FF;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                color: white;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0C7AE6;
                border-color: #0C7AE6;
            }
            QPushButton:pressed {
                background-color: #0B6DCC;
            }
            QPushButton:focus {
                border: 1px solid #A8D1FF;
                outline: none;
            }
            QPushButton:disabled {
                background-color: #94D3FF;
                color: #F6F8FA;
            }
        """)


class SecondaryButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                color: #24292E;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #F6F8FA;
                border-color: #D0D7DE;
            }
            QPushButton:pressed {
                background-color: #E1E4E8;
            }
            QPushButton:focus {
                border: 1px solid #A8D1FF;
                outline: none;
            }
        """)


class ResponsiveScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #F6F8FA;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #E1E4E8;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
                height: 0px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)


class RuleDetailLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QLabel {
                background-color: #F6F8FA;
                border: 1px solid #E1E4E8;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                color: #24292E;
                margin: 2px;
            }
        """)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft |
                          Qt.AlignmentFlag.AlignVCenter)


class PermissionConfigurator(QWidget):
    config_updated = Signal(dict)
    success_signal = Signal(ResponsePayload)
    error_signal = Signal(ResponsePayload)

    def __init__(
        self,
        initial_config: FullConfigModel,
        bot_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: #F6F8FA;
                font-family: 'Microsoft YaHei', sans-serif;
                font-size: 10pt;
            }
            QLabel {
                color: #24292E;
            }
            QToolTip {
                background-color: #FFFFFF;
                color: #24292E;
                border: 1px solid #E1E4E8;
                padding: 4px;
                border-radius: 4px;
            }
        """)

        self.success_signal.connect(self._show_success)
        self.error_signal.connect(self._show_error)

        self.filter_bot_id = bot_id
        self.filter_plugin_name = plugin_name

        try:
            ReadableRoster.update_config(initial_config)
        except Exception as e:
            QMessageBox.critical(self, "配置错误", f"无法解析配置数据: {str(e)}")
            raise

        self.init_ui()
        self.build_config_tree()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        self.setLayout(main_layout)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_widget.setLayout(content_layout)

        scroll_area = ResponsiveScrollArea()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Expanding)
        splitter.setHandleWidth(12)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E1E4E8;
                width: 1px;
            }
            QSplitter::handle:hover {
                background-color: #D0D7DE;
            }
        """)

        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: transparent;")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.config_tree = StyledTreeWidget()
        self.config_tree.setHeaderHidden(True)
        self.config_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.config_tree.itemSelectionChanged.connect(self.on_item_selected)
        self.config_tree.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.config_tree)

        left_panel.setLayout(left_layout)

        self.config_panel_container = QWidget()
        self.config_panel_container.setStyleSheet(
            "background-color: transparent;")
        self.config_panel_layout = QVBoxLayout()
        self.config_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.config_panel_layout.setSpacing(12)
        self.config_panel_container.setLayout(self.config_panel_layout)

        config_scroll = ResponsiveScrollArea()
        config_scroll.setWidget(self.config_panel_container)

        panel_frame = QFrame()
        panel_frame.setFrameShape(QFrame.Shape.StyledPanel)
        panel_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
            }
        """)
        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(config_scroll)
        panel_frame.setLayout(panel_layout)

        self.clear_config_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(panel_frame)

        splitter.setSizes([280, 720])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.splitter = splitter

        content_layout.addWidget(splitter, 1)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 12, 0, 0)
        button_layout.setSpacing(12)

        self.save_button = PrimaryButton("保存配置")
        self.save_button.setIcon(QIcon.fromTheme("document-save"))
        self.save_button.clicked.connect(self.save_config)

        self.test_button = SecondaryButton("测试权限")
        self.test_button.setIcon(QIcon.fromTheme("system-run"))
        self.test_button.clicked.connect(self.test_permission)

        button_layout.addStretch()
        button_layout.addWidget(self.test_button)
        button_layout.addWidget(self.save_button)

        content_layout.addLayout(button_layout)

    def build_config_tree(self):
        self.config_tree.clear()
        current_config = ReadableRoster.get_config()

        bot_font = QFont()
        bot_font.setBold(True)
        bot_font.setPointSize(13)

        plugin_font = QFont()
        plugin_font.setBold(True)
        plugin_font.setPointSize(12)

        matcher_font = QFont()
        matcher_font.setPointSize(11)

        bots_to_display = []
        if self.filter_bot_id:
            if self.filter_bot_id in current_config["bots"]:
                bots_to_display.append(self.filter_bot_id)
        else:
            bots_to_display = list(current_config["bots"].keys())

        for bot_id in bots_to_display:
            bot_data = current_config["bots"][bot_id]
            plugins = bot_data["plugins"]

            plugins_to_display = []
            if self.filter_plugin_name:
                if self.filter_plugin_name in plugins:
                    plugins_to_display.append(self.filter_plugin_name)
            else:
                plugins_to_display = list(plugins.keys())

            if not plugins_to_display:
                continue

            bot_item = QTreeWidgetItem(self.config_tree, [bot_id])
            bot_item.setData(0, Qt.ItemDataRole.UserRole, ("bot", bot_id))
            bot_item.setFont(0, bot_font)

            for plugin_name in plugins_to_display:
                plugin_data = plugins[plugin_name]
                plugin_item = QTreeWidgetItem(bot_item, [plugin_name])
                plugin_item.setData(0, Qt.ItemDataRole.UserRole,
                                    ("plugin", bot_id, plugin_name))
                plugin_item.setFont(0, plugin_font)

                for matcher in plugin_data["matchers"]:
                    matcher_key = ReadableRoster._get_rule_display_name(
                        matcher["rule"])
                    matcher_item = QTreeWidgetItem(plugin_item, [matcher_key])
                    matcher_item.setData(
                        0, Qt.ItemDataRole.UserRole, ("matcher", bot_id, plugin_name, matcher_key))
                    matcher_item.setIcon(0, QIcon.fromTheme("text-x-generic"))
                    matcher_item.setFont(0, matcher_font)

        self.config_tree.expandAll()
        self.config_tree.setRootIsDecorated(True)
        self.config_tree.setItemsExpandable(True)

    def clear_config_panel(self):
        for i in reversed(range(self.config_panel_layout.count())):
            widget = self.config_panel_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def on_item_selected(self):
        selected_items = self.config_tree.selectedItems()
        if not selected_items:
            self.clear_config_panel()
            return

        item = selected_items[0]
        item_type, *item_data = item.data(0, Qt.ItemDataRole.UserRole)

        self.clear_config_panel()

        if item_type == "bot":
            self.show_bot_config(item_data[0])
        elif item_type == "plugin":
            bot_id, plugin_name = item_data
            self.show_plugin_config(bot_id, plugin_name)
        elif item_type == "matcher":
            bot_id, plugin_name, matcher_key = item_data
            self.show_matcher_config(bot_id, plugin_name, matcher_key)

    def show_bot_config(self, bot_id: str):
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout()
        scroll_content.setLayout(scroll_layout)

        scroll = ResponsiveScrollArea()
        scroll.setWidget(scroll_content)
        self.config_panel_layout.addWidget(scroll)

        group = StyledGroupBox(f"机器人配置: {bot_id}")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(16)
        group.setLayout(layout)
        scroll_layout.addWidget(group)

        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #F6F8FA;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)

        title_label = QLabel(f"机器人ID: {bot_id}")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #24292E;
        """)
        info_layout.addWidget(title_label)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        current_config = ReadableRoster.get_config()
        bot_data = current_config["bots"].get(bot_id, {"plugins": {}})
        plugins_count = len(bot_data["plugins"])
        plugins_label = QLabel(f"插件数量: {plugins_count}")
        plugins_label.setStyleSheet("""
            font-size: 14px;
            color: #57606A;
        """)
        stats_layout.addWidget(plugins_label)

        total_matchers = sum(
            len(plugin["matchers"])
            for plugin in bot_data["plugins"].values()
        )
        matchers_label = QLabel(f"规则总数: {total_matchers}")
        matchers_label.setStyleSheet("""
            font-size: 14px;
            color: #57606A;
        """)
        stats_layout.addWidget(matchers_label)

        stats_layout.addStretch()
        info_layout.addLayout(stats_layout)
        info_card.setLayout(info_layout)
        layout.addWidget(info_card)

        plugin_group = StyledGroupBox("插件列表")
        plugin_layout = QVBoxLayout()
        plugin_layout.setContentsMargins(12, 20, 12, 12)
        plugin_layout.setSpacing(12)

        self.plugin_list = StyledListWidget()
        self.plugin_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)

        for plugin_name in bot_data["plugins"].keys():
            self.plugin_list.addItem(plugin_name)

        plugin_layout.addWidget(self.plugin_list)
        plugin_group.setLayout(plugin_layout)
        layout.addWidget(plugin_group, 1)

    def show_plugin_config(self, bot_id: str, plugin_name: str):
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout()
        scroll_content.setLayout(scroll_layout)

        scroll = ResponsiveScrollArea()
        scroll.setWidget(scroll_content)
        self.config_panel_layout.addWidget(scroll)

        group = StyledGroupBox(f"插件配置: {plugin_name}")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(16)
        group.setLayout(layout)
        scroll_layout.addWidget(group)

        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #F6F8FA;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)

        title_label = QLabel(f"插件名称: {plugin_name}")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #24292E;
        """)
        info_layout.addWidget(title_label)

        bot_label = QLabel(f"所属机器人: {bot_id}")
        bot_label.setStyleSheet("""
            font-size: 14px;
            color: #57606A;
        """)
        info_layout.addWidget(bot_label)

        current_config = ReadableRoster.get_config()
        plugin_data = current_config["bots"].get(bot_id, {"plugins": {}}).get(
            "plugins", {}).get(plugin_name, {"matchers": []})
        matchers_count = len(plugin_data["matchers"])
        matchers_label = QLabel(f"规则数量: {matchers_count}")
        matchers_label.setStyleSheet("""
            font-size: 14px;
            color: #57606A;
        """)
        info_layout.addWidget(matchers_label)

        info_card.setLayout(info_layout)
        layout.addWidget(info_card)

        matcher_group = StyledGroupBox("规则列表")
        matcher_layout = QVBoxLayout()
        matcher_layout.setContentsMargins(12, 20, 12, 12)
        matcher_layout.setSpacing(12)

        self.matcher_list = StyledListWidget()
        self.matcher_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)

        for matcher in plugin_data["matchers"]:
            matcher_key = ReadableRoster._get_rule_display_name(
                matcher["rule"])
            self.matcher_list.addItem(matcher_key)

        matcher_layout.addWidget(self.matcher_list)
        matcher_group.setLayout(matcher_layout)
        layout.addWidget(matcher_group, 1)

    def create_rule_detail_widget(self, rule_data: dict) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel("规则详情")
        title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: 600;
            color: #24292E;
        """)
        layout.addWidget(title_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)

        row = 0

        if rule_data.get("alconna_commands"):
            commands = rule_data["alconna_commands"]
            if commands:
                grid.addWidget(QLabel("Alconna 命令"), row, 0)
                commands_label = RuleDetailLabel(", ".join(commands))
                grid.addWidget(commands_label, row, 1)
                row += 1

        if rule_data.get("commands"):
            commands = rule_data["commands"]
            if commands:
                grid.addWidget(QLabel("命令"), row, 0)
                commands_label = RuleDetailLabel(
                    ", ".join("/".join(cmd) for cmd in commands))
                grid.addWidget(commands_label, row, 1)
                row += 1

        if rule_data.get("regex_patterns"):
            patterns = rule_data["regex_patterns"]
            if patterns:
                grid.addWidget(QLabel("正则表达式"), row, 0)
                patterns_label = RuleDetailLabel(", ".join(patterns))
                grid.addWidget(patterns_label, row, 1)
                row += 1

        if rule_data.get("keywords"):
            keywords = rule_data["keywords"]
            if keywords:
                grid.addWidget(QLabel("关键词"), row, 0)
                keywords_label = RuleDetailLabel(", ".join(keywords))
                grid.addWidget(keywords_label, row, 1)
                row += 1

        if rule_data.get("startswith"):
            starts = rule_data["startswith"]
            if starts:
                grid.addWidget(QLabel("开头匹配"), row, 0)
                starts_label = RuleDetailLabel(", ".join(starts))
                grid.addWidget(starts_label, row, 1)
                row += 1

        if rule_data.get("endswith"):
            ends = rule_data["endswith"]
            if ends:
                grid.addWidget(QLabel("结尾匹配"), row, 0)
                ends_label = RuleDetailLabel(", ".join(ends))
                grid.addWidget(ends_label, row, 1)
                row += 1

        if rule_data.get("fullmatch"):
            fullmatches = rule_data["fullmatch"]
            if fullmatches:
                grid.addWidget(QLabel("完全匹配"), row, 0)
                fullmatches_label = RuleDetailLabel(", ".join(fullmatches))
                grid.addWidget(fullmatches_label, row, 1)
                row += 1

        if rule_data.get("event_types"):
            types = rule_data["event_types"]
            if types:
                grid.addWidget(QLabel("事件类型"), row, 0)
                types_label = RuleDetailLabel(", ".join(types))
                grid.addWidget(types_label, row, 1)
                row += 1

        if rule_data.get("to_me", False):
            grid.addWidget(QLabel("触发方式"), row, 0)
            to_me_label = RuleDetailLabel("机器人相关信息")
            grid.addWidget(to_me_label, row, 1)
            row += 1

        if row == 0:
            no_rule_label = QLabel("此规则没有设置任何匹配条件")
            no_rule_label.setStyleSheet("color: #57606A; font-style: italic;")
            grid.addWidget(no_rule_label, row, 0, 1, 2)

        layout.addLayout(grid)
        widget.setLayout(layout)
        return widget

    def show_matcher_config(self, bot_id: str, plugin_name: str, matcher_key: str):
        current_config = ReadableRoster.get_config()
        plugin_data = current_config["bots"].get(bot_id, {"plugins": {}}).get(
            "plugins", {}).get(plugin_name, {"matchers": []})

        matcher_config = None
        for matcher in plugin_data["matchers"]:
            if ReadableRoster._get_rule_display_name(matcher["rule"]) == matcher_key:
                matcher_config = matcher
                break

        if not matcher_config:
            return

        rule_data = matcher_config["rule"]
        is_on = matcher_config.get("is_on", True)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout()
        scroll_content.setLayout(scroll_layout)

        scroll = ResponsiveScrollArea()
        scroll.setWidget(scroll_content)
        self.config_panel_layout.addWidget(scroll)

        group = StyledGroupBox(f"规则配置: {matcher_key[:50]}")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(16)
        group.setLayout(layout)
        scroll_layout.addWidget(group)

        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #F6F8FA;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)

        title_label = QLabel(f"规则: {matcher_key}")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #24292E;
        """)
        info_layout.addWidget(title_label)

        plugin_label = QLabel(f"所属插件: {plugin_name} (机器人: {bot_id})")
        plugin_label.setStyleSheet("""
            font-size: 14px;
            color: #57606A;
        """)
        info_layout.addWidget(plugin_label)

        status_label = QLabel(
            "状态: " +
            ("<span style='color:#2DA44E;'>已启用</span>" if is_on else "<span style='color:#D1242F;'>已禁用</span>")
        )
        status_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(status_label)

        info_card.setLayout(info_layout)
        layout.addWidget(info_card)

        rule_card = QFrame()
        rule_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        rule_layout = QVBoxLayout()
        rule_layout.setContentsMargins(0, 0, 0, 0)
        rule_layout.setSpacing(8)

        rule_detail_widget = self.create_rule_detail_widget(rule_data)
        rule_layout.addWidget(rule_detail_widget)

        rule_card.setLayout(rule_layout)
        layout.addWidget(rule_card)

        switch_card = QFrame()
        switch_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        switch_layout = QHBoxLayout()
        switch_layout.setContentsMargins(0, 0, 0, 0)

        self.enable_check = QCheckBox("启用此规则")
        self.enable_check.setChecked(is_on)
        self.enable_check.setStyleSheet("""
            QCheckBox {
                font-size: 15px;
                font-weight: 500;
                color: #000000;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                font-size: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #E1E4E8;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2188FF;
                border-radius: 4px;
                background: #2188FF;
                color: #000000;
                image: url(qt-project.org/doc/qt-5/images/checkmark.png);
            }
        """)
        self.enable_check.stateChanged.connect(
            lambda: self.update_matcher_config(
                bot_id, plugin_name, matcher_key)
        )
        switch_layout.addWidget(self.enable_check)
        switch_layout.addStretch()
        switch_card.setLayout(switch_layout)
        layout.addWidget(switch_card)

        search_card = QFrame()
        search_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
                color: #000000;
            }
        """)
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)

        search_label = QLabel("快速筛选")
        search_label.setStyleSheet("font-size: 14px;")

        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self._perform_filtering)

        self.search_edit = StyledLineEdit()
        self.search_edit.setPlaceholderText("输入关键词过滤所有名单...")
        self.search_edit.textChanged.connect(self.on_search_text_changed)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        search_card.setLayout(search_layout)
        layout.addWidget(search_card)

        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(16)

        if self.width() < 1000:
            lists_layout.setDirection(QVBoxLayout.Direction.TopToBottom)

        white_group = StyledGroupBox("白名单")
        white_layout = QVBoxLayout()
        white_layout.setContentsMargins(12, 20, 12, 12)
        white_layout.setSpacing(16)

        white_user_group = QGroupBox("用户白名单")
        white_user_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 18px;
                font-size: 14px;
                font-weight: 500;
                color: #24292E;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        white_user_layout = QVBoxLayout()
        white_user_layout.setContentsMargins(8, 16, 8, 8)
        white_user_layout.setSpacing(8)

        self.white_user_list = SearchableListWidget()
        self.white_user_list.addItems(
            matcher_config["permission"]["white_list"]["user"])
        white_user_layout.addWidget(self.white_user_list)

        white_user_btn_layout = QHBoxLayout()
        white_user_btn_layout.setSpacing(8)

        add_white_user_btn = SecondaryButton("添加")
        add_white_user_btn.setIcon(QIcon.fromTheme("list-add"))
        add_white_user_btn.clicked.connect(
            lambda: self.add_to_list(self.white_user_list, "white_list", "user",
                                     bot_id, plugin_name, matcher_key)
        )

        remove_white_user_btn = SecondaryButton("删除")
        remove_white_user_btn.setIcon(QIcon.fromTheme("list-remove"))
        remove_white_user_btn.clicked.connect(
            lambda: self.remove_from_list(self.white_user_list, "white_list", "user",
                                          bot_id, plugin_name, matcher_key)
        )

        white_user_btn_layout.addWidget(add_white_user_btn)
        white_user_btn_layout.addWidget(remove_white_user_btn)
        white_user_layout.addLayout(white_user_btn_layout)
        white_user_group.setLayout(white_user_layout)
        white_layout.addWidget(white_user_group)

        white_group_group = QGroupBox("群组白名单")
        white_group_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 18px;
                font-size: 14px;
                font-weight: 500;
                color: #24292E;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        white_group_layout = QVBoxLayout()
        white_group_layout.setContentsMargins(8, 16, 8, 8)
        white_group_layout.setSpacing(8)

        self.white_group_list = SearchableListWidget()
        self.white_group_list.addItems(
            matcher_config["permission"]["white_list"]["group"])
        white_group_layout.addWidget(self.white_group_list)

        white_group_btn_layout = QHBoxLayout()
        white_group_btn_layout.setSpacing(8)

        add_white_group_btn = SecondaryButton("添加")
        add_white_group_btn.setIcon(QIcon.fromTheme("list-add"))
        add_white_group_btn.clicked.connect(
            lambda: self.add_to_list(self.white_group_list, "white_list", "group",
                                     bot_id, plugin_name, matcher_key)
        )

        remove_white_group_btn = SecondaryButton("删除")
        remove_white_group_btn.setIcon(QIcon.fromTheme("list-remove"))
        remove_white_group_btn.clicked.connect(
            lambda: self.remove_from_list(self.white_group_list, "white_list", "group",
                                          bot_id, plugin_name, matcher_key)
        )

        white_group_btn_layout.addWidget(add_white_group_btn)
        white_group_btn_layout.addWidget(remove_white_group_btn)
        white_group_layout.addLayout(white_group_btn_layout)
        white_group_group.setLayout(white_group_layout)
        white_layout.addWidget(white_group_group)

        white_group.setLayout(white_layout)
        lists_layout.addWidget(white_group, 1)

        ban_group = StyledGroupBox("黑名单")
        ban_layout = QVBoxLayout()
        ban_layout.setContentsMargins(12, 20, 12, 12)
        ban_layout.setSpacing(16)

        ban_user_group = QGroupBox("用户黑名单")
        ban_user_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 18px;
                font-size: 14px;
                font-weight: 500;
                color: #24292E;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        ban_user_layout = QVBoxLayout()
        ban_user_layout.setContentsMargins(8, 16, 8, 8)
        ban_user_layout.setSpacing(8)

        self.ban_user_list = SearchableListWidget()
        self.ban_user_list.addItems(
            matcher_config["permission"]["ban_list"]["user"])
        ban_user_layout.addWidget(self.ban_user_list)

        ban_user_btn_layout = QHBoxLayout()
        ban_user_btn_layout.setSpacing(8)

        add_ban_user_btn = SecondaryButton("添加")
        add_ban_user_btn.setIcon(QIcon.fromTheme("list-add"))
        add_ban_user_btn.clicked.connect(
            lambda: self.add_to_list(self.ban_user_list, "ban_list", "user",
                                     bot_id, plugin_name, matcher_key)
        )

        remove_ban_user_btn = SecondaryButton("删除")
        remove_ban_user_btn.setIcon(QIcon.fromTheme("list-remove"))
        remove_ban_user_btn.clicked.connect(
            lambda: self.remove_from_list(self.ban_user_list, "ban_list", "user",
                                          bot_id, plugin_name, matcher_key)
        )

        ban_user_btn_layout.addWidget(add_ban_user_btn)
        ban_user_btn_layout.addWidget(remove_ban_user_btn)
        ban_user_layout.addLayout(ban_user_btn_layout)
        ban_user_group.setLayout(ban_user_layout)
        ban_layout.addWidget(ban_user_group)

        ban_group_group = QGroupBox("群组黑名单")
        ban_group_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 18px;
                font-size: 14px;
                font-weight: 500;
                color: #24292E;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        ban_group_layout = QVBoxLayout()
        ban_group_layout.setContentsMargins(8, 16, 8, 8)
        ban_group_layout.setSpacing(8)

        self.ban_group_list = SearchableListWidget()
        self.ban_group_list.addItems(
            matcher_config["permission"]["ban_list"]["group"])
        ban_group_layout.addWidget(self.ban_group_list)

        ban_group_btn_layout = QHBoxLayout()
        ban_group_btn_layout.setSpacing(8)

        add_ban_group_btn = SecondaryButton("添加")
        add_ban_group_btn.setIcon(QIcon.fromTheme("list-add"))
        add_ban_group_btn.clicked.connect(
            lambda: self.add_to_list(self.ban_group_list, "ban_list", "group",
                                     bot_id, plugin_name, matcher_key)
        )

        remove_ban_group_btn = SecondaryButton("删除")
        remove_ban_group_btn.setIcon(QIcon.fromTheme("list-remove"))
        remove_ban_group_btn.clicked.connect(
            lambda: self.remove_from_list(self.ban_group_list, "ban_list", "group",
                                          bot_id, plugin_name, matcher_key)
        )

        ban_group_btn_layout.addWidget(add_ban_group_btn)
        ban_group_btn_layout.addWidget(remove_ban_group_btn)
        ban_group_layout.addLayout(ban_group_btn_layout)
        ban_group_group.setLayout(ban_group_layout)
        ban_layout.addWidget(ban_group_group)

        ban_group.setLayout(ban_layout)
        lists_layout.addWidget(ban_group, 1)

        layout.addLayout(lists_layout, 1)

    def on_search_text_changed(self):
        self.filter_timer.start(300)

    def _perform_filtering(self):
        search_text = self.search_edit.text()
        self.white_user_list.filter_items(search_text)
        self.white_group_list.filter_items(search_text)
        self.ban_user_list.filter_items(search_text)
        self.ban_group_list.filter_items(search_text)

    def update_matcher_config(self, bot_id: str, plugin_name: str, matcher_key: str):
        current_config = ReadableRoster.get_config()
        plugin_data = current_config["bots"].get(bot_id, {"plugins": {}}).get(
            "plugins", {}).get(plugin_name, {"matchers": []})

        for matcher in plugin_data["matchers"]:
            if ReadableRoster._get_rule_display_name(matcher["rule"]) == matcher_key:
                matcher["is_on"] = self.enable_check.isChecked()
                break

        ReadableRoster.update_config(current_config)

    def add_to_list(self, list_widget: SearchableListWidget, list_type: str, id_type: str,
                    bot_id: str, plugin_name: str, matcher_key: str):
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"添加{id_type}")

        layout = QVBoxLayout(dialog)

        # 添加标签
        label = QLabel(f"请输入{id_type} ID:")
        label.setStyleSheet(
            "font-size: 14px; color: #333; margin-bottom: 10px;")
        layout.addWidget(label)

        line_edit = QLineEdit()
        line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
                color: #000000;
            }
        """)
        layout.addWidget(line_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        def validate_input():
            button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
                bool(line_edit.text()))

        line_edit.textChanged.connect(validate_input)
        validate_input()

        if dialog.exec_() == QDialog.DialogCode.Accepted:
            id_value = line_edit.text()
            # 原有逻辑保持不变
            current_config = ReadableRoster.get_config()
            bot_data = current_config["bots"].setdefault(
                bot_id, {"plugins": {}})
            plugin_data = bot_data["plugins"].setdefault(
                plugin_name, {"matchers": []})

            for matcher in plugin_data["matchers"]:
                if ReadableRoster._get_rule_display_name(matcher["rule"]) == matcher_key:
                    if id_value not in matcher["permission"][list_type][id_type]:
                        matcher["permission"][list_type][id_type].append(
                            id_value)
                    break

            ReadableRoster.update_config(current_config)
            list_widget.addItem(id_value)

            if self.search_edit.text():
                list_widget.filter_items(self.search_edit.text())

    def remove_from_list(self, list_widget: SearchableListWidget, list_type: str, id_type: str,
                         bot_id: str, plugin_name: str, matcher_key: str):
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return

        current_config = ReadableRoster.get_config()
        plugin_data = current_config["bots"].get(bot_id, {"plugins": {}}).get(
            "plugins", {}).get(plugin_name, {"matchers": []})

        for item in selected_items:
            id_value = item.text()

            for matcher in plugin_data["matchers"]:
                if ReadableRoster._get_rule_display_name(matcher["rule"]) == matcher_key:
                    if id_value in matcher["permission"][list_type][id_type]:
                        matcher["permission"][list_type][id_type].remove(
                            id_value)
                    break

            list_widget.takeItem(list_widget.row(item))

        ReadableRoster.update_config(current_config)

    def save_config(self):
        talker.send_request("sync_matchers", success_signal=self.success_signal,
                            error_signal=self.error_signal, new_roster=ujson.dumps(ReadableRoster.get_config()))

    def _show_success(self, result: ResponsePayload):
        self.config_updated.emit(ReadableRoster.get_config())
        MessageBoxBuilder().hide_icon().set_title("保存成功!").set_content(
            "配置已成功保存!").set_background_color("#FFFFFF").add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.Yes,
                    text="真棒!"
                )
        ).build_and_fetch_result()

    def _show_error(self, result: ResponsePayload):
        MessageBoxBuilder().hide_icon().set_title("保存失败").set_content(
            f"配置未能成功保存\n{result.error}").set_background_color("#FFFFFF").add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.Yes,
                    text="呃呃"
                )
        ).build_and_fetch_result()

    def test_permission(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("权限测试")
        dialog.setMinimumSize(500, 400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #F6F8FA;
            }
            QLabel {
                color: #24292E;
                font-size: 14px;
            }
            QPushButton {
                min-width: 80px;
                color: #000000;
            }
            QComboBox {
                color: #000000;
            }
            QLineEdit {
                color: #000000;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title_label = QLabel("权限测试工具")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #24292E;
            padding-bottom: 8px;
        """)
        layout.addWidget(title_label)

        form_card = QFrame()
        form_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
                color: #000000;
            }
            QLabel {
                color: #000000;
            }
        """)
        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(16)

        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(12)
        bot_label = QLabel("机器人ID:")
        bot_label.setFixedWidth(80)
        bot_combo = QComboBox()
        bot_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bot_combo.setStyleSheet("color: #000000;")

        current_config = ReadableRoster.get_config()
        if self.filter_bot_id:
            bot_combo.addItem(self.filter_bot_id)
        else:
            bot_combo.addItems(list(current_config["bots"].keys()))

        bot_layout.addWidget(bot_label)
        bot_layout.addWidget(bot_combo)
        form_layout.addLayout(bot_layout)

        plugin_layout = QHBoxLayout()
        plugin_layout.setSpacing(12)
        plugin_label = QLabel("插件名称:")
        plugin_label.setFixedWidth(80)
        plugin_combo = QComboBox()
        plugin_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        plugin_combo.setStyleSheet("color: #000000;")
        plugin_layout.addWidget(plugin_label)
        plugin_layout.addWidget(plugin_combo)
        form_layout.addLayout(plugin_layout)

        matcher_layout = QHBoxLayout()
        matcher_layout.setSpacing(12)
        matcher_label = QLabel("规则:")
        matcher_label.setFixedWidth(80)
        matcher_combo = QComboBox()
        matcher_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        matcher_combo.setStyleSheet("color: #000000;")
        matcher_layout.addWidget(matcher_label)
        matcher_layout.addWidget(matcher_combo)
        form_layout.addLayout(matcher_layout)

        user_layout = QHBoxLayout()
        user_layout.setSpacing(12)
        user_label = QLabel("用户ID:")
        user_label.setFixedWidth(80)
        user_edit = QLineEdit("user1")
        user_edit.setPlaceholderText("必填")
        user_edit.setStyleSheet("color: #000000;")
        user_layout.addWidget(user_label)
        user_layout.addWidget(user_edit)
        form_layout.addLayout(user_layout)

        group_layout = QHBoxLayout()
        group_layout.setSpacing(12)
        group_label = QLabel("群组ID:")
        group_label.setFixedWidth(80)
        group_edit = QLineEdit("group1")
        group_edit.setPlaceholderText("可选")
        group_edit.setStyleSheet("color: #000000;")
        group_layout.addWidget(group_label)
        group_layout.addWidget(group_edit)
        form_layout.addLayout(group_layout)

        form_card.setLayout(form_layout)
        layout.addWidget(form_card)

        result_card = QFrame()
        result_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                padding: 16px;
                color: #000000;
            }
            QLabel {
                color: #000000;
            }
        """)
        result_layout = QVBoxLayout()
        result_layout.setContentsMargins(0, 0, 0, 0)

        self.result_label = QLabel("测试结果将显示在这里")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("""
            font-size: 15px; 
            padding: 12px;
            border-radius: 6px;
            color: #000000;
        """)
        result_layout.addWidget(self.result_label)
        result_card.setLayout(result_layout)
        layout.addWidget(result_card)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        close_btn = SecondaryButton("关闭")
        close_btn.setStyleSheet("color: #000000;")
        close_btn.clicked.connect(dialog.reject)

        test_btn = PrimaryButton("测试")
        test_btn.setStyleSheet("color: #000000;")
        test_btn.clicked.connect(lambda: self.run_test(
            bot_combo.currentText(),
            plugin_combo.currentText(),
            matcher_combo.currentText(),
            user_edit.text(),
            group_edit.text() if group_edit.text() else None
        ))

        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addWidget(test_btn)
        layout.addLayout(button_layout)

        def update_plugins():
            plugin_combo.clear()
            bot_id = bot_combo.currentText()
            if bot_id in current_config["bots"]:
                plugins = current_config["bots"][bot_id]["plugins"]
                if self.filter_plugin_name:
                    if self.filter_plugin_name in plugins:
                        plugin_combo.addItem(self.filter_plugin_name)
                else:
                    plugin_combo.addItems(list(plugins.keys()))
            update_matchers()

        def update_matchers():
            matcher_combo.clear()
            bot_id = bot_combo.currentText()
            plugin_name = plugin_combo.currentText()
            if (bot_id in current_config["bots"] and
                    plugin_name in current_config["bots"][bot_id]["plugins"]):
                matchers = current_config["bots"][bot_id]["plugins"][plugin_name]["matchers"]
                matcher_combo.addItems(
                    [ReadableRoster._get_rule_display_name(m["rule"]) for m in matchers])

        bot_combo.currentTextChanged.connect(update_plugins)
        plugin_combo.currentTextChanged.connect(update_matchers)

        update_plugins()

        dialog.setLayout(layout)
        dialog.exec()

    def run_test(self, bot_id: str, plugin_name: str, matcher_key: str, userid: str, groupid: Optional[str]):
        if not all([bot_id, plugin_name, matcher_key, userid]):
            self.result_label.setText("请填写所有必填字段!")
            self.result_label.setStyleSheet("""
                color: #D1242F;
                font-weight: 500;
                background-color: #FFEBE9;
                border: 1px solid #FFD8D3;
            """)
            return

        is_allowed = ReadableRoster.check(
            bot_id, plugin_name, matcher_key, userid, groupid)

        if is_allowed:
            self.result_label.setText("✅ 权限检查: 允许访问")
            self.result_label.setStyleSheet("""
                color: #2DA44E;
                font-weight: 500;
                background-color: #E6F7ED;
                border: 1px solid #C8E6D9;
            """)
        else:
            self.result_label.setText("❌ 权限检查: 禁止访问")
            self.result_label.setStyleSheet("""
                color: #D1242F;
                font-weight: 500;
                background-color: #FFEBE9;
                border: 1px solid #FFD8D3;
            """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.width()
        if width < 1000:
            self.splitter.setSizes([200, width - 220])
        elif width < 1400:
            self.splitter.setSizes([280, width - 300])
        else:
            self.splitter.setSizes([350, width - 370])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    example_config: FullConfigModel = {
        "bots": {
            "bot_123": {
                "plugins": {
                    "admin": {
                        "matchers": [
                            {
                                "rule": {
                                    "commands": ["1", "2"],
                                    "regex_patterns": [],
                                    "keywords": [],
                                    "startswith": [],
                                    "endswith": [],
                                    "fullmatch": [],
                                    "event_types": ["55"],
                                    "to_me": False
                                },
                                "permission": {
                                    "white_list": {
                                        "user": ["user1", "user2"],
                                        "group": ["group1"]
                                    },
                                    "ban_list": {
                                        "user": ["user3"],
                                        "group": ["group2"]
                                    }
                                },
                                "is_on": True
                            },
                            {
                                "rule": {
                                    "commands": [],
                                    "regex_patterns": ["^test.*"],
                                    "keywords": [],
                                    "startswith": [],
                                    "endswith": [],
                                    "fullmatch": [],
                                    "event_types": [],
                                    "to_me": True
                                },
                                "permission": {
                                    "white_list": {
                                        "user": ["user4"],
                                        "group": []
                                    },
                                    "ban_list": {
                                        "user": [],
                                        "group": ["group3"]
                                    }
                                },
                                "is_on": True
                            }
                        ]
                    }
                }
            }
        }
    }

    window = PermissionConfigurator(
        initial_config=example_config,
        # bot_id="bot_123",
        # plugin_name="admin"
    )
    window.show()
    sys.exit(app.exec())
