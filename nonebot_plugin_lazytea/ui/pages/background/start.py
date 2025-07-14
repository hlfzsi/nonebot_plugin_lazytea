from typing import Dict
from PySide6.QtCore import Signal, QObject
import importlib
import importlib.util
from types import ModuleType
import sys
import traceback

from ..utils.ui_types.plugins import PluginInfo
from ..utils.client import talker, ResponsePayload
from ..utils.tealog import logger

name_module: Dict[str, ModuleType] = {}


class PluginInit(QObject):
    data = Signal(ResponsePayload)
    signal = Signal(ResponsePayload)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugins_to_load = set()
        self.data.connect(self.process)
        self.signal.connect(self._self_import)
        talker.send_request(
            "get_plugins", success_signal=self.data)

    def process(self, data: ResponsePayload):
        plugins: Dict[str, PluginInfo] = data.data
        for plugin_name, plugin_data in plugins.items():
            if plugin_data.get("meta", {}).get("ui_support", False):
                self.plugins_to_load.add(plugin_name)
        if self.plugins_to_load:
            logger.info(f"发现需要加载的UI插件: {' | '.join(self.plugins_to_load)}")
        else:
            logger.info("没有发现需要加载的UI插件，将继续执行加载流程。")

        talker.send_request("ui_load", plugins_to_load=list(self.plugins_to_load), timeout=30,
                            success_signal=self.signal, error_signal=self.signal)

    def _self_import(self, _: ResponsePayload):
        """
        [最健arct solução]
        遍历插件，通过查找插件规范(spec)来创建一个完整的、但尚未执行的模块对象。
        这个对象拥有所有必需的属性(__path__, __spec__等)，可以完美地骗过导入系统，
        从而在绕过 __init__.py 的同时，还能正确加载子模块。
        """
        for plugin_name in self.plugins_to_load:
            module_path = f"{plugin_name}.__ui__"

            # 如果父包已经加载，我们无能为力，只能直接尝试导入
            if plugin_name in sys.modules:
                logger.warning(
                    f"插件包 '{plugin_name}' 已存在于 sys.modules 中。将直接尝试导入其 UI 模块。")
            else:
                # [核心修改] 使用 find_spec 和 module_from_spec 组合拳
                try:
                    # 1. 在不执行的情况下查找包的“配方”(spec)
                    spec = importlib.util.find_spec(plugin_name)
                    if spec is None:
                        logger.error(
                            f"无法找到插件 '{plugin_name}' 的规范(spec)。可能未正确安装或路径错误。")
                        continue

                    if spec.submodule_search_locations is None:
                        logger.error(
                            f"找到的 '{plugin_name}' 不是一个包（没有搜索路径），无法加载其子模块。")
                        continue

                    # 2. 使用“配方”创建一个完整的、但尚未执行的模块对象
                    #    这将自动设置好 __name__, __path__, __file__, __spec__, __loader__ 等所有重要属性！
                    fake_package = importlib.util.module_from_spec(spec)

                    # 3. 将这个完美的“假包”注入到 sys.modules
                    sys.modules[plugin_name] = fake_package
                    logger.debug(
                        f"为 '{plugin_name}' 注入了一个完整的假包以绕过 __init__.py。")

                except Exception as e:
                    logger.error(f"在为 '{plugin_name}' 准备假包时发生错误: {e}")
                    logger.error("详细错误信息:\n" + traceback.format_exc())
                    continue

            # 现在可以绝对安全地尝试导入 __ui__ 子模块了
            try:
                module = importlib.import_module(module_path)
                name_module[plugin_name] = module
                logger.success(f"成功导入插件UI模块: {module_path}")
            except ImportError:
                logger.error(
                    f"导入 '{module_path}' 失败 (ImportError)。请检查文件是否存在及其内部导入是否正确。")
                logger.error("详细错误信息:\n" + traceback.format_exc())
                continue
            except Exception as e:
                logger.error(f"导入 '{module_path}' 时出现未知错误: {e}")
                logger.error("详细错误信息:\n" + traceback.format_exc())
                continue

        self.deleteLater()
