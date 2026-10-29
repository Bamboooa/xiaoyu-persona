"""小鱼的记忆点：她自己挑出来、值得留下的东西。

纯 SQLite，零依赖。区别于聊天记录——这里只存她主动判断「值得记」的碎片。
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "moments.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        create table if not exists moments (
            id integer primary key autoincrement,
            ts real not null,
            text text not null,
            nick text default '',
            uid text default '',
            group_id text default '',
            importance real default 0.5,
            shared integer default 0
        )
        """
    )
    con.commit()
    return con


def add(text: str, nick: str = "", uid: str = "", group_id: str = "",
        importance: float = 0.5) -> int:
    text = (text or "").strip()
    if not text:
        raise ValueError("空内容不记")
    con = _conn()
    try:
        cur = con.execute(
            "insert into moments (ts, text, nick, uid, group_id, importance)"
            " values (?,?,?,?,?,?)",
            (time.time(), text[:500], nick, uid, group_id, float(importance)),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def recent(limit: int = 10, days: int = 30) -> list[dict]:
    con = _conn()
    try:
        since = time.time() - days * 86400
        rows = con.execute(
            "select id, ts, text, nick, uid, importance, shared from moments"
            " where ts >= ? order by ts desc limit ?",
            (since, limit),
        ).fetchall()
        return [
            {
                "id": r[0],
                "time": datetime.fromtimestamp(r[1]).strftime("%m-%d %H:%M"),
                "text": r[2],
                "nick": r[3],
                "uid": r[4],
                "importance": r[5],
                "shared": bool(r[6]),
            }
            for r in rows
        ]
    finally:
        con.close()


def search(keyword: str, limit: int = 10) -> list[dict]:
    con = _conn()
    try:
        rows = con.execute(
            "select id, ts, text, nick, uid, importance, shared from moments"
            " where text like ? order by ts desc limit ?",
            (f"%{keyword}%", limit),
        ).fetchall()
        return [
            {
                "id": r[0],
                "time": datetime.fromtimestamp(r[1]).strftime("%m-%d %H:%M"),
                "text": r[2],
                "nick": r[3],
                "importance": r[5],
            }
            for r in rows
        ]
    finally:
        con.close()


def unshared(limit: int = 20) -> list[dict]:
    con = _conn()
    try:
        rows = con.execute(
            "select id, ts, text, nick, importance from moments"
            " where shared = 0 order by importance desc, ts desc limit ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "time": datetime.fromtimestamp(r[1]).strftime("%m-%d %H:%M"),
             "text": r[2], "nick": r[3], "importance": r[4]}
            for r in rows
        ]
    finally:
        con.close()


def mark_shared(moment_id: int) -> None:
    con = _conn()
    try:
        con.execute("update moments set shared = 1 where id = ?", (moment_id,))
        con.commit()
    finally:
        con.close()


def count_today() -> int:
    con = _conn()
    try:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return int(con.execute(
            "select count(*) from moments where ts >= ?", (start,)
        ).fetchone()[0])
    finally:
        con.close()
