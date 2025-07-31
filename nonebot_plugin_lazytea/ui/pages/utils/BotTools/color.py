import random
import threading
from typing import Dict, Union, Iterator
import colorsys

GOLDEN_RATIO_CONJUGATE = (3 - 5**0.5) / 2


def create_color_generator(saturation: float = 0.8, lightness: float = 0.75) -> Iterator[str]:
    """
    使用黄金比例来无限地、懒加载地生成颜色

    Args:
        saturation (float): 所有生成颜色的饱和度 (0.0 到 1.0)。
        lightness (float): 所有生成颜色的亮度 (0.0 到 1.0)。

    Yields:
        Iterator[str]: 一个可以无限产生十六进制颜色字符串的迭代器。
    """
    hue = random.random()

    while True:
        hue = (hue + GOLDEN_RATIO_CONJUGATE) % 1.0

        rgb_float = colorsys.hls_to_rgb(hue, lightness, saturation)
        rgb_int = [int(c * 255) for c in rgb_float]

        yield f"#{rgb_int[0]:02X}{rgb_int[1]:02X}{rgb_int[2]:02X}"


class ColorMap:
    color_map: Dict[Union[int, str], str] = {}
    _color_generator_instance = create_color_generator()
    _lock = threading.Lock()

    @classmethod
    def get(cls, key) -> str:
        """
        为给定的键获取一个颜色。

        如果这个键是新的，会自动为其生成并分配一个新颜色。
        如果键已存在，则返回之前分配的颜色。

        Args:
            key (int | str): 需要关联颜色的键。
        Returns:
            str: 与该键关联的十六进制颜色字符串。
        """
        key_str = str(key)
        with cls._lock:
            if key_str in cls.color_map:
                return cls.color_map[key_str]
            else:
                new_color = next(cls._color_generator_instance)
                cls.color_map[key_str] = new_color
                return new_color

    @classmethod
    def reset(cls):
        """
        重置颜色映射表和颜色生成器的状态。
        """
        with cls._lock:
            cls.color_map.clear()
            cls._color_generator_instance = create_color_generator()