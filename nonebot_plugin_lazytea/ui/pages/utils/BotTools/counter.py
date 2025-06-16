import time
import threading
from collections import deque
from typing import Dict, Union, Optional

class MsgCounter:
    """时间窗口计数器"""
    __slots__ = ('_counters', '_max_period', '_merge_threshold', '_merge_ratio', '_lock')
    
    def __init__(self, 
                 max_period: int = 3600,
                 merge_threshold: int = 512,
                 merge_ratio: int = 2):
        self._max_period = max_period
        self._merge_threshold = merge_threshold
        self._merge_ratio = merge_ratio
        self._counters: Dict[str, Dict[str, _Counter]] = {} # type: ignore
        self._lock = threading.RLock()

    class _Counter:
        """使用循环缓冲区和层级合并策略的计数器"""
        __slots__ = ('base_count', 'time_windows', 'granularity',
                    '_merge_threshold', '_merge_ratio', '_max_period', '_lock')
        
        def __init__(self, max_period: int, merge_threshold: int, merge_ratio: int):
            self.base_count = 0
            self.time_windows = deque(maxlen=merge_threshold*2)  # 循环缓冲区优化
            self.granularity = 0.1
            self._merge_threshold = merge_threshold
            self._merge_ratio = merge_ratio
            self._max_period = max_period
            self._lock = threading.RLock()

        def _current_cutoff(self) -> float:
            return time.time() - self._max_period

        def _cleanup(self):
            """基于窗口结束时间的精确清理"""
            cutoff = self._current_cutoff()
            while self.time_windows:
                window_start, count = self.time_windows[0]
                window_end = window_start + self.granularity
                if window_end <= cutoff:
                    self.base_count += count
                    self.time_windows.popleft()
                else:
                    break

        def add_event(self, event_time: float, count: int = 1):
            with self._lock:
                self._cleanup()
                window_start = self._align_time(event_time)
                
                # 合并到最后一个窗口如果时间相同
                if self.time_windows and self.time_windows[-1][0] == window_start:
                    self.time_windows[-1] = (window_start, self.time_windows[-1][1] + count)
                else:
                    self.time_windows.append((window_start, count))
                
                # 动态合并检测
                if len(self.time_windows) > self._merge_threshold:
                    self._merge_windows()

        def _align_time(self, t: float) -> float:
            return (t // self.granularity) * self.granularity

        def _merge_windows(self):
            """层级合并算法"""
            with self._lock:
                new_granularity = self.granularity * self._merge_ratio
                merged = deque()
                current_ws = None
                current_cnt = 0

                for ws, cnt in self.time_windows:
                    aligned_ws = (ws // new_granularity) * new_granularity
                    if aligned_ws == current_ws:
                        current_cnt += cnt
                    else:
                        if current_ws is not None:
                            merged.append((current_ws, current_cnt))
                        current_ws, current_cnt = aligned_ws, cnt
                if current_ws is not None:
                    merged.append((current_ws, current_cnt))

                self.time_windows = merged
                self.granularity = new_granularity
                self._cleanup()

        def get_total(self) -> int:
            with self._lock:
                self._cleanup()
                return self.base_count + sum(cnt for _, cnt in self.time_windows)

        def get_period_count(self, period: float) -> float:
            with self._lock:
                self._cleanup()
                period = min(period, self._max_period)
                cutoff = time.time() - period
                total = 0.0
                
                for ws, cnt in self.time_windows:
                    window_end = ws + self.granularity
                    if window_end <= cutoff:
                        continue
                    
                    if ws >= cutoff:
                        total += cnt
                    else:
                        overlap_start = max(ws, cutoff)
                        overlap_end = min(window_end, time.time())
                        ratio = (overlap_end - overlap_start) / self.granularity
                        total += cnt * ratio
                return total

    def add_event(self, key: str, event_type: str, event_time: Optional[float] = None):
        with self._lock:
            counter = self._get_counter(key, event_type)
            counter.add_event(event_time or time.time())

    def batch_add_events(self, key: str, event_type: str, count: int, 
                        event_time: Optional[float] = None):
        with self._lock:
            counter = self._get_counter(key, event_type)
            counter.add_event(event_time or time.time(), count)

    def _get_counter(self, key: str, event_type: str) -> "_Counter":
        if key not in self._counters:
            self._counters[key] = {}
        if event_type not in self._counters[key]:
            self._counters[key][event_type] = self._Counter(
                self._max_period, self._merge_threshold, self._merge_ratio
            )
        return self._counters[key][event_type]

    def get_total_count(self, key: str, event_type: str = 'all') -> Union[int, float]:
        with self._lock:
            if key not in self._counters:
                return 0
            counters = self._counters[key]
            return (sum(c.get_total() for c in counters.values()) if event_type == 'all'
                    else counters[event_type].get_total() if event_type in counters else 0)

    def get_period_count(self, key: str, period: float, 
                        event_type: str = 'all') -> Union[int, float]:
        with self._lock:
            if key not in self._counters:
                return 0
            counters = self._counters[key]
            return (sum(c.get_period_count(period) for c in counters.values()) if event_type == 'all'
                    else counters[event_type].get_period_count(period) if event_type in counters else 0)