import random
from typing import Dict


class ColorMap:
    color_map: Dict[int | str, str] = {}
    _default_colors = ["#FFC1C1", "#00FF00", "#FFDAB9", "#EE82EE"]
    random.shuffle(_default_colors)
    DEFAULT_LIST = _default_colors
    _next_color_index = 0

    @classmethod
    def get(cls, key, default=None):
        if key in cls.color_map:
            return cls.color_map[key]
        else:
            return cls._assign_color(key, default)

    @classmethod
    def _assign_color(cls, key, default=None):
        if cls._next_color_index < len(cls.DEFAULT_LIST):
            color = cls.DEFAULT_LIST[cls._next_color_index]
            cls._next_color_index += 1
        elif default:
            color = default
        else:
            # 预设颜色用完后随机生成颜色
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            color = f"#{r:02X}{g:02X}{b:02X}"
        cls.color_map[key] = color
        return color
