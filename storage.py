# -*- coding: utf-8 -*-
"""SQLite 存储层：任务、重复规则、设置。"""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

APP_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ReminderDesk")
DB_PATH = os.path.join(APP_DIR, "reminder.db")
LEGACY_JSON = os.path.join(APP_DIR, "tasks.json")

FMT = "%Y-%m-%d %H:%M"

REPEATS = [
    ("none", "不重复"),
    ("daily", "每天"),
    ("weekly", "每周"),
    ("monthly", "每月"),
    ("workdays", "工作日"),
]
REPEAT_LABELS = dict(REPEATS)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL DEFAULT '',
    note        TEXT    NOT NULL DEFAULT '',
    due         TEXT,
    repeat      TEXT    NOT NULL DEFAULT 'none',
    done        INTEGER NOT NULL DEFAULT 0,
    done_at     TEXT,
    notified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(done, due);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@dataclass
class Task:
    id: int = 0
    title: str = ""
    note: str = ""
    due: datetime | None = None
    repeat: str = "none"
    done: bool = False
    notified: bool = False
    done_at: datetime | None = None


# ---------------------------------------------------------------- 时间工具
def fmt_due(due: datetime | None) -> str:
    if not due:
        return "不提醒"
    d = due.date()
    today = date.today()
    if d == today:
        pre = "今天"
    elif d == today + timedelta(days=1):
        pre = "明天"
    elif d == today - timedelta(days=1):
        pre = "昨天"
    elif d.year == today.year:
        pre = "%d月%d日" % (d.month, d.day)
    else:
        pre = "%d-%02d-%02d" % (d.year, d.month, d.day)
    return "%s %02d:%02d" % (pre, due.hour, due.minute)


