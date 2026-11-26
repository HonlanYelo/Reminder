# -*- coding: utf-8 -*-
"""自绘控件：导航项、任务卡片、图标按钮、标题栏。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

import icons
import theme
from storage import REPEAT_LABELS, Task, fmt_due, fmt_left


# --------------------------------------------------------------------- 文本
class ElidedLabel(QWidget):
    """单行文本，空间不够自动出省略号。"""

    def __init__(self, text="", color="#26324f", px=13, bold=False, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = QColor(color)
        f = QFont()
        f.setPixelSize(px)
        f.setBold(bold)
        self.setFont(f)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def sizeHint(self):
        return QSize(40, QFontMetrics(self.font()).height() + 2)

    def minimumSizeHint(self):
        return QSize(0, QFontMetrics(self.font()).height() + 2)

    def set_text(self, text):
        if text != self._text:
            self._text = text
            self.update()

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.setFont(self.font())
        p.setPen(QPen(self._color))
        fm = QFontMetrics(self.font())
        txt = fm.elidedText(self._text, Qt.TextElideMode.ElideRight, max(0, self.width()))
        p.drawText(self.rect(),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), txt)


# --------------------------------------------------------------------- 按钮
class IconButton(QPushButton):
    def __init__(self, name, color="#8b95ad", size=15, box=28,
                 hover_bg="#eef3ff", parent=None):
        super().__init__(parent)
        self.setFixedSize(box, box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(icons.icon(name, color, size))
        self.setIconSize(QSize(size, size))
        self.setStyleSheet(
            "QPushButton{border:0;border-radius:%dpx;background:transparent;}"
            "QPushButton:hover{background:%s;}" % (box // 2, hover_bg)
        )


# --------------------------------------------------------------------- 导航
class NavItem(QWidget):
    clicked = Signal(str)

    def __init__(self, key, label, icon_name, parent=None):
        super().__init__(parent)
        self.key = key
        self.label = label
        self.icon_name = icon_name
        self.count = None
        self.selected = False
        self.hover = False
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_count(self, n):
        self.count = n
        self.update()

    def set_selected(self, on):
        if self.selected != on:
            self.selected = on
            self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.key)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(0, 1, 0, -1)
        if self.selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.ACCENT_SOFT))
            p.drawRoundedRect(r, 12, 12)
            p.setBrush(QColor(theme.ACCENT))
            p.drawRoundedRect(QRect(r.left(), r.top() + 10, 3, r.height() - 20), 1.5, 1.5)
        elif self.hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 170))
            p.drawRoundedRect(r, 12, 12)

        color = theme.ACCENT if self.selected else "#4a5679"
        pm = icons.pixmap(self.icon_name, color, 18, width=1.7)
        p.drawPixmap(15, (self.height() - 18) // 2, pm)

        f = QFont(self.font())
        f.setPixelSize(15)
        f.setBold(self.selected)
        p.setFont(f)
        p.setPen(QColor(theme.ACCENT if self.selected else "#2b3857"))
        p.drawText(QRect(44, 0, max(10, self.width() - 80), self.height()),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self.label)

        if self.count is not None:
            txt = str(self.count)
            fm = QFontMetrics(self.font())
            bw = max(23, fm.horizontalAdvance(txt) + 15)
            br = QRect(self.width() - bw - 9, (self.height() - 22) // 2, bw, 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.ACCENT if self.selected else "#e4eaf9"))
            p.drawRoundedRect(br, 11, 11)
            f2 = QFont(self.font())
            f2.setPixelSize(11)
            f2.setBold(self.selected)
            p.setFont(f2)
            p.setPen(QColor("#ffffff" if self.selected else "#6b7695"))
            p.drawText(br, int(Qt.AlignmentFlag.AlignCenter), txt)


# --------------------------------------------------------------------- 卡片
class TaskCard(QFrame):
    toggled = Signal(int)
    opened = Signal(int)
    deleted = Signal(int)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("TaskCard")
        self.setFixedHeight(88)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 14, 16, 14)
        root.setSpacing(0)

        self.stripe = QFrame(self)
        self.stripe.setFixedWidth(4)
        root.addWidget(self.stripe)
        root.addSpacing(20)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)
        self.title = ElidedLabel(task.title or "未命名任务", px=16, bold=True)
        self.note = ElidedLabel(task.note or "无备注", px=13, color="#8b95b2")
        info.addStretch(1)
        info.addWidget(self.title)
        info.addWidget(self.note)
        info.addStretch(1)
        root.addLayout(info, 1)

        meta_box = QWidget(self)
        meta_box.setFixedWidth(132)
        meta = QVBoxLayout(meta_box)
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(3)
        self.time = QLabel()
        self.time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.left = QLabel()          # 还剩多久提醒
        self.left.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.repeat = QLabel(REPEAT_LABELS.get(task.repeat, "不重复"))
        self.repeat.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meta.addStretch(1)
        meta.addWidget(self.time)
        meta.addWidget(self.left)
        meta.addWidget(self.repeat)
        meta.addStretch(1)
        root.addWidget(meta_box)
        root.addSpacing(16)

        # 手动确认完成：右侧胶囊按钮，完成后原地改状态，不移出列表
        self.done_btn = QPushButton(self)
        self.done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_btn.setFixedSize(84, 30)
        self.done_btn.setIconSize(QSize(13, 13))
        self.done_btn.clicked.connect(lambda: self.toggled.emit(self.task.id))
        root.addWidget(self.done_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addSpacing(8)
        self.del_btn = IconButton("trash", "#c3ccdd", 16, 28, hover_bg="#ffeaea", parent=self)
        self.del_btn.setToolTip("删除任务")
        self.del_btn.clicked.connect(lambda: self.deleted.emit(self.task.id))
        root.addWidget(self.del_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._apply_state()

    def set_task(self, task: Task):
        """原地换掉卡片绑定的任务数据，只重绘状态，不重建控件。"""
        self.task = task
        self._apply_state()

    def refresh_left(self):
        """定时刷新「还剩多久」，顺带更新逾期配色，不碰按钮和文案。"""
        self._paint_due(datetime.now())

    # ------------------------------------------------------------------
    def _paint_due(self, now):
        t = self.task
        done = t.done
        overdue = bool(t.due and not done and t.due < now)

        self.time.setText(fmt_due(t.due))
        self.time.setStyleSheet(
            "font-size:13px;color:%s;" %
            ("#b3bacb" if done else (theme.RED if overdue else theme.ACCENT))
        )

        if done:
            # 已完成：第三行换成完成时间，保持三行结构，右侧不会缺一块
            self.left.setText("完成于 " + t.done_at.strftime("%m-%d %H:%M")
                              if t.done_at else "已完成")
            self.left.setStyleSheet("font-size:12px;color:#b9c1d2;")
            return
        if not t.due:
            self.left.setText("")
            self.left.setStyleSheet("font-size:12px;color:#c3c9d8;")
            return
        secs = (t.due - now).total_seconds()
        if secs <= 0:
            color = theme.RED
        elif secs <= 600:
            color = theme.AMBER
        else:
            color = "#98a2bb"
        self.left.setText(fmt_left(t.due, now))
        self.left.setStyleSheet("font-size:12px;font-weight:600;color:%s;" % color)

    def _apply_state(self):
        t = self.task
        done = t.done

        self.stripe.setStyleSheet(
            "background-color:%s;border-radius:2px;" % ("#d5ddec" if done else theme.ACCENT)
        )
        self.title.set_color("#a2aabc" if done else theme.INK)
        f = self.title.font()
        f.setStrikeOut(done)
        self.title.setFont(f)
        self.title.set_text(t.title or "未命名任务")
        self.note.set_color("#b3bacb" if done else "#8b95b2")
        self.note.set_text(t.note or "无备注")

        self._paint_due(datetime.now())
        self.repeat.setStyleSheet(
            "font-size:12px;color:%s;" % ("#c3c9d8" if done else "#98a2bb")
        )
        self.repeat.setText(REPEAT_LABELS.get(t.repeat, "不重复"))

        if done:
            self.done_btn.setText("已完成")
            self.done_btn.setIcon(icons.icon("check", "#17a06a", 13, width=2.6))
            self.done_btn.setStyleSheet(
                "QPushButton{background:#eaf8f2;border:1px solid #cdeddf;border-radius:10px;"
                "color:#17a06a;font-size:13px;font-weight:600;}"
                "QPushButton:hover{background:#dcf4ea;border-color:#a6e2cb;}"
            )
            self.done_btn.setToolTip("点击撤销完成")
        else:
            self.done_btn.setText("完成")
            self.done_btn.setIcon(icons.icon("check", "#8a95b0", 13, width=2.4))
            self.done_btn.setStyleSheet(
                "QPushButton{background:#f7f9ff;border:1px solid #e2e8f8;border-radius:10px;"
                "color:#5c6a8c;font-size:13px;}"
                "QPushButton:hover{background:#eef3ff;border-color:#3468f5;color:#3468f5;}"
            )
            self.done_btn.setToolTip("点击标记为已完成")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.opened.emit(self.task.id)


# --------------------------------------------------------------------- 顶栏
class TopBar(QWidget):
    minimize = Signal()
    close = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._drag = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 9, 12, 0)
        lay.setSpacing(2)
        lay.addStretch(1)
        self.btn_min = IconButton("minus", "#8b95ad", 16, 28, hover_bg="#ffffff", parent=self)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.minimize.emit)
        self.btn_close = IconButton("close", "#8b95ad", 14, 28, hover_bg="#ffe6e6", parent=self)
        self.btn_close.setToolTip("隐藏到托盘")
        self.btn_close.clicked.connect(self.close.emit)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_close)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
