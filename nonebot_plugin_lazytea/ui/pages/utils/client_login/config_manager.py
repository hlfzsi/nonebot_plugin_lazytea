import ujson
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ValidationError
from ..tealog import logger


CONFIG_DIR = Path(".") / "resources"
CONFIG_FILE = CONFIG_DIR / "login.json"


class ConnectionDetails(BaseModel):
    """
    用于存储和验证连接信息的Pydantic模型
    """
    host: str = "127.0.0.1"
    port: int
    token: str = "疯狂星期四V我50"
    remember: bool = False


class ConnectionConfigManager:
    """
    负责管理 login.json 的读取和写入
    """

    def __init__(self, path: Path = CONFIG_FILE):
        self._config_path = path

    def save_config(self, details: ConnectionDetails) -> None:
        """
        将连接详情保存到 JSON 文件

        Args:
            details (ConnectionDetails): 要保存的连接详情对象
        """
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                f.write(details.model_dump_json(indent=4))
            logger.info(f"Connection config saved to {self._config_path}")
        except IOError as e:
            logger.error(f"Failed to save config file: {e}")

    def load_config(self) -> Optional[ConnectionDetails]:
        """
        从 JSON 文件加载连接详情

        Returns:
            Optional[ConnectionDetails]: 如果文件存在且内容有效, 返回配置对象, 否则返回 None.
        """
        if not self._config_path.exists():
            return None
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = ujson.load(f)
                return ConnectionDetails(**data)
        except (IOError, ujson.JSONDecodeError, ValidationError) as e:
            logger.warning(
                f"Failed to load or validate config file {self._config_path}: {e}")
            return None
