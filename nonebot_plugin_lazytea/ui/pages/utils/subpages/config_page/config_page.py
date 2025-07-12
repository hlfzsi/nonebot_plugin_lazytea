import math
import inspect
from typing import (Any, Callable, Optional, Tuple, Type, TypedDict,
                    Union, Literal, get_origin, get_args, List, Dict)
from enum import Enum
from pydantic import BaseModel, Field, create_model, ValidationError
from pydantic.fields import FieldInfo
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QGroupBox, QStackedWidget,
    QPushButton, QSizePolicy, QScrollArea, QSizePolicy,
    QButtonGroup, QRadioButton, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal

from .beautify import StyleManager
from ...Qcomponents.MessageBox import MessageBoxBuilder, MessageBoxConfig, ButtonConfig
from ...Qcomponents.nonwheel import NoWheelSpinBox, NoWheelDoubleSpinBox, NoWheelComboBox
from ...client import talker, ResponsePayload


class WidgetInfo(TypedDict):
    widget: QWidget
    getter: Callable[[], Any]
    setter: Callable[[Any], None]
    error: QLabel
    field_info: FieldInfo


TYPE_NAME_MAP = {
    int: "整数(int)",
    str: "字符串(str)",
    float: "小数(float)",
    bool: "布尔值(bool)",
    type(None): "空值(None)",
    list: "列表(list)",
    dict: "字典(dict)",
    List[int]: "整数列表(List[int])",
    List[str]: "字符串列表(List[str])",
}


def _get_friendly_name(t: Type) -> str:
    """获取友好类型名称"""
    if get_origin(t) is Literal:
        allowed = get_args(t)
        return f"选项值（{'/'.join(map(str, allowed))}）"

    origin = get_origin(t)
    if origin is list:
        item_type = get_args(t)[0]
        return TYPE_NAME_MAP.get(t, f"{_get_friendly_name(item_type)}列表")

    if inspect.isclass(t) and issubclass(t, Enum):
        return f"枚举（{t.__name__}）"

    return TYPE_NAME_MAP.get(t, t.__name__)


