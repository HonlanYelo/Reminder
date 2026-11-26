# -*- coding: utf-8 -*-
"""主窗口：侧边导航 + 任务列表 + 设置页；新建/编辑走 TaskDialog 弹窗。"""
from __future__ import annotations

import os
import time
from datetime import date, datetime

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QScrollArea, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

import icons
import theme
from scheduler import Scheduler
from storage import Store, Task, fmt_due
from taskdialog import TaskDialog
from widgets import NavItem, TaskCard, TopBar

APP_TITLE = "小提醒"

# 本次运行开始的时刻 + 源码清单：用来判断窗口里跑的是不是最新代码
_START_TS = time.time()
_HERE = os.path.dirname(os.path.abspath(__file__))
_SOURCES = ("main.py", "mainwindow.py", "taskdialog.py", "datefield.py", "widgets.py",
            "theme.py", "storage.py", "scheduler.py", "icons.py")


def sources_mtime() -> float:
    latest = 0.0
    for name in _SOURCES:
        p = os.path.join(_HERE, name)
        if os.path.exists(p):
            latest = max(latest, os.path.getmtime(p))
    return latest


class MainWindow(QWidget):
    W_MAX, H_MAX = 1180, 772

    def __init__(self):
        super().__init__()
        self.store = Store()
        self.store.migrate_legacy()
        self.store.seed_demo()
        self.store.silence_stale()

        self.tasks: list[Task] = []
        self.nav_key = "all"
        self.search_text = ""
        self.tray = None
        self.dialog: TaskDialog | None = None
        self._quitting = False

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(icons.app_icon())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._build()
        self._resize()
        self.refresh()

        # 卡片上的「还剩多久」每 10 秒就地刷新，不重建列表
        self._left_timer = QTimer(self)
        self._left_timer.timeout.connect(self._tick_left)
        self._left_timer.start(10000)

        self.scheduler = Scheduler(self.store.path)
        self.scheduler.fired.connect(self.on_due)
        self.scheduler.start()

    # ================================================================ 界面
    def _resize(self):
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        w, h = self.W_MAX, self.H_MAX
        if geo:
            w = min(w, geo.width() - 40)
            h = min(h, geo.height() - 40)
        self.setFixedSize(w, h)
        if geo:
            self.move(geo.center() - self.rect().center())

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 20)

        self.card = QFrame()
        self.card.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(60, 84, 150, 70))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        self.topbar = TopBar(self.card)
        self.topbar.minimize.connect(self.showMinimized)
        self.topbar.close.connect(self.hide_to_tray)
        card_lay.addWidget(self.topbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        self.stack.setObjectName("Stack")
        self.stack.addWidget(self._build_list_page())
        self.stack.addWidget(self._build_settings_page())
        body.addWidget(self.stack, 1)
        card_lay.addLayout(body, 1)

    # ---------------------------------------------------------------- 侧栏
    def _build_sidebar(self):
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(216)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(14, 2, 14, 16)
        lay.setSpacing(5)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.setContentsMargins(0, 8, 0, 20)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("clock", theme.ACCENT, 32, width=1.8))
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        brand.addWidget(logo)
        name = QLabel(APP_TITLE)
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name.setStyleSheet("font-size:18px;font-weight:700;color:%s;margin-top:7px;" % theme.INK)
        brand.addWidget(name)
        tag = QLabel("准时提醒 · 简单生活")
        tag.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        tag.setStyleSheet("font-size:12px;color:#98a2bb;margin-top:3px;")
        brand.addWidget(tag)
        lay.addLayout(brand)

        self.nav = {}
        for key, label, ico in (("all", "全部任务", "list"),
                                ("today", "今天", "calendar"),
                                ("upcoming", "即将提醒", "bell"),
                                ("done", "已完成", "check-circle")):
            item = NavItem(key, label, ico, bar)
            item.clicked.connect(self._on_nav)
            lay.addWidget(item)
            self.nav[key] = item

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#e6ebfa;")
        lay.addSpacing(10)
        lay.addWidget(line)
        lay.addSpacing(10)

        self.nav["settings"] = NavItem("settings", "设置", "sliders", bar)
        self.nav["settings"].clicked.connect(self._on_nav)
        lay.addWidget(self.nav["settings"])
        lay.addStretch(1)

        status = QFrame()
        status.setObjectName("StatusCard")
        s = QVBoxLayout(status)
        s.setContentsMargins(13, 11, 13, 12)
        s.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet("background:#25bb76;border-radius:4px;")
        row.addWidget(dot)
        st = QLabel("后台运行中")
        st.setStyleSheet("font-size:12px;color:#3b4969;")
        row.addWidget(st)
        row.addStretch(1)
        s.addLayout(row)
        s2 = QLabel("关闭窗口后继续提醒")
        s2.setStyleSheet("font-size:11px;color:#98a2bb;margin-left:16px;")
        s.addWidget(s2)
        lay.addWidget(status)
        return bar

    # ---------------------------------------------------------------- 列表页
    def _build_list_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 4, 22, 14)
        lay.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        greet = QVBoxLayout()
        greet.setSpacing(4)
        self.h1 = QLabel("早上好")
        self.h1.setStyleSheet("font-size:25px;font-weight:700;color:%s;" % theme.INK)
        self.h2 = QLabel("今天没有待办，放松一下")
        self.h2.setStyleSheet("font-size:13px;color:#7d88a8;")
        greet.addWidget(self.h1)
        greet.addWidget(self.h2)
        header.addLayout(greet)
        header.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("搜索任务")
        self.search.setFixedSize(212, 38)
        self.search.addAction(icons.icon("search", "#98a2bb", 15),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._on_search)
        header.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)

        new_btn = QPushButton("新建任务")
        new_btn.setObjectName("Primary")
        new_btn.setIcon(icons.icon("plus", "#ffffff", 15, width=2.2))
        new_btn.setIconSize(QSize(15, 15))
        new_btn.setFixedHeight(38)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._focus_form)
        header.addWidget(new_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("ScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.list_host = QWidget()
        self.list_host.setObjectName("ListHost")
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 10, 4)
        self.list_lay.setSpacing(12)
        self.list_lay.addStretch(1)
        self.scroll.setWidget(self.list_host)
        body.addWidget(self.scroll, 1)
        lay.addLayout(body, 1)

        self.footer = QLabel("共 0 个任务 · 0 个已完成")
        self.footer.setStyleSheet("font-size:12px;color:#98a2bb;")
        lay.addWidget(self.footer)
        return page

    # ---------------------------------------------------------------- 设置页
    def _build_settings_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 8, 22, 18)
        lay.setSpacing(14)

        h1 = QLabel("设置")
        h1.setStyleSheet("font-size:25px;font-weight:700;color:%s;" % theme.INK)
        lay.addWidget(h1)
        sub = QLabel("偏好会立刻生效并保存到本地数据库")
        sub.setStyleSheet("font-size:13px;color:#7d88a8;")
        lay.addWidget(sub)
        lay.addSpacing(4)

        # 提醒
        card = self._setting_card("提醒", "bell")
        self.cb_tray = QCheckBox("关闭窗口时隐藏到托盘")
        self.cb_tray.setChecked(self.store.get_bool("close_to_tray", True))
        self.cb_tray.toggled.connect(lambda v: self.store.set_bool("close_to_tray", v))
        card.layout().addWidget(self.cb_tray)
        self.cb_sound = QCheckBox("无系统托盘时补一声提示音")
        self.cb_sound.setToolTip("正常情况走系统通知，声音由系统播放，这里不重复响")
        self.cb_sound.setChecked(self.store.get_bool("sound", True))
        self.cb_sound.toggled.connect(lambda v: self.store.set_bool("sound", v))
        card.layout().addWidget(self.cb_sound)
        lay.addWidget(card)

        # 数据
        card2 = self._setting_card("数据", "folder")
        path = QLabel(self.store.path)
        path.setStyleSheet("font-size:12px;color:#8b95b2;")
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card2.layout().addWidget(path)
        row = QHBoxLayout()
        row.setSpacing(8)
        open_dir = QPushButton("打开数据目录")
        open_dir.setObjectName("Ghost")
        open_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        open_dir.clicked.connect(self._open_data_dir)
        clear = QPushButton("清理已完成任务")
        clear.setObjectName("Ghost")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self._clear_done)
        row.addWidget(open_dir)
        row.addWidget(clear)
        row.addStretch(1)
        card2.layout().addSpacing(4)
        card2.layout().addLayout(row)
        lay.addWidget(card2)

        # 关于
        card3 = self._setting_card("关于", "info")
        about = QLabel("小提醒 2.0　·　PySide6 + SQLite + 系统托盘")
        about.setStyleSheet("font-size:13px;color:#6b7695;")
        card3.layout().addWidget(about)
        self.build_lb = QLabel()
        self.build_lb.setWordWrap(True)
        card3.layout().addWidget(self.build_lb)
        self._refresh_build_info()
        tip = QLabel("提醒服务在后台线程按秒巡检，主界面关闭也不影响。")
        tip.setStyleSheet("font-size:12px;color:#a2abc2;")
        tip.setWordWrap(True)
        card3.layout().addWidget(tip)
        lay.addWidget(card3)
        lay.addStretch(1)
        return page

    def _refresh_build_info(self):
        """当前进程启动后源码有没有再改过：改过就提示重启。"""
        latest = sources_mtime()
        stamp = datetime.fromtimestamp(latest).strftime("%m-%d %H:%M") if latest else "-"
        if latest > _START_TS:
            self.build_lb.setText("代码已更新（%s），重启后生效" % stamp)
            self.build_lb.setStyleSheet("font-size:12px;color:%s;" % theme.AMBER)
        else:
            self.build_lb.setText("构建 %s　·　本次运行开始于 %s"
                                  % (stamp,
                                     datetime.fromtimestamp(_START_TS).strftime("%H:%M")))
            self.build_lb.setStyleSheet("font-size:12px;color:#a2abc2;")

    @staticmethod
    def _setting_card(title, icon_name):
        card = QFrame()
        card.setObjectName("SettingCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 18)
        v.setSpacing(9)
        head = QHBoxLayout()
        head.setSpacing(9)
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, theme.ACCENT, 16, width=1.8))
        head.addWidget(ico)
        lb = QLabel(title)
        lb.setStyleSheet("font-size:14px;font-weight:700;color:%s;" % theme.INK)
        head.addWidget(lb)
        head.addStretch(1)
        v.addLayout(head)
        return card

    # ================================================================ 数据刷新
    def refresh(self):
        self.tasks = self.store.all()
        self._refresh_counts()
        self._render_cards()

    def _refresh_counts(self):
        now = datetime.now()
        counts = {
            "all": len(self.tasks),
            "today": sum(1 for t in self.tasks
                         if not t.done and t.due and t.due.date() == date.today()),
            "upcoming": sum(1 for t in self.tasks
                            if not t.done and t.due and t.due > now),
            "done": sum(1 for t in self.tasks if t.done),
        }
        for key, n in counts.items():
            self.nav[key].set_count(n)

        self._update_header(counts)
        self.footer.setText("共 %d 个任务 · %d 个已完成" % (len(self.tasks), counts["done"]))

    def _card_for(self, tid):
        for i in range(self.list_lay.count()):
            w = self.list_lay.itemAt(i).widget()
            if isinstance(w, TaskCard) and w.task.id == tid:
                return w
        return None

    def _tick_left(self):
        """只更新每张卡片的倒计时文字。"""
        for i in range(self.list_lay.count()):
            w = self.list_lay.itemAt(i).widget()
            if isinstance(w, TaskCard):
                w.refresh_left()

    def _update_header(self, counts):
        hour = datetime.now().hour
        if 5 <= hour < 11:
            hello = "早上好"
        elif 11 <= hour < 13:
            hello = "中午好"
        elif 13 <= hour < 18:
            hello = "下午好"
        else:
            hello = "晚上好"
        self.h1.setText(hello)
        n = counts["today"]
        self.h2.setText("今天有 %d 个待办任务" % n if n else "今天没有待办，放松一下")

    def _visible_tasks(self):
        now = datetime.now()
        q = self.search_text.strip().lower()
        out = []
        for t in self.tasks:
            if q and q not in ("%s %s" % (t.title, t.note)).lower():
                continue
            if self.nav_key == "today":
                if t.done or not t.due or t.due.date() != date.today():
                    continue
            elif self.nav_key == "upcoming":
                if t.done or not t.due or t.due <= now:
                    continue
            elif self.nav_key == "done":
                if not t.done:
                    continue
            out.append(t)
        return out

    def _render_cards(self):
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        rows = self._visible_tasks()
        if not rows:
            self.list_lay.insertWidget(0, self._empty_state())
            return

        for i, task in enumerate(rows):
            card = TaskCard(task)
            card.toggled.connect(self._on_toggle)
            card.opened.connect(self._on_open_task)
            card.deleted.connect(self._on_delete)
            self.list_lay.insertWidget(i, card)

    def _empty_state(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 60, 0, 0)
        v.setSpacing(8)
        ico = QLabel()
        ico.setPixmap(icons.pixmap("inbox", "#c6d0e6", 44, width=1.4))
        ico.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(ico)
        t1 = QLabel("暂无任务")
        t1.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        t1.setStyleSheet("font-size:15px;color:#8b95b2;")
        v.addWidget(t1)
        t2 = QLabel("点右上角「新建任务」添加一条")
        t2.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        t2.setStyleSheet("font-size:12px;color:#aab3c8;")
        v.addWidget(t2)
        return box

    # ================================================================ 交互
    def _on_nav(self, key):
        self.nav_key = key
        for k, item in self.nav.items():
            item.set_selected(k == key)
        if key == "settings":
            self._refresh_build_info()
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
            self._render_cards()

    def _on_search(self, text):
        self.search_text = text
        self._render_cards()

    def _focus_form(self):
        self.show_task_dialog()

    def show_task_dialog(self, task: Task | None = None):
        """新建 / 编辑都走这个弹窗，列表区不再常驻表单。"""
        if not self.isVisible():
            self.show_window()
        if self.stack.currentIndex() != 0:
            self._on_nav("all")
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None
        dlg = TaskDialog(self)
        dlg.submitted.connect(self._on_submit)
        dlg.finished.connect(lambda *_: self._forget_dialog(dlg))
        self.dialog = dlg
        dlg.open_for(task)

    def _forget_dialog(self, dlg):
        if self.dialog is dlg:
            self.dialog = None

    def _on_submit(self, data):
        if data["id"]:
            self.store.update(data["id"], data["title"], data["note"],
                              data["due"], data["repeat"])
        else:
            self.store.add(data["title"], data["note"], data["due"], data["repeat"])
        self.refresh()

    def _on_toggle(self, tid):
        task = self.store.get(tid)
        if not task:
            return
        if task.done:
            self.store.reopen(tid)
        else:
            self.store.complete(tid)
            if task.repeat != "none" and task.due:
                nxt = self.store.get(tid)
                if nxt and nxt.due:
                    self.tray_message("已安排下一次", "%s · %s" %
                                      (nxt.title, fmt_due(nxt.due)))

        # 只改这一张卡片的状态，不重建列表：任务留在原位，不会跳走或消失
        self.tasks = self.store.all()
        self._refresh_counts()
        card = self._card_for(tid)
        latest = self.store.get(tid)
        if card is not None and latest is not None:
            card.set_task(latest)
            # 只有「已完成」这个集合例外：撤销完成后本来就不属于这里，才移出
            if self.nav_key == "done" and not latest.done:
                self._render_cards()

    def _on_open_task(self, tid):
        task = self.store.get(tid)
        if task:
            self.show_task_dialog(task)

    def _on_delete(self, tid):
        task = self.store.get(tid)
        if not task:
            return
        box = QMessageBox(self)
        box.setWindowTitle("删除任务")
        box.setText("确定删除「%s」？" % task.title)
        box.setIcon(QMessageBox.Icon.Question)
        yes = box.addButton("删除", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.store.delete(tid)
            if self.dialog is not None and self.dialog.panel.editing_id == tid:
                self.dialog.close()
            self.refresh()

    def _open_data_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.store.path)))

    def _clear_done(self):
        n = self.store.clear_done()
        self.refresh()
        self.tray_message("已清理", "删除了 %d 条已完成任务" % n)

    # ================================================================ 提醒
    def on_due(self, tid):
        """到点只发一条系统通知，界面上不叠加任何浮窗。"""
        task = self.store.get(tid)
        if not task or task.done:
            return

        if self.tray is not None:
            # Windows 通知自带提示音，不再额外 beep，免得响两次
            self.tray_message("任务提醒", "%s\n%s" % (task.title, fmt_due(task.due)))
        else:
            # 极端情况（没有系统托盘）：把窗口提到前面，至少别错过
            self.show_window()
            if self.store.get_bool("sound", True):
                self._beep()
        self.refresh()

    @staticmethod
    def _beep():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            QApplication.beep()

    def tray_message(self, title, body):
        if self.tray is not None:
            try:
                self.tray.showMessage(title, body,
                                      QSystemTrayIcon.MessageIcon.Information, 6000)
            except Exception:
                pass

    def toggle_pause(self, paused: bool):
        if paused:
            self.scheduler.pause()
        else:
            self.scheduler.resume()

    # ================================================================ 窗口
    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        """关窗口就静默收进托盘，不再弹右下角提示。"""
        if self.tray is not None and self.tray.isVisible():
            self.hide()
        else:
            self.quit_app()

    def quit_app(self):
        self._quitting = True
        if self.dialog is not None:
            try:
                self.dialog.close()
            except Exception:
                pass
            self.dialog = None
        try:
            self.scheduler.stop()
        except Exception:
            pass
        if self.tray is not None:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        if self.store.get_bool("close_to_tray", True) and self.tray is not None:
            e.ignore()
            self.hide_to_tray()
            return
        self.quit_app()
        e.accept()
