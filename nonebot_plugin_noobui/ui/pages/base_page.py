from abc import abstractmethod
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QWidget
import qasync


class PageBase(QWidget):
    """防抖页面基类"""
    page_enter = pyqtSignal()  # 页面进入可视范围（防抖后）
    page_leave = pyqtSignal()  # 页面离开可视范围（防抖后）
    page_active = pyqtSignal()  # 页面获得焦点
    page_inactive = pyqtSignal()  # 页面失去焦点

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loaded = False  # 资源加载状态标记
        self._debounce_interval = 200  # 防抖时间间隔

        # 初始化定时器
        self._enter_timer = self._create_timer(self._handle_enter)
        self._leave_timer = self._create_timer(self._handle_leave)

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
        
    @qasync.asyncSlot()
    async def _handle_enter(self):
        """实际处理页面进入"""
        if self.isVisible():
            self.page_enter.emit()  # 防抖后确认可见性再发送信号
            await self.on_enter()
            await self._check_activation()

    @qasync.asyncSlot()
    async def _handle_leave(self):
        """实际处理页面离开"""
        if not self.isVisible():
            self.page_leave.emit()  # 防抖后确认隐藏再发送信号
            await self.on_leave()
            await self._check_deactivation()

    async def _check_activation(self):
        """检查并触发焦点激活"""
        if self.isActiveWindow() and self.isVisible():
            self.page_active.emit()
            await self.on_active()

    async def _check_deactivation(self):
        """检查并触发焦点失活"""
        if not self.isActiveWindow() or not self.isVisible():
            self.page_inactive.emit()
            await self.on_inactive()

    @abstractmethod
    def on_first_enter(self):
        """首次进入页面时调用（仅触发一次）  仅同步支持"""

    @abstractmethod
    async def on_enter(self):
        """防抖处理后进入页面"""

    @abstractmethod
    @qasync.asyncSlot()
    async def on_leave(self):
        """防抖处理后离开页面"""

    @abstractmethod
    @qasync.asyncSlot()
    async def on_active(self):
        """页面获得焦点时调用"""

    @abstractmethod
    @qasync.asyncSlot()
    async def on_inactive(self):
        """页面失去焦点时调用"""