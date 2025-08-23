from enum import Enum
import orjson
from typing import Optional, Any, Literal
from pydantic import BaseModel, field_validator
from PySide6.QtGui import QColor
from PySide6.QtCore import QSize


class MessageBoxConfig:
    """
    消息框配置枚举类，包含按钮类型、图标类型和按钮模式的枚举定义 

    Attributes:
        ButtonType: 按钮类型枚举 
        IconType: 图标类型枚举 
        ButtonMode: 按钮交互模式枚举 
    """

    class ButtonType(Enum):
        """支持的按钮类型枚举"""
        OK = 0x00000400
        Cancel = 0x00400000
        Yes = 0x00004000
        No = 0x00010000
        Abort = 0x00040000
        Retry = 0x00100000
        Ignore = 0x00200000
        Custom = 0x00800000  # 可携带可序列化信息

    class IconType(Enum):
        """消息图标类型枚举"""
        Info = 1
        Warning = 2
        Critical = 3
        Question = 4
        NoIcon = 5
        Custom = 6  # 自定义图标类型

    class ButtonMode(Enum):
        """按钮交互模式枚举"""
        Always = 1
        """始终可点击"""

        AfterAnimation = 2
        """需要完成动画后才能点击"""

        AutoPress = 3
        """动画完成后自动触发点击"""


class ButtonConfig(BaseModel):
    """
    单个按钮的配置数据类 

    Attributes:
        btn_type (MessageBoxConfig.ButtonType): 按钮类型
        text (str): 按钮显示文本 
        custom_id (Optional[Any]): 自定义ID,支持可序列化数据,仅按钮类型为custom时有效
        role (Literal['primary', 'secondary', 'danger', 'normal']): 按钮角色 
        animation_color (Optional[QColor]): 按钮动画颜色，None表示使用默认颜色
        animation_opacity (int): 动画透明度 (0-255)
        animation_duration (Optional[int]): 动画持续时间 (ms)，None或0表示禁用动画 
        click_mode (Optional[MessageBoxConfig.ButtonMode]): 点击模式，None表示使用默认模式
        fixed_size (Optional[QSize]): 固定尺寸 
        min_width (Optional[int]): 最小宽度 
        max_width (Optional[int]): 最大宽度 
        closes_dialog (bool): 点击此按钮后是否关闭对话框
    """
    btn_type: MessageBoxConfig.ButtonType
    text: str
    custom_id: Optional[Any] = None
    role: Literal['primary', 'secondary', 'danger', 'normal'] = 'normal'
    animation_color: Optional[QColor] = None
    animation_opacity: int = 180
    animation_duration: Optional[int] = None
    click_mode: Optional[MessageBoxConfig.ButtonMode] = None
    fixed_size: Optional[QSize] = None
    min_width: Optional[int] = None
    max_width: Optional[int] = None
    closes_dialog: bool = True
    
    model_config = {'arbitrary_types_allowed': True}

    @field_validator('animation_color', mode='before')
    def validate_animation_color(cls, v):
        if isinstance(v, str):
            return QColor(v)
        elif isinstance(v, (tuple, list)):
            return QColor(*v)
        return v

    @field_validator('fixed_size', mode='before')
    def validate_fixed_size(cls, v):
        if isinstance(v, (tuple, list)) and len(v) == 2:
            return QSize(v[0], v[1])
        elif isinstance(v, dict) and 'width' in v and 'height' in v:
            return QSize(v['width'], v['height'])
        return v

    @field_validator('custom_id', mode='before')
    def validate_custom_id(cls, value):
        if value is not None:
            try:
                orjson.dumps(value)
            except (TypeError, ValueError):
                raise ValueError("custom_id must be serializable")
        return value