def fmt_left(due: datetime | None, now: datetime | None = None) -> str:
    """距离提醒还剩多久（或已逾期多久）。"""
    if not due:
        return ""
    now = now or datetime.now()
    secs = (due - now).total_seconds()

    if secs <= 0:
        late = -secs
        if late < 60:
            return "刚刚到期"
        if late < 3600:
            return "已逾期 %d 分钟" % int(late // 60)
        if late < 86400:
            return "已逾期 %d 小时" % int(late // 3600)
        return "已逾期 %d 天" % int(late // 86400)

    if secs < 60:
        return "马上提醒"
    if secs < 3600:
        return "还有 %d 分钟" % int(secs // 60)
    if secs < 86400:
        h, m = int(secs // 3600), int((secs % 3600) // 60)
        return "还有 %d 小时" % h if m < 5 else "还有 %d 小时 %d 分" % (h, m)
    d, h = int(secs // 86400), int((secs % 86400) // 3600)
    if d <= 7 and h:
        return "还有 %d 天 %d 小时" % (d, h)
    return "还有 %d 天" % d


def _add_month(d: datetime, n: int = 1) -> datetime:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def next_due(due: datetime, repeat: str, now: datetime) -> datetime | None:
    """算出下一次应当提醒的时间；「不重复」返回 None。"""
    if repeat == "none" or not due:
        return None
    t = due
    for _ in range(600):
        if repeat == "daily":
            t = t + timedelta(days=1)
        elif repeat == "weekly":
            t = t + timedelta(days=7)
        elif repeat == "monthly":
            t = _add_month(t)
        elif repeat == "workdays":
            t = t + timedelta(days=1)
            while t.weekday() >= 5:
                t = t + timedelta(days=1)
        else:
            return None
        if t > now:
            return t
    return t


def _parse_dt(raw) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, FMT)
    except ValueError:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"] or "",
        note=row["note"] or "",
        due=_parse_dt(row["due"]),
        repeat=row["repeat"] or "none",
        done=bool(row["done"]),
        notified=bool(row["notified"]),
        done_at=_parse_dt(row["done_at"]),
    )


class Store:
    """主线程使用的数据库句柄。调度线程会自己再开一个连接。"""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------- 任务
    def all(self) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks ORDER BY done ASC, "
            "CASE WHEN due IS NULL THEN 1 ELSE 0 END, due ASC, id DESC"
        ).fetchall()
        return [_row_to_task(r) for r in rows]

    def get(self, tid: int) -> Task | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return _row_to_task(row) if row else None

    def add(self, title: str, note: str, due: datetime | None, repeat: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO tasks (title, note, due, repeat, done, notified, created_at) "
            "VALUES (?,?,?,?,0,0,?)",
            (title, note, due.strftime(FMT) if due else None, repeat,
             datetime.now().strftime(FMT)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update(self, tid: int, title: str, note: str,
               due: datetime | None, repeat: str) -> None:
        old = self.get(tid)
        notified = old.notified if old else False
        if due is None:
            notified = False
        elif not old or old.due != due:
            notified = False
        self.conn.execute(
            "UPDATE tasks SET title=?, note=?, due=?, repeat=?, notified=? WHERE id=?",
            (title, note, due.strftime(FMT) if due else None, repeat, int(notified), tid),
        )
        self.conn.commit()

    def delete(self, tid: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        self.conn.commit()

    def complete(self, tid: int) -> None:
        """完成任务：重复任务滚动到下一次，普通任务标记已完成。"""
        t = self.get(tid)
        if not t:
            return
        now = datetime.now()
        nd = next_due(t.due, t.repeat, now) if t.due else None
        if nd:
            self.conn.execute(
                "UPDATE tasks SET due=?, done=0, done_at=NULL, notified=0 WHERE id=?",
                (nd.strftime(FMT), tid),
            )
        else:
            self.conn.execute(
                "UPDATE tasks SET done=1, done_at=? WHERE id=?",
                (now.strftime(FMT), tid),
            )
        self.conn.commit()

    def reopen(self, tid: int) -> None:
        self.conn.execute(
            "UPDATE tasks SET done=0, done_at=NULL, notified=0 WHERE id=?", (tid,)
        )
        self.conn.commit()

    def clear_done(self) -> int:
        cur = self.conn.execute("DELETE FROM tasks WHERE done=1")
        self.conn.commit()
        return cur.rowcount

    def silence_stale(self, hours: int = 12) -> None:
        """启动时把很久以前就该响的任务标记为已提醒，避免一次弹一堆。"""
        limit = (datetime.now() - timedelta(hours=hours)).strftime(FMT)
        self.conn.execute(
            "UPDATE tasks SET notified=1 WHERE done=0 AND notified=0 "
            "AND due IS NOT NULL AND due < ?",
            (limit,),
        )
        self.conn.commit()

    # ------------------------------------------------------------- 设置
    def get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_bool(self, key: str, default: bool = True) -> bool:
        return self.get_meta(key, "1" if default else "0") == "1"

    def set_bool(self, key: str, value: bool) -> None:
        self.set_meta(key, "1" if value else "0")

    # ------------------------------------------------------------- 迁移 / 示例
    def migrate_legacy(self) -> int:
        """把旧 tkinter 版本留下的 tasks.json 导入（仅当库为空）。"""
        if not os.path.exists(LEGACY_JSON):
            return 0
        n = int(self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
        if n:
            return 0
        try:
            with open(LEGACY_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0
        inserted = 0
        for t in data.get("tasks", []):
            due_ts = float(t.get("due") or 0)
            due = datetime.fromtimestamp(due_ts) if due_ts else None
            self.conn.execute(
                "INSERT INTO tasks (title, note, due, repeat, done, notified, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (str(t.get("title") or "未命名任务"), "", 
                 due.strftime(FMT) if due else None, "none",
                 1 if t.get("done") else 0, 1 if t.get("notified") else 0,
                 datetime.now().strftime(FMT)),
            )
            inserted += 1
        self.conn.commit()
        return inserted

    def seed_demo(self) -> int:
        """首次启动放三条示例，方便直接看效果。"""
        if int(self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]):
            return 0
        now = datetime.now().replace(second=0, microsecond=0)
        rows = [
            ("整理今日待办", "把今天最重要的三件事排个顺序", now + timedelta(hours=1), "daily"),
            ("喝水休息一下", "站起来活动五分钟", now + timedelta(hours=3), "workdays"),
            ("交房租", "下个月的房租别忘了", (now + timedelta(days=4)).replace(hour=9, minute=0), "monthly"),
        ]
        for title, note, due, rep in rows:
            self.add(title, note, due, rep)
        return len(rows)
