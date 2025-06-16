"""
使用说明：
1. MessageBoxBuilder：消息框构建器，用于创建消息框的实例。
2. MessageBoxConfig：消息框配置枚举类，包含按钮类型、图标类型和按钮模式的枚举定义。

例:
```python
from . import MessageBoxBuilder, MessageBoxConfig
result = MessageBoxBuilder()
        .set_title("点击模式测试")
        .set_content("测试三种点击模式的工作情况")
        .set_icon_type(MessageBoxConfig.IconType.Question)
        .set_animation_duration(1000)  # 1秒动画
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.Yes,
            text="AutoPress模式",
            role='primary',
            click_mode=MessageBoxConfig.ButtonMode.AutoPress,
            # animation_color=QColor("#38B2AC"),
            animation_opacity=50
        ))
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.No,
            text="AfterAnimation模式",
            role='danger',
            click_mode=MessageBoxConfig.ButtonMode.AfterAnimation,
            animation_opacity=255
        ))
        .add_button(ButtonConfig(
            btn_type=MessageBoxConfig.ButtonType.Cancel,
            text="Always模式",
            click_mode=MessageBoxConfig.ButtonMode.Always
        ))
        .build_and_fetch_result()
```
"""


from .message_box import MessageBoxBuilder
from .model import MessageBoxConfig, ButtonConfig

__all__ = ["MessageBoxBuilder", "MessageBoxConfig", "ButtonConfig"]
