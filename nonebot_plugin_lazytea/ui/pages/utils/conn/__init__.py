import os
from pathlib import Path
from functools import lru_cache

from .pool import PoolAccess, AsyncQuerySignal
from ..tealog import logger

__all__ = ["init_db", "get_database", "AsyncQuerySignal"]

_path = Path(os.getenv("UIDATADIR") or (Path(".") / "resources"))
os.makedirs(_path, exist_ok=True)
path = str(_path / "data.db3")


@lru_cache(maxsize=1)
def get_database():
    pool = PoolAccess.get(path, min_pool_size=1, max_pool_size=5)
    return pool


def init_db():
    pool = get_database()

    pool.execute_async("""
        CREATE TABLE IF NOT EXISTS Message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            group_id TEXT,
            bot TEXT,
            timestamps INTEGER,
            content TEXT,
            meta TEXT,
            plaintext TEXT
        );
    """, for_write=True)

    # 创建 FTS 虚拟表（使用 FTS5），仅包含 plaintext 字段
    pool.execute_async("""
        CREATE VIRTUAL TABLE IF NOT EXISTS message_for_fts USING fts5(plaintext);
    """, for_write=True)

    # 创建触发器：当向 Message 插入新记录时，同步到 FTS 表（调用 cut 函数分词）
    pool.execute_async("""
        CREATE TRIGGER IF NOT EXISTS trigger_message_insert AFTER INSERT ON Message
        BEGIN
            INSERT INTO message_for_fts(rowid, plaintext)
            VALUES (NEW.id, cut(NEW.plaintext));
        END;
    """, for_write=True)

    # 创建触发器：当更新 Message 记录时，同步更新 FTS 表（调用 cut 函数分词）
    pool.execute_async("""
        CREATE TRIGGER IF NOT EXISTS trigger_message_update AFTER UPDATE ON Message
        BEGIN
            UPDATE message_for_fts
            SET plaintext = cut(NEW.plaintext)
            WHERE rowid = NEW.id;
        END;
    """, for_write=True)

    # 创建触发器：当删除 Message 记录时，同步删除 FTS 表中的记录
    pool.execute_async("""
        CREATE TRIGGER IF NOT EXISTS trigger_message_delete AFTER DELETE ON Message
        BEGIN
            DELETE FROM message_for_fts WHERE rowid = OLD.id;
        END;
    """, for_write=True)

    try:
        pool.execute_async("REINDEX;", for_write=True)
    except Exception as e:
        logger.warning(f"[WARNING] Reindex failed: {e}")
