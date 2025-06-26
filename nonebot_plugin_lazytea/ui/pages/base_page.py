from threading import Lock
from PySide6.QtCore import QTimer, Signal, QMutex
from PySide6.QtWidgets import QWidget


class PageBase(QWidget):
    """防抖页面基类（单例模式）"""
    _instances = {}
    _mutex = QMutex()
    _lock = Lock()

    page_enter = Signal()  # 页面进入可视范围（防抖后）
    page_leave = Signal()  # 页面离开可视范围（防抖后）
    page_active = Signal()  # 页面获得焦点
    page_inactive = Signal()  # 页面失去焦点

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__new__(cls)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loaded = False  # 资源加载状态标记
        self._debounce_interval = 200  # 防抖时间间隔

        # 初始化定时器
        self._enter_timer = self._create_timer(self._handle_enter)
        self._leave_timer = self._create_timer(self._handle_leave)

    def show_subpage(self, widget: QWidget, title: str):
        parent = self.parent()
        show_method = None

        while parent is not None:
            method = getattr(parent, "show_subpage", None)

            if callable(method):
                show_method = method
                break

            parent = parent.parent()

        if show_method:
            show_method(self, widget, title)
        else:
            raise RuntimeWarning(
                f"{self.__class__.__name__} 所有父控件都没有实现 show_subpage 方法"
            )

    def _create_timer(self, callback):
        """创建防抖定时器"""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        return timer

    def showEvent(self, event):
        """显示事件处理"""
        if not self._is_loaded:
            self.on_first_enter()
            self._is_loaded = True

        # 取消待处理的离开事件
        self._leave_timer.stop()
        # 延迟触发进入事件
        self._enter_timer.start(self._debounce_interval)

        super().showEvent(event)

    def hideEvent(self, event):
        """隐藏事件处理"""
        # 取消待处理的进入事件
        self._enter_timer.stop()
        # 延迟触发离开事件
        self._leave_timer.start(self._debounce_interval)

        super().hideEvent(event)

    def _handle_enter(self):
        """实际处理页面进入"""
        if self.isVisible():
            self.page_enter.emit()  # 防抖后确认可见性再发送信号
            self.on_enter()
            self._check_activation()

    def _handle_leave(self):
        """实际处理页面离开"""
        if not self.isVisible():
            self.page_leave.emit()  # 防抖后确认隐藏再发送信号
            self.on_leave()
            self._check_deactivation()

    def _check_activation(self):
        """检查并触发焦点激活"""
        if self.isActiveWindow() and self.isVisible():
            self.page_active.emit()
            self.on_active()

    def _check_deactivation(self):
        """检查并触发焦点失活"""
        if not self.isActiveWindow() or not self.isVisible():
            self.page_inactive.emit()
            self.on_inactive()

    def on_first_enter(self):
        """首次进入页面时调用（仅触发一次）"""

    def on_enter(self):
        """防抖处理后进入页面"""

    def on_leave(self):
        """防抖处理后离开页面"""

    def on_active(self):
        """页面获得焦点时调用"""

    def on_inactive(self):
        """页面失去焦点时调用"""
