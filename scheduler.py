# -*- coding: utf-8 -*-
"""后台调度线程：每 2 秒扫一次到期任务，通过信号把任务 id 丢回主线程。"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from storage import FMT


class Scheduler(QThread):
    fired = Signal(int)

    def __init__(self, db_path: str, interval: float = 2.0, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.interval = interval
        self._stop = threading.Event()
        self._running_evt = threading.Event()
        self._running_evt.set()

    # ------------------------------------------------------------ 控制
    def pause(self) -> None:
        self._running_evt.clear()

    def resume(self) -> None:
        self._running_evt.set()

    def stop(self) -> None:
        self._stop.set()
        self.wait(4000)

    # ------------------------------------------------------------ 主循环
    def run(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=5)
        try:
            conn.execute("PRAGMA busy_timeout = 4000")
            while not self._stop.is_set():
                if self._running_evt.is_set():
                    try:
                        for tid in self._scan(conn):
                            self.fired.emit(tid)
                    except Exception:
                        pass          # 单次扫描失败不影响下一轮
                self._stop.wait(self.interval)
        finally:
            conn.close()

    def _scan(self, conn: sqlite3.Connection) -> list[int]:
        now = datetime.now().strftime(FMT)
        rows = conn.execute(
            "SELECT id FROM tasks WHERE done=0 AND notified=0 "
            "AND due IS NOT NULL AND due <= ? ORDER BY due ASC",
            (now,),
        ).fetchall()
        if not rows:
            return []
        ids = [int(r[0]) for r in rows]
        conn.executemany("UPDATE tasks SET notified=1 WHERE id=?", [(i,) for i in ids])
        conn.commit()
        return ids