class WidgetFactory:
    """控件创建工厂，统一管理各类控件的生成逻辑"""

    @staticmethod
    def create_widget(field_info: Union[FieldInfo, Any], default: Any = None) -> Tuple[QWidget, Callable, Callable]:
        annotation = field_info.annotation
        origin = get_origin(annotation)

        if origin is Union:
            return UnionWidget.create(field_info, default)

        if origin is Literal:
            return WidgetFactory.create_literal_widget(annotation, default)

        if inspect.isclass(annotation) and issubclass(annotation, Enum):
            return WidgetFactory.create_enum_widget(annotation, default)

        return WidgetFactory.create_basic_widget(annotation, default)

    @staticmethod
    def create_basic_widget(field_type: Optional[Type], default: Any) -> Tuple[QWidget, Callable, Callable]:
        """创建基础类型控件"""
        if field_type is None:
            raise ValueError("Field type cannot be None")

        if field_type is type(None):
            widget = QLabel("不可编辑 (None)")
            StyleManager.apply_style(widget)
            return widget, lambda: None, lambda v: None

        if field_type is int:
            widget = NoWheelSpinBox()
            widget.setRange(-2147483648, 2147483647)
            try:
                default = int(default) if default is not None else 0
            except (TypeError, ValueError):
                default = 0
            widget.setValue(default)
            StyleManager.apply_style(widget)
            return widget, widget.value, widget.setValue

        if field_type is float:
            widget = NoWheelDoubleSpinBox()
            widget.setRange(-math.inf, math.inf)
            widget.setDecimals(2)
            widget.setValue(default or 0.0)
            StyleManager.apply_style(widget)
            return widget, widget.value, widget.setValue

        if field_type is bool:
            return WidgetFactory.create_checkbox_widget(default or False)

        widget = QLineEdit(str(default) if default is not None else "")
        StyleManager.apply_style(widget)
        return widget, lambda: widget.text().strip(), lambda v: widget.setText(str(v))

    @staticmethod
    def create_checkbox_widget(default: bool = False) -> Tuple[QWidget, Callable[[], bool], Callable[[bool], None]]:
        """
        创建带有状态标签的复选框控件

        参数:
            default: 默认选中状态

        返回:
            Tuple[容器控件, 取值函数, 设值函数]
        """
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Preferred)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        checkbox = QCheckBox()
        checkbox.setChecked(default)
        StyleManager.apply_style(checkbox)

        status_label = QLabel("已启用" if default else "已禁用")
        status_label.setProperty("class", "checkbox-status")
        status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # 确保标签有最小宽度
        status_label.setMinimumWidth(80)
        StyleManager.apply_style(status_label)

        def update_label(state: int) -> None:
            text = ""
            if default and state:
                text = "已启用"
            elif default and not state:
                text = "准备废弃"
            elif not default and not state:
                text = "已禁用"
            elif not default and state:
                text = "就绪"
            status_label.setText(text)

        checkbox.stateChanged.connect(update_label)

        layout.addWidget(checkbox)
        layout.addWidget(status_label)
        layout.addStretch()

        container.setStyleSheet("""
            QWidget {
                background-color: white;
            }
            QLabel.checkbox-status {
                color: #495057;
                background-color: transparent;
            }
        """)

        return container, checkbox.isChecked, checkbox.setChecked

    @staticmethod
    def create_enum_widget(enum_type: Type[Enum], default: Any) -> Tuple[NoWheelComboBox, Callable, Callable]:
        """创建枚举类型控件"""
        combo = NoWheelComboBox()
        items = [e.value for e in enum_type]
        combo.addItems(items)
        if default is not None:
            combo.setCurrentText(str(default))
        StyleManager.apply_style(combo)
        return combo, lambda: enum_type(combo.currentText()), lambda v: combo.setCurrentText(v.value)

    @staticmethod
    def create_literal_widget(literal_type: Any, default: Any) -> Tuple[QWidget, Callable, Callable]:
        """创建Literal类型控件"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        allowed = get_args(literal_type)
        # 处理单选项情况
        if len(allowed) == 1:
            container = QWidget()
            layout = QHBoxLayout(container)
            value = allowed[0]
            label = QLabel(f"固定值：{value}（{_get_friendly_name(type(value))}）")
            label.setProperty("class", "literal-single")
            layout.addWidget(label)
            layout.addStretch()
            StyleManager.apply_style(container)
            return container, lambda: value, lambda v: None

        button_group = QButtonGroup(container)
        buttons = []

        type_hint = QLabel(f"允许的值       |       类型")
        type_hint.setProperty("class", "type-hint")
        StyleManager.apply_style(type_hint)
        layout.addWidget(type_hint)

        for value in allowed:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(15, 0, 0, 0)

            btn = QRadioButton(str(value))
            btn.setProperty("literal_value", value)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred,
                              QSizePolicy.Policy.Preferred)
            StyleManager.apply_style(btn)

            type_label = QLabel(f"{_get_friendly_name(type(value))}")
            type_label.setProperty("class", "type-label")
            type_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            StyleManager.apply_style(type_label)

            if value == default:
                btn.setChecked(True)

            row_layout.addWidget(btn)
            row_layout.addWidget(type_label)
            row_layout.addStretch()

            layout.addWidget(row)
            button_group.addButton(btn)
            buttons.append(btn)

        layout.addStretch()

        def getter():
            for btn in buttons:
                if btn.isChecked():
                    return btn.property("literal_value")
            return None

        def setter(val):
            for btn in buttons:
                if btn.property("literal_value") == val:
                    btn.setChecked(True)
                    break

        return container, getter, setter

    @staticmethod
    def _create_list_element(element_type: Type, default: Any) -> Tuple[QWidget, Callable, Callable]:
        """创建列表元素控件"""
        class TempField:
            def __init__(self):
                self.annotation = element_type
                self.default = default
        return WidgetFactory.create_widget(TempField(), default)


class UnionWidget:
    """联合类型控件处理"""

    @staticmethod
    def create(field_info: FieldInfo, default: Any) -> Tuple[QWidget, Callable, Callable]:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        combo = NoWheelComboBox()
        stacked = QStackedWidget()
        type_options = [t for t in get_args(field_info.annotation)]

        widgets = []

        for t in type_options:
            type_name = _get_friendly_name(t)
            combo.addItem(type_name)

            class TempField:
                def __init__(self):
                    self.annotation = t
                    self.default = getattr(field_info, 'default', None)
            temp_field = TempField()

            widget, getter, setter = WidgetFactory.create_widget(
                temp_field, default)
            stacked.addWidget(widget)
            widgets.append((getter, setter))

        combo.currentIndexChanged.connect(stacked.setCurrentIndex)
        StyleManager.apply_style(combo)

        def setter(value):
            for i, t in enumerate(type_options):
                try:
                    if value is None and t is type(None):
                        combo.setCurrentIndex(i)
                        break
                    if get_origin(t) is Literal:
                        allowed = get_args(t)
                        if value in allowed:
                            combo.setCurrentIndex(i)
                            widgets[i][1](value)
                            break
                    elif inspect.isclass(t) and issubclass(t, Enum) and isinstance(value, t):
                        combo.setCurrentIndex(i)
                        widgets[i][1](value)
                        break
                    elif isinstance(value, t):
                        combo.setCurrentIndex(i)
                        widgets[i][1](value)
                        break
                except TypeError:
                    continue

        if default is not None:
            setter(default)

        layout.addWidget(combo)
        layout.addWidget(stacked)
        return container, lambda: widgets[stacked.currentIndex()][0](), setter


class ListManager:
    """列表控件管理（重构版，复用控件工厂）"""

    def __init__(self, parent: "ConfigEditor", field_name: str, field_info: FieldInfo):
        self.parent = parent
        self.field_name = field_name
        self.field_info = field_info
        self.entries = []
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 获取列表元素的类型注解
        self.element_type = get_args(field_info.annotation)[0]
        self.defaults = self.parent.initial_data.get(field_name, [])

    def create_widget(self) -> Tuple[QWidget, Callable, Callable]:
        """创建列表管理控件"""
        container = QWidget()
        container.setLayout(self.layout)

        # 添加初始条目
        for value in self.defaults:
            self._add_entry(value)

        # 添加条目按钮
        add_btn = QPushButton("+ 添加条目")
        add_btn.setProperty("class", "add-button")
        StyleManager.apply_style(add_btn)
        add_btn.clicked.connect(lambda: self._add_entry())
        self.layout.addWidget(add_btn)

        return container, self.get_values, self.set_values

    def _add_entry(self, value: Any = None) -> None:
        """添加独立布局的列表条目"""
        # 创建条目容器
        entry_widget = QGroupBox(f"条目 {len(self.entries)+1}")

        entry_layout = QVBoxLayout(entry_widget)
        entry_layout.setContentsMargins(12, 8, 12, 8)
        entry_layout.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        field = FieldInfo(annotation=self.element_type)
        widget, getter, setter = WidgetFactory.create_widget(field, value)

        # 错误提示标签
        error_label = QLabel()
        error_label.setProperty("class", "error-label")
        error_label.setWordWrap(True)

        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.setProperty("class", "danger")
        del_btn.setFixedSize(60, 24)

        # 布局组合
        content_layout.addWidget(widget)
        content_layout.addWidget(error_label)

        # 操作栏布局
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        bottom_layout.addStretch()
        bottom_layout.addWidget(del_btn)

        entry_layout.addWidget(content_widget)
        entry_layout.addWidget(bottom_bar)

        # 绑定事件
        del_btn.clicked.connect(lambda: self._remove_entry(entry_widget))
        self._bind_validation(widget, getter, error_label)

        # 存储条目信息
        self.entries.append({
            "widget": entry_widget,
            "getter": getter,
            "error": error_label,
            "valid": True
        })
        self.layout.insertWidget(len(self.entries)-1, entry_widget)

    def _bind_validation(self, widget: QWidget, getter: Callable, error_label: QLabel):
        """绑定输入验证逻辑"""
        def validate():
            try:
                value = getter()
                self.parent._validate_element(value, self.field_name)
                error_label.setVisible(False)
            except ValidationError as e:
                error_label.setText(
                    self.parent._translate_error(e.errors()[0]))
                error_label.setVisible(True)

        # 根据控件类型绑定事件
        if hasattr(widget, "valueChanged"):
            widget.valueChanged.connect(validate)  # type: ignore
        elif hasattr(widget, "textChanged"):
            widget.textChanged.connect(validate)  # type: ignore
        elif isinstance(widget, (QCheckBox, QComboBox)):
            widget.currentIndexChanged.connect(validate)  # type: ignore

    def _remove_entry(self, widget: QWidget) -> None:
        """移除指定条目"""
        for i, entry in enumerate(self.entries):
            if entry["widget"] is widget:
                self.layout.removeWidget(widget)
                widget.deleteLater()
                self.entries.pop(i)
                self._refresh_entry_numbers()
                break

    def _refresh_entry_numbers(self):
        """刷新条目编号"""
        for idx, entry in enumerate(self.entries):
            entry["widget"].setTitle(f"条目 {idx+1}")

    def get_values(self) -> list:
        """获取所有有效值"""
        return [entry["getter"]() for entry in self.entries if entry["valid"]]

    def set_values(self, values: list) -> None:
        """批量设置值"""
        while self.entries:
            self._remove_entry(self.entries[0]["widget"])
        for v in values:
            self._add_entry(v)


class ConfigEditor(QWidget):
    """配置编辑器主界面"""
    success_signal = Signal(ResponsePayload)
    error_signal = Signal(ResponsePayload)

    def __init__(self, schema: Dict, data_model_dump: Dict, moudle_name: str):
        super().__init__()
        self.validation_timer = QTimer(self)
        self.validation_timer.setSingleShot(True)
        self.validation_timer.setInterval(100)
        self.model_cls = self._generate_model(schema)
        self.initial_data = data_model_dump
        self.moudle_name = moudle_name
        self.widgets: Dict[str, WidgetInfo] = {}
        self.success_signal.connect(self.show_success_messagebox)
        self.error_signal.connect(self.show_error_messagebox)
        self._init_ui()

    def show_success_messagebox(self, data: ResponsePayload):
        MessageBoxBuilder().set_title("配置成功").set_content("当前配置成功完成保存,将在下一次启动时被应用").hide_icon().add_button(
            ButtonConfig(btn_type=MessageBoxConfig.ButtonType.OK, text="我明白了")
        ).build_and_fetch_result()

    def show_error_messagebox(self, data: ResponsePayload):
        MessageBoxBuilder().set_title("配置失败").set_content(f"当前配置未能完成保存,原因如下:\n{data.error}\n若你认为这是LazyTea的问题,请联系开发者").hide_icon().add_button(
            ButtonConfig(btn_type=MessageBoxConfig.ButtonType.OK, text="真是可惜")
        ).build_and_fetch_result()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        StyleManager.apply_base_style(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        StyleManager.style_scroll_area(scroll)

        content = QWidget()
        self.form_layout = QFormLayout()
        self.form_layout.setRowWrapPolicy(
            QFormLayout.RowWrapPolicy.WrapAllRows)
        self.form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form_layout.setVerticalSpacing(15)
        self.form_layout.setContentsMargins(5, 5, 5, 5)

        self._build_form()
        self._apply_initial_values()

        content.setLayout(self.form_layout)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        self._add_control_buttons(main_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("配置编辑器")
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
        """)

    def _generate_model(self, schema: Dict) -> Type[BaseModel]:
        fields = {}

        for field_name, props in schema["properties"].items():
            field_type = self._parse_json_schema_type(props)
            field_info = self._extract_field_info(props)
            fields[field_name] = (field_type, Field(**field_info))

        return create_model(schema.get("title", "Config"), **fields)

    def _parse_json_schema_type(self, props: Dict) -> Any:
        if "enum" in props:
            return Literal[tuple(props["enum"])]

        if props.get("type") == "array":
            return List[self._parse_json_schema_type(props["items"])]

        if "anyOf" in props:
            return Union[tuple(self._parse_json_schema_type(t) for t in props["anyOf"])]

        return self._type_mapping(props.get("type"))

    def _type_mapping(self, type_str: Optional[str]) -> Type:
        if type_str is None:
            return type(object())
        return {"string": str, "integer": int, "number": float, "boolean": bool, "null": type(None)}.get(type_str, type(object()))

    def _extract_field_info(self, props: Dict) -> Dict:
        return {k: v for k, v in {
            "description": props.get("description"),
            "ge": props.get("minimum"),
            "le": props.get("maximum"),
            "default": props.get("default")
        }.items() if v is not None}

    def _build_form(self) -> None:
        for name, field in self.model_cls.model_fields.items():
            self._create_field_row(name, field)

    def _create_field_row(self, field_name: str, field_info: FieldInfo) -> None:
        required = field_info.is_required()
        group = QGroupBox(field_name if not required else f"{field_name} *")
        StyleManager.style_group_box(group)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        label = QLabel(field_info.description or "")
        label.setProperty("class", "description")
        StyleManager.apply_style(label)
        label.setWordWrap(True)

        widget_container = QWidget()
        widget_layout = QVBoxLayout(widget_container)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setSpacing(5)

        error_label = QLabel()
        error_label.setProperty("class", "error-label")
        StyleManager.apply_style(error_label)
        error_label.setVisible(False)

        origin = get_origin(field_info.annotation)
        if origin is list:
            list_manager = ListManager(self, field_name, field_info)
            widget, getter, setter = list_manager.create_widget()

            self.widgets[field_name] = {
                "widget": widget,
                "getter": getter,
                "setter": setter,  # 初始setter来自create_widget
                "error": error_label,
                "field_info": field_info
            }
            # 更新为ListManager的set_values方法
            self.widgets[field_name]["setter"] = list_manager.set_values
        else:
            widget, getter, setter = WidgetFactory.create_widget(
                field_info, self.initial_data.get(field_name))

            self.widgets[field_name] = {
                "widget": widget,
                "getter": getter,
                "setter": setter,
                "error": error_label,
                "field_info": field_info
            }

        def schedule_validation():
            try:
                self.validation_timer.timeout.disconnect()
            except RuntimeError:
                pass
            self.validation_timer.timeout.connect(
                lambda: self._validate_field(field_name))
            self.validation_timer.start()

        if hasattr(widget, "valueChanged"):
            widget.valueChanged.connect(schedule_validation)  # type: ignore
        elif hasattr(widget, "textChanged"):
            widget.textChanged.connect(schedule_validation)  # type: ignore
        elif isinstance(widget, NoWheelComboBox):
            widget.currentIndexChanged.connect(schedule_validation)

        widget_layout.addWidget(widget)
        layout.addWidget(label)
        layout.addWidget(widget_container)
        layout.addWidget(error_label)
        group.setLayout(layout)
        self.form_layout.addRow(group)

    def _apply_initial_values(self) -> None:
        for name, info in self.widgets.items():
            if name in self.initial_data:
                info["setter"](self.initial_data[name])

    def _add_control_buttons(self, layout: QVBoxLayout) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)

        self.save_btn = QPushButton("保存配置")
        StyleManager.apply_style(self.save_btn)
        self.save_btn.setFixedHeight(36)
        self.save_btn.clicked.connect(self._save_config)

        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _save_config(self) -> None:
        try:
            data = self._get_current_values()
            self.model_cls(**data)
            for k, v in data.items():
                if isinstance(v, set):
                    data[k] = list(v)
            talker.send_request(
                "save_env", success_signal=self.success_signal, error_signal=self.error_signal,
                module_name=self.moudle_name, data=data, timeout=30)
        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                loc = error.get('loc', ())
                field_path = []

                for part in loc:
                    if isinstance(part, int):
                        field_path.append(f"第{part+1}个元素")
                    else:
                        field_path.append(str(part))

                translated = self._translate_error(error)
                if field_path:
                    prefix = " → ".join(field_path) + "："
                    error_messages.append(f"{prefix}{translated}")
                else:
                    error_messages.append(translated)

            error_text = "配置验证失败：\n\n" + "\n\n".join(
                f"• {msg}" for msg in error_messages
            )
            MessageBoxBuilder().set_title("配置失败").set_content(f"当前配置未能完成保存,原因如下:\n{error_text}\n\n请根据提示修正配置后重试。").hide_icon().add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.OK, text="了解了")
            ).build_and_fetch_result()

    def _get_current_values(self) -> Dict:
        return {name: info["getter"]() for name, info in self.widgets.items()}

    def _validate_element(self, value: Any, field_name: str) -> None:
        current_data = self._get_current_values()
        current_data[field_name] = value

        try:
            self.model_cls(**current_data)
        except ValidationError as e:
            field_errors = []
            for error in e.errors():
                if error['loc'][0] == field_name:
                    field_errors.append({
                        "type": error["type"],
                        "loc": error["loc"],
                        "msg": error["msg"],
                        "input": error["input"],
                        "ctx": error.get("ctx", {})
                    })

            if field_errors:
                raise ValidationError.from_exception_data(
                    title="ValidationError",
                    line_errors=field_errors
                )

    def _validate_field(self, name: str) -> bool:
        widget = self.widgets[name]
        try:
            widget["error"].setVisible(False)
            value = widget["getter"]()
            self._validate_element(value, name)
            return True
        except ValidationError as e:
            error = self._translate_error(e.errors()[0])
            widget["error"].setText(error)
            widget["error"].setVisible(True)
            return False

    def _translate_error(self, error: Union[Dict, Any]) -> str:
        """将Pydantic错误转换为友好提示"""
        error_type = error["type"]
        ctx = error.get("ctx", {})
        loc = error.get("loc", ())

        if len(loc) > 1 and isinstance(loc[1], int):
            return f"第{loc[1]+1}个元素：{self._translate_single_error(error_type, ctx)}"

        return self._translate_single_error(error_type, ctx)

    def _translate_single_error(self, error_type: str, ctx: dict) -> str:
        messages = {
            "type_error.integer": "请输入整数",
            "type_error.float": "请输入数字",
            "type_error.bool": "请选择是或否",
            "value_error.const": "值不符合要求",
            "greater_than_equal": f"值不能小于{ctx.get('ge', '')}",
            "less_than_equal": f"值不能大于{ctx.get('le', '')}",
            "literal_error": "请选择有效选项",
            "missing": "该字段为必填项",
            "list_type": "请输入有效的列表元素",
            "union_tag_invalid": "请选择有效的类型",
            "union_tag_not_found": "请选择类型"
        }
        return messages.get(error_type, f"输入错误：{error_type}")

    def _validate_all(self) -> bool:
        valid = all(self._validate_field(name) for name in self.widgets)
        return valid

    def cleanup(self):
        if self.validation_timer.isActive():
            self.validation_timer.stop()
