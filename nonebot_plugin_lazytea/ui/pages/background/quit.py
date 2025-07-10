import sys
import threading
from PySide6.QtCore import QObject, Signal


class StdinListener(QObject):
    """
    在一个单独的线程中监听标准输入流(stdin)的指令,
    当收到关闭指令时，发射一个信号。
    """
    shutdown_requested = Signal()
    _instance = None

    def __init__(self):
        super().__init__()
        self._thread = threading.Thread(target=self._run, daemon=True)

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            with threading.Lock():
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance

    def _run(self):
        try:
            for line in sys.stdin:
                command = line.strip()
                if command == "shutdown":
                    self.shutdown_requested.emit()
                    break
        except:
            import traceback
            traceback.print_exc()

    def start(self):
        """启动监听线程。"""
        self._thread.start()

