import time
import threading

import apsw
from PySide6.QtCore import QObject, QTimer, Signal, QMutex, QMutexLocker, QThreadPool, QRunnable, QWaitCondition, QThread
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any, Union, Sequence

from ..token import tokenize
from ..tealog import logger


class ConnectionWrapper:
    def __init__(self, db_path: str):
        self.conn = apsw.Connection(db_path)
        self.mutex = QMutex()
        self.last_used = time.monotonic()
        self.in_use = False
        self.is_valid = True

    def execute(self, sql: str, params: Optional[Union[tuple, list]] = None) -> apsw.Cursor:
        with QMutexLocker(self.mutex):
            self.last_used = time.monotonic()
            cursor = self.conn.cursor()
            cursor.execute(sql, params or ())
            return cursor

    def executemany(self, sql: str, params_list: Sequence[Union[tuple, list]]) -> apsw.Cursor:
        with QMutexLocker(self.mutex):
            self.last_used = time.monotonic()
            cursor = self.conn.cursor()
            cursor.executemany(sql, params_list)
            return cursor

    def close(self):
        with QMutexLocker(self.mutex):
            self.conn.close()
            self.is_valid = False

    def ping(self) -> bool:
        """检查连接是否有效"""
        try:
            with QMutexLocker(self.mutex):
                cursor = self.conn.cursor()
                cursor.execute("SELECT 1").fetchone()
            return True
        except apsw.Error:
            return False


class AsyncQuerySignal(QObject):
    """异步查询结果信号"""
    finished = Signal(object, Exception)  # (result, error)


class AsyncQueryRunner(QRunnable):
    """异步查询执行器"""

    def __init__(self, connection_pool: 'SQLiteConnectionPool', sql: str, params: Any, signal: Optional[AsyncQuerySignal] = None):
        super().__init__()
        self.connection_pool = connection_pool
        self.sql = sql
        self.params = params
        self.signal = signal

    def run(self):
        result = None
        error = None
        conn = None
        try:
            conn = self.connection_pool.acquire_connection()
            cursor = conn.execute(self.sql, self.params)
            result = cursor.fetchall()
        except Exception as e:
            error = e
            logger.error(f"Query execution failed: {e}")
            logger.error(f"fail sql: {self.sql}  \nparams:  {self.params}")
            import traceback
            traceback.print_exc()
        finally:
            if conn:
                self.connection_pool.release_connection(conn)
            if self.signal:
                self.signal.finished.emit(result, error)


class WriteTask:
    """写入任务数据结构"""
    __slots__ = ('sql', 'params', 'is_many', 'result',
                 'error', 'completion_event')

    def __init__(self, sql: str, params: Optional[Union[Tuple, List]] = None, is_many: bool = False):
        self.sql: str = sql
        self.params: Optional[Union[Tuple, List]] = params
        self.is_many: bool = is_many
        self.result: Any = None
        self.error: Any = None
        self.completion_event: Optional[threading.Event] = None


class WriteWorker(QThread):
    """专用的写入工作线程，采用双缓冲结构减少锁冲突"""
    finished = Signal()

    def __init__(self, db_path: str):
        super().__init__()

        self.db_path = db_path
        self.active_queue = deque()
        self.pending_queue = deque()
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.running = True
        self.conn: Optional[apsw.Connection] = None

    def register_tokenizer(self):
        """注册自定义分词器到数据库连接"""
        try:
            def _tokenize(*args):
                if not args or not args[0]:
                    return ""
                text = str(args[0])

                words = tokenize(text)

                filtered_words = (word.strip() for word in words)
                return " ".join(word for word in filtered_words if word)

            self.conn.createscalarfunction(  # type: ignore
                "cut", _tokenize)
            logger.info("自定义分词器注册成功")
        except Exception as e:
            logger.error(f"注册自定义分词器失败: {e}")

    def run(self):
        """工作线程主循环"""
        threading.current_thread().name = f"database_writer_for_{self.db_path}"
        try:
            # 创建数据库连接
            self.conn = apsw.Connection(self.db_path)

            # 注册自定义分词器
            self.register_tokenizer()

            while True:
                with QMutexLocker(self.mutex):
                    while self.running and not self.pending_queue:
                        self.condition.wait(self.mutex)

                    if not self.running and not self.pending_queue:
                        break

                    self.active_queue, self.pending_queue = self.pending_queue, self.active_queue

                while self.active_queue:
                    if not self.running:
                        break
                    task: WriteTask = self.active_queue.popleft()
                    try:
                        cursor = self.conn.cursor()
                        if task.is_many:
                            cursor.executemany(task.sql, task.params or [])
                        else:
                            cursor.execute(task.sql, task.params or ())
                        task.result = True
                    except apsw.Error as e:
                        task.error = e
                        logger.error(f"写入操作失败: {e}\nSQL: {task.sql}")
                    finally:
                        if task.completion_event:
                            task.completion_event.set()
        except Exception as e:
            logger.exception("工作线程异常退出")
        finally:
            if self.conn:
                self.conn.close()
            self.finished.emit()

    def add_task(self, task: WriteTask):
        """添加写入任务到缓冲队列"""
        with QMutexLocker(self.mutex):
            # 添加到待处理队列（非活跃队列）
            self.pending_queue.append(task)
            # 唤醒工作线程
            self.condition.wakeOne()

    def get_pending_tasks_count(self) -> int:
        """返回当前待处理的任务总数（包括等待队列和活跃队列）"""
        with QMutexLocker(self.mutex):
            return len(self.pending_queue) + len(self.active_queue)

    def stop(self):
        """停止工作线程"""
        with QMutexLocker(self.mutex):
            self.running = False
            self.condition.wakeAll()


