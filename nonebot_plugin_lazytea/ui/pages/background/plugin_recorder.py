from PySide6.QtCore import QObject, Signal

from ..utils.conn import get_database
from ..utils.client import talker


class Recorder(QObject):
    calling_signal = Signal(str, dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.calling_signal.connect(self.insert)
        self._create_table()
        talker.subscribe("plugin_call", signal=self.calling_signal)
        
    def _create_table(self):
        table_name = "plugin_call_record"
        columns = """
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot TEXT,
                    platform TEXT,
                    time_costed REAL,
                    group_id TEXT,
                    user_id TEXT,
                    plugin_name TEXT,
                    matcher_hash TEXT,
                    exception_name TEXT,
                    exception_detail TEXT,
                    timestamp INTEGER
                    """
        create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns});'
        create_index_bot_platform = f'CREATE INDEX IF NOT EXISTS idx_bot_platform ON "{table_name}" (bot, platform);'
        create_index_timestamp = f'CREATE INDEX IF NOT EXISTS idx_timestamp ON "{table_name}" (timestamp);'
        db = get_database()
        db.execute_async(create_table_sql, for_write=True)
        db.execute_async(create_index_bot_platform, for_write=True)
        db.execute_async(create_index_timestamp, for_write=True)

    def insert(self, type_: str, data: dict):
        bot = data.get("bot")
        time_costed = float(data.get("time_costed", 0))
        timestamp = int(data.get("time", 0))
        group_id = data.get("groupid")
        user_id = data.get("userid")
        plugin_name = data.get("plugin")
        platform = data.get("platform")
        matcher_hash = ",".join(data.get("matcher_hash", ""))
        exception = data.get("exception")
        exception_name = exception.get(
            "name") if isinstance(exception, dict) else None
        exception_detail = exception.get(
            "detail") if isinstance(exception, dict) else None

        get_database().executelater(f"""
                                    INSERT INTO plugin_call_record(
                                    bot, platform, time_costed, group_id, user_id, plugin_name,
                                    matcher_hash, exception_name, exception_detail, timestamp
                                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (bot, platform, time_costed, group_id, user_id, plugin_name,
                                                                             matcher_hash, exception_name, exception_detail, timestamp))
