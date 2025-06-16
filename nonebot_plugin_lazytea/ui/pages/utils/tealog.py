import sys
import os
from loguru import logger

COLOR_SCHEME = {
    "DEBUG": "<fg #8e8e93>",
    "INFO": "<fg #5ac8fa>",
    "SUCCESS": "<fg #4cd964>",
    "WARNING": "<fg #ffcc00>",
    "ERROR": "<fg #ff3b30>",
    "CRITICAL": "<fg #ff2d55>",
    "CONTEXT": "#af52de",
    "TIME": "#aeaeb2",
}


def setup_logger(context: str = "LazyTEEEA", level: str = os.getenv("LOGLEVEL") or "DEBUG"):
    logger.remove()

    log_format = (
        f"<fg {COLOR_SCHEME['CONTEXT']}>{context}</> | "
        "<green>{time:MM-DD HH:mm:ss}</green> "
        "[<level>{level}</level>] "
        "{message}"
    )

    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
        enqueue=True,
    )

    for log_level, color in COLOR_SCHEME.items():
        if log_level in ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]:
            logger.level(log_level, color=color)

    return logger


logger = setup_logger()