class SQLiteConnectionPool(QObject):
    connection_acquired = Signal()
    connection_released = Signal()
    connection_invalidated = Signal()

    def __init__(self, db_path: str, min_pool_size: int = 3, max_pool_size: int = 20,
                 idle_timeout: float = 300.0, connection_timeout: float = 5.0,
                 write_buffer_interval: int = 5000):
        super().__init__()
        self.db_path = db_path
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.idle_timeout = idle_timeout
        self.connection_timeout = connection_timeout

        # 连接管理
        self._idle_connections = deque()
        self._in_use_connections = set()
        self._all_connections = []

        # 同步机制
        self.pool_mutex = QMutex()
        self.condition = QWaitCondition()

        # 写操作队列和工作线程
        self.write_worker = WriteWorker(db_path)
        self.write_worker.start()

        # 初始化连接池
        self._init_connections(min_pool_size)

        # 双缓冲延迟提交系统
        self.front_buffer: Dict[str, List[Tuple]] = defaultdict(list)
        self.back_buffer: Dict[str, List[Tuple]] = defaultdict(list)
        self.buffer_mutex = QMutex()
        self.buffer_swap_mutex = QMutex()

        # 缓冲刷新定时器
        self.buffer_timer = QTimer(self)
        self.buffer_timer.setInterval(write_buffer_interval)
        self.buffer_timer.timeout.connect(self.commit_delayed)
        self.buffer_timer.start()

    def _init_connections(self, initial_size: int):
        """初始化连接池"""
        connections = []
        for _ in range(initial_size):
            conn = None
            try:
                conn = ConnectionWrapper(self.db_path)
                conn.execute("SELECT 1").fetchone()
                connections.append(conn)
            except apsw.Error as e:
                logger.error(f"Connection creation failed: {e}")
                if conn:
                    conn.close()

        with QMutexLocker(self.pool_mutex):
            self._idle_connections.extend(connections)
            self._all_connections.extend(connections)

        # 写操作初始化
        self._execute_write("PRAGMA journal_mode=WAL;")
        self._execute_write("REINDEX;")

    def _create_connection(self) -> ConnectionWrapper:
        """创建新连接并验证"""
        conn = ConnectionWrapper(self.db_path)
        try:
            conn.execute("SELECT 1").fetchone()
            return conn
        except apsw.Error as e:
            logger.error(f"Connection creation failed: {e}")
            conn.close()
            raise

    def acquire_connection(self) -> ConnectionWrapper:
        """
        从连接池获取连接
        如果无可用连接且未达上限则创建新连接
        超时未获取到连接则抛出异常
        """
        end_time = time.monotonic() + self.connection_timeout

        with QMutexLocker(self.pool_mutex):
            while True:
                # 尝试从空闲队列获取
                if self._idle_connections:
                    conn = self._idle_connections.popleft()
                    self._in_use_connections.add(conn)
                    conn.in_use = True
                    self.connection_acquired.emit()
                    return conn

                # 创建新连接（如果未达上限）
                if len(self._all_connections) < self.max_pool_size:
                    try:
                        conn = self._create_connection()
                        self._all_connections.append(conn)
                        self._in_use_connections.add(conn)
                        conn.in_use = True
                        self.connection_acquired.emit()
                        return conn
                    except apsw.Error:
                        # 创建失败则继续等待
                        pass

                # 等待可用连接 - 使用更短的超时检查
                remaining = max(0, end_time - time.monotonic())
                if not self.condition.wait(self.pool_mutex, int(remaining * 1000)):
                    raise TimeoutError("获取数据库连接超时")

    def release_connection(self, conn: ConnectionWrapper):
        """归还连接到连接池"""
        # 在锁外检查连接有效性
        is_valid = conn.is_valid and conn.ping()

        with QMutexLocker(self.pool_mutex):
            if conn in self._in_use_connections:
                self._in_use_connections.remove(conn)
                conn.in_use = False

                # 处理连接状态
                if is_valid:
                    self._idle_connections.append(conn)
                else:
                    logger.warning("连接失效，已移除")
                    try:
                        conn.close()
                    except:
                        pass
                    self.connection_invalidated.emit()
                    # 维持最小连接数
                    if len(self._all_connections) < self.min_pool_size:
                        try:
                            new_conn = self._create_connection()
                            self._all_connections.append(new_conn)
                            self._idle_connections.append(new_conn)
                        except apsw.Error as e:
                            logger.error(f"无法创建新连接: {e}")

                self.connection_released.emit()
                self.condition.wakeOne()

    def executelater(self, sql: str, params: Union[tuple, list]):
        """延迟提交方法"""
        with QMutexLocker(self.buffer_mutex):
            self.front_buffer[sql].append(tuple(params))

    def _swap_buffers(self):
        """交换前后缓冲区"""
        with QMutexLocker(self.buffer_swap_mutex):
            self.front_buffer, self.back_buffer = self.back_buffer, self.front_buffer

    def commit_delayed(self):
        """执行延迟提交 - 将缓冲区的操作提交到写队列"""
        self._swap_buffers()

        if not self.back_buffer:
            return

        tasks_added = 0
        for sql, params_list in self.back_buffer.items():
            if params_list:
                task = WriteTask(sql, params_list, is_many=True)
                self.write_worker.add_task(task)
                tasks_added += 1

        self.back_buffer.clear()

    def execute_async(self, sql: str, params: Union[tuple, list] = (),
                      callback_signal: Optional[AsyncQuerySignal] = None,
                      for_write: bool = True):
        """
        异步执行查询

        :param for_write: 标记是否为写操作（默认为True）
        """
        if for_write:
            self._execute_write_async(sql, params, callback_signal)
        else:
            self._execute_read_async(sql, params, callback_signal)

    def _execute_read_async(self, sql: str, params: Union[tuple, list],
                            callback_signal: Optional[AsyncQuerySignal] = None):
        runner = AsyncQueryRunner(self, sql, params, callback_signal)
        QThreadPool.globalInstance().start(runner)

    def _execute_write_async(self, sql: str, params: Union[tuple, list],
                             callback_signal: Optional[AsyncQuerySignal] = None):
        task = WriteTask(sql, params)
        signal = callback_signal or AsyncQuerySignal()

        def on_complete():
            if task.error:
                signal.finished.emit(None, task.error)
            else:
                signal.finished.emit(task.result, None)

        QTimer.singleShot(0, on_complete)
        self.write_worker.add_task(task)

    def execute(self, sql: str, params: Optional[Union[tuple, list]] = None, for_write: bool = True):
        """
        同步执行查询

        :param for_write: 标记是否为写操作（默认为True）
        """
        if for_write:
            return self._execute_write(sql, params)
        else:
            return self._execute_read(sql, params)

    def _execute_write(self, sql: str, params: Optional[Union[tuple, list]] = None):
        task = WriteTask(sql, params)
        task.completion_event = threading.Event()

        self.write_worker.add_task(task)
        task.completion_event.wait()

        if task.error:
            raise task.error
        return task.result

    def _execute_read(self, sql: str, params: Optional[Union[tuple, list]] = None):
        conn = self.acquire_connection()
        try:
            cursor = conn.execute(sql, params or ())
            result = cursor.fetchall()
            return result
        finally:
            self.release_connection(conn)

    def flush(self):
        """刷新缓冲区，提交所有延迟写入，并等待所有写任务完成"""
        # 提交所有延迟写入
        self.commit_delayed()

        # 等待写工作线程处理完所有任务
        while self.write_worker.get_pending_tasks_count() > 0:
            time.sleep(0.01)  # 10ms

    def shutdown(self):
        """关闭连接池"""
        self.buffer_timer.stop()

        self.flush()

        self.write_worker.stop()
        self.write_worker.wait()

        connections_to_close = []
        with QMutexLocker(self.pool_mutex):
            connections_to_close = list(self._all_connections)
            self._all_connections.clear()
            self._idle_connections.clear()
            self._in_use_connections.clear()

        for conn in connections_to_close:
            conn: ConnectionWrapper
            try:
                conn.close()
            except:
                pass

        logger.info("连接池已关闭")

    @property
    def total_connections(self) -> int:
        with QMutexLocker(self.pool_mutex):
            return len(self._all_connections)

    @property
    def idle_connections(self) -> int:
        with QMutexLocker(self.pool_mutex):
            return len(self._idle_connections)

    @property
    def active_connections(self) -> int:
        with QMutexLocker(self.pool_mutex):
            return len(self._in_use_connections)

    @property
    def pending_write_tasks(self) -> int:
        """返回写工作线程中待处理的任务总数"""
        return self.write_worker.get_pending_tasks_count()


class PoolAccess:
    existed_pool: Dict[str, SQLiteConnectionPool] = {}
    _lock = threading.Lock()

    @classmethod
    def get(cls, path: str, min_pool_size: int = 3, max_pool_size: int = 20, idle_timeout: float = 300, connection_timeout: float = 5, write_buffer_interval: int = 5000):
        if path in cls.existed_pool:
            return cls.existed_pool[path]
        else:
            with cls._lock:
                if path not in cls.existed_pool:
                    pool = SQLiteConnectionPool(
                        path, min_pool_size, max_pool_size, idle_timeout, connection_timeout, write_buffer_interval)
                    cls.existed_pool[path] = pool
            return cls.existed_pool[path]

    @classmethod
    def close(cls, path: str):
        if path in cls.existed_pool:
            cls.existed_pool[path].shutdown()
            del cls.existed_pool[path]

    @classmethod
    def close_all(cls):
        for path in list(cls.existed_pool.keys()):
            cls.close(path)
