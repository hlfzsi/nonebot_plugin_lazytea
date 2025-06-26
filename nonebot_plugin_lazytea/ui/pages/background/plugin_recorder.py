from PySide6.QtCore import QObject, Signal

from ..utils.conn import get_database
from ..utils.client import talker


class Recorder(QObject):
    calling_signal = Signal(str, dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.handled_plugin = set()
        self.calling_signal.connect(self.insert)
        talker.subscribe("plugin_call", signal=self.calling_signal)

    def insert(self, type_: str, data: dict):
        bot = data.get("bot")
        time_costed = float(data.get("time_costed", 0))
        timestamps = int(data.get("time", 0))
        group_id = data.get("groupid")
        user_id = data.get("userid")
        plugin_name = data.get("plugin")
        matcher_hash = ",".join(data.get("matcher_hash", ""))
        exception = data.get("exception")
        exception_name = exception.get(
            "name") if isinstance(exception, dict) else None
        exception_detail = exception.get(
            "detail") if isinstance(exception, dict) else None

        table_name = f"plugin_call_{plugin_name}"

        if plugin_name not in self.handled_plugin:
            columns = """
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot TEXT,
                    time_costed REAL,
                    group_id TEXT,
                    user_id TEXT,
                    plugin_name TEXT,
                    matcher_hash TEXT,
                    exception_name TEXT,
                    exception_detail TEXT,
                    timestamps INTEGER
                    """
            create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns});'
            self.handled_plugin.add(plugin_name)
            get_database().execute_async(create_table_sql, for_write=True)

        get_database().executelater(f"""
                                    INSERT INTO {table_name}(
                                    bot, time_costed, group_id, user_id, plugin_name,
                                    matcher_hash, exception_name, exception_detail, timestamps
                                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""", (bot, time_costed, group_id, user_id, plugin_name,
                                                                             matcher_hash, exception_name, exception_detail, timestamps))
