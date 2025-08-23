from typing import Dict, Optional, Tuple, Any

import orjson
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget,
    QTreeWidgetItem, QGroupBox, QCheckBox, QListWidget,
    QLabel, QFrame, QScrollArea, QGridLayout, QStackedWidget, QComboBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QPixmap

from ...Qcomponents.MessageBox import MessageBoxBuilder, MessageBoxConfig, ButtonConfig
from ...client import talker, ResponsePayload
from .model import FullConfigModel, MatcherRuleModel, ReadableRoster
from .things import Style, StyledButton, StyledLineEdit


class PermissionConfigurator(QWidget):
    """权限配置器主窗口"""
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
        self.setStyleSheet(Style.get_main_style())

        self.filter_bot_id = bot_id
        self.filter_plugin_name = plugin_name

        self.panel_cache: Dict[Tuple, QWidget] = {}
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_filtering)

        self._connect_signals()
        self._init_ui()
        self.update_config(initial_config)

    def _connect_signals(self) -> None:
        self.success_signal.connect(self._on_save_success)
        self.error_signal.connect(self._on_save_error)

    def update_config(self, config: FullConfigModel) -> None:
        try:
            for bot_data in config.get("bots", {}).values():
                for plugin_data in bot_data.get("plugins", {}).values():
                    if "matchers" in plugin_data and plugin_data["matchers"]:
                        plugin_data["matchers"].sort(
                            key=lambda m: ReadableRoster._get_rule_display_name(
                                m.get("rule", {}))
                        )

            ReadableRoster.update_config(config)
            self._build_config_tree()
            self.panel_cache.clear()
            self._clear_right_panel()
            self._show_placeholder_panel()
        except Exception as e:
            MessageBoxBuilder().set_title("配置错误").set_content(
                f"无法解析配置数据: {e}"
            ).add_button(ButtonConfig(
                btn_type=MessageBoxConfig.ButtonType.OK, text="好的"
            )).build_and_fetch_result()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet(
            "QSplitter::handle { background-color: #D0D7DE; }")

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)

        main_layout.addWidget(self.splitter)
        main_layout.addLayout(self._create_bottom_bar())

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)
        self.config_tree = QTreeWidget()
        self.config_tree.setHeaderHidden(True)
        self.config_tree.setStyleSheet(Style.TREE_WIDGET_STYLE)
        self.config_tree.itemSelectionChanged.connect(self._on_item_selected)
        layout.addWidget(self.config_tree)
        return panel

    def _create_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setStyleSheet(
            f"background-color: {Style.PANEL_BACKGROUND}; border-radius: 8px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)
        return panel

    def _create_bottom_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addStretch()
        self.save_button = StyledButton("保存配置", "primary")
        self.save_button.clicked.connect(self.save_config)
        self.test_button = StyledButton("测试权限")
        self.test_button.clicked.connect(self.test_permission)
        layout.addWidget(self.test_button)
        layout.addWidget(self.save_button)
        return layout

    def _build_config_tree(self) -> None:
        self.config_tree.clear()
        current_config = ReadableRoster.get_config()
        bots_to_display = [self.filter_bot_id] if self.filter_bot_id else sorted(
            current_config["bots"].keys())

        for bot_id in bots_to_display:
            bot_data = current_config["bots"].get(bot_id)
            if not bot_data or not bot_data.get("plugins"):
                continue

            bot_item = QTreeWidgetItem(self.config_tree, [bot_id])
            bot_item.setData(0, Qt.ItemDataRole.UserRole, ("bot", bot_id))
            bot_item.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Bold))
            bot_item.setIcon(0, QIcon.fromTheme("computer"))

            plugins_to_display = [self.filter_plugin_name] if self.filter_plugin_name else sorted(
                bot_data["plugins"].keys())

            for plugin_name in plugins_to_display:
                plugin_data = bot_data["plugins"].get(plugin_name)
                if not plugin_data or not plugin_data.get("matchers"):
                    continue

                plugin_item = QTreeWidgetItem(bot_item, [plugin_name])
                plugin_item.setData(0, Qt.ItemDataRole.UserRole,
                                    ("plugin", bot_id, plugin_name))
                plugin_item.setFont(
                    0, QFont("Segoe UI", 10, QFont.Weight.DemiBold))
                plugin_item.setIcon(0, QIcon.fromTheme("extension"))

                for matcher_idx, matcher in enumerate(plugin_data["matchers"]):
                    matcher_key = ReadableRoster._get_rule_display_name(
                        matcher["rule"])
                    matcher_item = QTreeWidgetItem(plugin_item, [matcher_key])
                    matcher_item.setData(
                        0, Qt.ItemDataRole.UserRole, ("matcher", bot_id, plugin_name, matcher_idx))
                    is_on = matcher.get("is_on", True)
                    icon_color = Style.SUCCESS_COLOR if is_on else Style.DANGER_COLOR
                    pixmap = QPixmap(16, 16)
                    pixmap.fill(QColor(icon_color))
                    matcher_item.setIcon(0, QIcon(pixmap))

        self.config_tree.expandAll()

    def _on_item_selected(self) -> None:
        selected_items = self.config_tree.selectedItems()
        if not selected_items:
            self._show_placeholder_panel()
            return

        item_data = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        item_key = tuple(item_data)

        if item_key in self.panel_cache:
            self.stacked_widget.setCurrentWidget(self.panel_cache[item_key])
        else:
            panel = self._create_panel_for_item(item_data)
            self.panel_cache[item_key] = panel
            self.stacked_widget.addWidget(panel)
            self.stacked_widget.setCurrentWidget(panel)

    def _create_panel_for_item(self, item_data: Tuple) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(Style.SCROLL_AREA_STYLE)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        item_type = item_data[0]
        if item_type == "matcher":
            self._populate_matcher_panel(layout, *item_data[1:])
        elif item_type == "plugin":
            self._populate_generic_panel(
                layout, f"插件: {item_data[2]}", f"所属机器人: {item_data[1]}")
        else:  # bot
            self._populate_generic_panel(
                layout, f"机器人: {item_data[1]}", "从左侧选择一个插件或规则进行详细配置。")

        layout.addStretch(1)
        scroll_area.setWidget(content_widget)
        return scroll_area

    def _clear_right_panel(self) -> None:
        for widget in self.panel_cache.values():
            widget.deleteLater()
        self.panel_cache.clear()

        while self.stacked_widget.count() > 0:
            self.stacked_widget.widget(0).deleteLater()
            self.stacked_widget.removeWidget(self.stacked_widget.widget(0))

    def _show_placeholder_panel(self) -> None:
        placeholder_key = ("placeholder",)
        if placeholder_key not in self.panel_cache:
            placeholder = QWidget()
            layout = QVBoxLayout(placeholder)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel("← 请从左侧选择一个项目进行配置")
            label.setStyleSheet(
                f"font-size: 16px; color: {Style.TEXT_COLOR_SECONDARY};")
            layout.addWidget(label)
            self.panel_cache[placeholder_key] = placeholder
            self.stacked_widget.addWidget(placeholder)
        self.stacked_widget.setCurrentWidget(self.panel_cache[placeholder_key])

    def _populate_matcher_panel(self, layout: QVBoxLayout, bot_id: str, plugin_name: str, matcher_idx: int) -> None:
        try:
            matcher_config = ReadableRoster.config["bots"][bot_id]["plugins"][plugin_name]["matchers"][matcher_idx]
        except (KeyError, IndexError):
            layout.addWidget(QLabel("错误：找不到对应的规则配置。"))
            return

        is_on = matcher_config.get("is_on", True)
        self.enable_check = QCheckBox("启用此规则")
        self.enable_check.setStyleSheet(f"""
            QCheckBox {{
                spacing: 8px; 
                color: {Style.TEXT_COLOR_PRIMARY};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {Style.BORDER_COLOR};
                background-color: {Style.PANEL_BACKGROUND};
            }}
            QCheckBox::indicator:hover {{
                border-color: #88929D;
            }}
            QCheckBox::indicator:checked {{
                background-color: {Style.ACCENT_COLOR};
                border-color: {Style.ACCENT_COLOR};
                image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M4 8l3 3 6-6"/></svg>');
            }}
        """)
        self.enable_check.setChecked(is_on)
        self.enable_check.stateChanged.connect(lambda: self._update_matcher_status(
            bot_id, plugin_name, matcher_idx, self.enable_check.isChecked()))
        layout.addWidget(self.enable_check)

        rule_group = QGroupBox("规则详情")
        rule_group.setStyleSheet(Style.GROUP_BOX_STYLE)
        rule_group.setLayout(
            self._create_rule_detail_layout(matcher_config["rule"]))
        layout.addWidget(rule_group)

        self.search_edit = StyledLineEdit()
        self.search_edit.setPlaceholderText("过滤下方用户/群组名单...")
        self.search_edit.textChanged.connect(
            lambda: self.search_timer.start(300))
        layout.addWidget(self.search_edit)

        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(20)
        self.white_list_group = self._create_permission_group(
            "白名单", matcher_config, "white_list", bot_id, plugin_name, matcher_idx)
        self.ban_list_group = self._create_permission_group(
            "黑名单", matcher_config, "ban_list", bot_id, plugin_name, matcher_idx)
        lists_layout.addWidget(self.white_list_group)
        lists_layout.addWidget(self.ban_list_group)
        layout.addLayout(lists_layout)

    def _create_rule_detail_layout(self, rule_data: Dict[str, Any]) -> QGridLayout:
        layout = QGridLayout()
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(15)
        layout.setColumnStretch(1, 1)
        row = 0
        details = {
            "Alconna 命令": ", ".join(rule_data.get("alconna_commands", [])),
            "命令": ", ".join("/".join(cmd) for cmd in rule_data.get("commands", [])),
            "正则表达式": "\n".join(rule_data.get("regex_patterns", [])),
            "关键词": ", ".join(rule_data.get("keywords", [])),
            "开头匹配": ", ".join(rule_data.get("startswith", [])),
            "结尾匹配": ", ".join(rule_data.get("endswith", [])),
            "完全匹配": ", ".join(rule_data.get("fullmatch", [])),
            "事件类型": ", ".join(rule_data.get("event_types", [])),
            "触发方式": "需要@机器人" if rule_data.get("to_me") else ""
        }
        for title, content in details.items():
            if content:
                title_label = QLabel(f"{title}:")
                title_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                content_label = QLabel(content)
                content_label.setWordWrap(True)
                layout.addWidget(title_label, row, 0)
                layout.addWidget(content_label, row, 1)
                row += 1
        if row == 0:
            layout.addWidget(QLabel("此规则无任何匹配条件。"), 0, 0, 1, 2)
        return layout

    def _create_permission_group(self, title: str, matcher_config: MatcherRuleModel, list_type: str, bot_id: str, plugin_name: str, matcher_idx: int) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(Style.GROUP_BOX_STYLE)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        user_list = QListWidget()
        user_list.setStyleSheet(Style.LIST_WIDGET_STYLE)
        user_list.addItems(matcher_config["permission"][list_type]["user"])
        layout.addWidget(QLabel("用户名单"))
        layout.addWidget(user_list)
        layout.addLayout(self._create_list_buttons(
            user_list, list_type, "user", bot_id, plugin_name, matcher_idx))

        group_list = QListWidget()
        group_list.setStyleSheet(Style.LIST_WIDGET_STYLE)
        group_list.addItems(matcher_config["permission"][list_type]["group"])
        layout.addWidget(QLabel("群组名单"))
        layout.addWidget(group_list)
        layout.addLayout(self._create_list_buttons(
            group_list, list_type, "group", bot_id, plugin_name, matcher_idx))

        group.setProperty("user_list", user_list)
        group.setProperty("group_list", group_list)
        return group

    def _create_list_buttons(self, list_widget: QListWidget, list_type: str, id_type: str, bot_id: str, plugin_name: str, matcher_idx: int) -> QHBoxLayout:
        layout = QHBoxLayout()
        add_btn = StyledButton("添加")
        add_btn.clicked.connect(lambda: self._add_to_list(
            list_widget, list_type, id_type, bot_id, plugin_name, matcher_idx))
        remove_btn = StyledButton("删除")
        remove_btn.clicked.connect(lambda: self._remove_from_list(
            list_widget, list_type, id_type, bot_id, plugin_name, matcher_idx))
        layout.addStretch()
        layout.addWidget(add_btn)
        layout.addWidget(remove_btn)
        return layout

    def _populate_generic_panel(self, layout: QVBoxLayout, title: str, subtitle: str):
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(
            f"font-size: 14px; color: {Style.TEXT_COLOR_SECONDARY};")
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

    def _update_matcher_status(self, bot_id: str, plugin_name: str, matcher_idx: int, is_on: bool):
        config = ReadableRoster.get_config()
        try:
            config["bots"][bot_id]["plugins"][plugin_name]["matchers"][matcher_idx]["is_on"] = is_on
            ReadableRoster.update_config(config)

            selected_item = self.config_tree.selectedItems()[0]
            icon_color = Style.SUCCESS_COLOR if is_on else Style.DANGER_COLOR
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(icon_color))
            selected_item.setIcon(0, QIcon(pixmap))
        except (KeyError, IndexError, AttributeError):
            pass

    def _perform_filtering(self) -> None:
        text = self.search_edit.text()
        self._filter_list(self.white_list_group.property("user_list"), text)
        self._filter_list(self.white_list_group.property("group_list"), text)
        self._filter_list(self.ban_list_group.property("user_list"), text)
        self._filter_list(self.ban_list_group.property("group_list"), text)

    def _filter_list(self, list_widget: Optional[QListWidget], text: str):
        if not list_widget:
            return
        text_lower = text.lower()
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            item.setHidden(text_lower not in item.text().lower())

    def _add_to_list(self, list_widget: QListWidget, list_type: str, id_type: str, bot_id: str, plugin_name: str, matcher_idx: int):
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        dialog_label = QLabel(f"请输入要添加的 {id_type} ID:")
        dialog_label.setStyleSheet(f"color: {Style.TEXT_COLOR_PRIMARY};")
        input_field = StyledLineEdit()
        input_field.setPlaceholderText(f"例如: 123456789")

        error_label = QLabel()
        error_label.setStyleSheet(
            f"color: {Style.DANGER_COLOR}; padding-top: 4px;")
        error_label.setWordWrap(True)
        error_label.hide()

        input_field.textChanged.connect(error_label.hide)

        input_layout.addWidget(dialog_label)
        input_layout.addWidget(input_field)
        input_layout.addWidget(error_label)

        builder = (
            MessageBoxBuilder()
            .set_title(f"添加 {id_type.capitalize()}")
            .add_custom_widget(input_container)
            .add_button(ButtonConfig(
                btn_type=MessageBoxConfig.ButtonType.Custom,
                text="确认",
                custom_id="ok_confirm",
                role="primary",
                closes_dialog=False
            ))
            .add_button(ButtonConfig(
                btn_type=MessageBoxConfig.ButtonType.Cancel, text="取消"
            ))
            .hide_icon()
        )

        dialog = builder.build()

        def handle_add_action(button_id: Any):
            if button_id != "ok_confirm":
                return

            new_id = input_field.text().strip()

            if not new_id:
                error_label.setText("ID 不能为空，请重新输入。")
                error_label.show()
                return

            config = ReadableRoster.get_config()
            try:
                permission_list = config["bots"][bot_id]["plugins"][plugin_name][
                    "matchers"][matcher_idx]["permission"][list_type][id_type]

                if new_id in permission_list:
                    error_label.setText(f"ID '{new_id}' 已存在于列表中。")
                    error_label.show()
                    return

                error_label.hide()

                permission_list.append(new_id)
                ReadableRoster.update_config(config)
                list_widget.addItem(new_id)
                list_widget.scrollToBottom()

                dialog.accept()

            except (KeyError, IndexError) as e:
                MessageBoxBuilder().set_title("内部错误").set_content(
                    f"更新配置时发生错误: {e}"
                ).add_button(ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.OK, text="好的"
                )).build_and_fetch_result()
                dialog.reject()

        dialog.buttonClicked.connect(handle_add_action)
        dialog.exec()

    def _remove_from_list(self, list_widget: QListWidget, list_type: str, id_type: str, bot_id: str, plugin_name: str, matcher_idx: int):
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return

        id_to_remove = selected_items[0].text()
        config = ReadableRoster.get_config()
        try:
            permission_list = config["bots"][bot_id]["plugins"][plugin_name][
                "matchers"][matcher_idx]["permission"][list_type][id_type]
            if id_to_remove in permission_list:
                permission_list.remove(id_to_remove)
                ReadableRoster.update_config(config)
                list_widget.takeItem(list_widget.row(selected_items[0]))
        except (KeyError, IndexError, ValueError):
            pass

    def save_config(self) -> None:
        talker.send_request("sync_matchers", success_signal=self.success_signal,
                            error_signal=self.error_signal, new_roster=orjson.dumps(ReadableRoster.get_config()))

    def _on_save_success(self, result: ResponsePayload) -> None:
        self.config_updated.emit(ReadableRoster.get_config())
        MessageBoxBuilder().set_title("保存成功").set_content("配置已成功保存！").add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.OK, text="好的")).build_and_fetch_result()

    def _on_save_error(self, result: ResponsePayload) -> None:
        MessageBoxBuilder().set_title("保存失败").set_content(
            f"未能保存配置：\n{result.error}"
        ).add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.OK, text="好的"
        )).build_and_fetch_result()

    def test_permission(self) -> None:
        dialog_container = QWidget()
        layout = QVBoxLayout(dialog_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        current_config = ReadableRoster.get_config()
        bot_combo = QComboBox()
        plugin_combo = QComboBox()
        matcher_combo = QComboBox()
        user_edit = StyledLineEdit()
        user_edit.setPlaceholderText("必填")
        group_edit = StyledLineEdit()
        group_edit.setPlaceholderText("选填, 私聊请留空")

        form_layout = QGridLayout()
        form_layout.setSpacing(10)
        form_layout.addWidget(QLabel("机器人:"), 0, 0)
        form_layout.addWidget(bot_combo, 0, 1)
        form_layout.addWidget(QLabel("插件:"), 1, 0)
        form_layout.addWidget(plugin_combo, 1, 1)
        form_layout.addWidget(QLabel("规则:"), 2, 0)
        form_layout.addWidget(matcher_combo, 2, 1)
        form_layout.addWidget(QLabel("用户ID:"), 3, 0)
        form_layout.addWidget(user_edit, 3, 1)
        form_layout.addWidget(QLabel("群组ID:"), 4, 0)
        form_layout.addWidget(group_edit, 4, 1)
        layout.addLayout(form_layout)

        result_label = QLabel("输入参数并点击测试")
        result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_label.setStyleSheet(
            f"padding: 10px; border-radius: 6px; background-color: #f1f1f1;")
        layout.addWidget(result_label)

        def update_plugins():
            plugin_combo.clear()
            bot_id = bot_combo.currentText()
            if bot_id in current_config["bots"]:
                plugins = current_config["bots"][bot_id]["plugins"]
                plugin_combo.addItems(sorted(plugins.keys()))
            update_matchers()

        def update_matchers():
            matcher_combo.clear()
            bot_id = bot_combo.currentText()
            plugin_name = plugin_combo.currentText()
            if bot_id in current_config["bots"] and plugin_name in current_config["bots"][bot_id]["plugins"]:
                matchers = current_config["bots"][bot_id]["plugins"][plugin_name]["matchers"]
                matcher_combo.addItems(
                    [ReadableRoster._get_rule_display_name(m["rule"]) for m in matchers])

        bot_combo.currentTextChanged.connect(update_plugins)
        plugin_combo.currentTextChanged.connect(update_matchers)
        if current_config["bots"]:
            bot_combo.addItems(sorted(current_config["bots"].keys()))

        def run_test():
            bot_id = bot_combo.currentText()
            plugin_name = plugin_combo.currentText()
            matcher_key = matcher_combo.currentText()
            userid = user_edit.text().strip()
            groupid = group_edit.text().strip() or None

            if not all([bot_id, plugin_name, matcher_key, userid]):
                result_label.setText("错误: 请确保所有必填项已选择/填写。")
                result_label.setStyleSheet(
                    f"color: white; background-color: {Style.DANGER_COLOR}; padding: 10px; border-radius: 6px;")
                return

            is_allowed = ReadableRoster.check(
                bot_id, plugin_name, matcher_key, userid, groupid)
            if is_allowed:
                result_label.setText("✅  权限检查通过: 允许访问")
                result_label.setStyleSheet(
                    f"color: white; background-color: {Style.SUCCESS_COLOR}; padding: 10px; border-radius: 6px;")
            else:
                result_label.setText("❌  权限检查不通过: 禁止访问")
                result_label.setStyleSheet(
                    f"color: white; background-color: {Style.DANGER_COLOR}; padding: 10px; border-radius: 6px;")

        def handle_dialog_clicks(result: Any):
            if result == "run_test":
                run_test()

        builder = (
            MessageBoxBuilder()
            .set_title("权限测试工具")
            .hide_icon()
            .add_custom_widget(dialog_container)
            .add_button(ButtonConfig(
                btn_type=MessageBoxConfig.ButtonType.Custom,
                text="关闭",
                custom_id="close",
                closes_dialog=True
            ))
            .add_button(ButtonConfig(
                btn_type=MessageBoxConfig.ButtonType.Custom,
                text="执行测试",
                custom_id="run_test",
                closes_dialog=False,
                role="primary"
            ))
        )

        dialog = builder.build()
        dialog.buttonClicked.connect(handle_dialog_clicks)
        dialog.exec()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        total_width = self.splitter.width()
        left_width = min(400, max(250, int(total_width * 0.3)))
        self.splitter.setSizes([left_width, total_width - left_width])
