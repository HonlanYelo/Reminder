# -*- coding: utf-8 -*-
"""新建 / 编辑任务的弹窗：遮罩 + 居中卡片，点外部或 Esc 关闭。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, Signal)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

import theme
from datefield import DateTimeField
from storage import REPEATS, Task
from widgets import IconButton

PANEL_W = 384


class DropdownBox(QComboBox):
    """再点一次要真的收起。

    Qt 把「关掉列表的那一次点击」重放给了下拉本身，默认实现会紧接着又来一次
    showPopup，于是怎么点都关不掉。这里加一道 0.2 秒的闸门把重放的那一下吃掉。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._guard_until = 0.0

    def hidePopup(self):
        self._guard_until = time.monotonic() + 0.2
        super().hidePopup()

    def _guarded(self) -> bool:
        return time.monotonic() < self._guard_until

    def mousePressEvent(self, e):
        if self.view().isVisible():
            self.hidePopup()
            e.accept()
            return
        if self._guarded():
            self._guard_until = 0.0
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self._guarded():
            self._guard_until = 0.0
            e.accept()
            return
        super().mouseReleaseEvent(e)



class TaskPanel(QFrame):
    """任务表单本体（不含窗口壳）。"""

    submitted = Signal(dict)
    dismissed = Signal()

    def __init__(self, parent=None, width=PANEL_W):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFixedWidth(width)
        self.editing_id: int | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.head_title = QLabel("新建任务")
        self.head_title.setStyleSheet("font-size:16px;font-weight:700;color:%s;" % theme.INK)
        head.addWidget(self.head_title)
        head.addStretch(1)
        self.btn_close = IconButton("close", "#a8b2c8", 14, 26, hover_bg="#f2f5fd", parent=self)
        self.btn_close.setToolTip("关闭")
        self.btn_close.clicked.connect(self.dismissed.emit)
        head.addWidget(self.btn_close)
        lay.addLayout(head)
        lay.addSpacing(18)

        self.title = QLineEdit()
        self.title.setObjectName("Field")
        self.title.setPlaceholderText("输入任务内容…")
        self.title.setFixedHeight(40)
        lay.addWidget(self.title)
        lay.addSpacing(14)

        # 「提醒」开关放在标签行右侧，让下面的时间框和别的输入框左右都对齐
        time_head = QHBoxLayout()
        time_head.setSpacing(8)
        time_head.addWidget(self._label("提醒时间"))
        time_head.addStretch(1)
        self.with_time = QCheckBox("提醒")
        self.with_time.setChecked(True)
        self.with_time.setStyleSheet("font-size:12px;color:#5b6787;")
        self.with_time.toggled.connect(self._toggle_time)
        time_head.addWidget(self.with_time, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(time_head)
        lay.addSpacing(7)
        self.due = DateTimeField(self)
        lay.addWidget(self.due)
        lay.addSpacing(14)

        lay.addWidget(self._label("重复"))
        lay.addSpacing(7)
        self.repeat = DropdownBox()
        self.repeat.setObjectName("Field")
        self.repeat.setFixedHeight(40)
        for key, text in REPEATS:
            self.repeat.addItem(text, key)
        lay.addWidget(self.repeat)
        lay.addSpacing(14)

        lay.addWidget(self._label("备注"))
        lay.addSpacing(7)
        self.note = QPlainTextEdit()
        self.note.setObjectName("Field")
        self.note.setPlaceholderText("补充说明（可选）")
        self.note.setFixedHeight(84)
        lay.addWidget(self.note)
        lay.addSpacing(20)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("Ghost")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.dismissed.emit)
        btns.addWidget(self.btn_cancel, 1)

        self.btn_save = QPushButton("保存任务")
        self.btn_save.setObjectName("Primary")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._submit)
        btns.addWidget(self.btn_save, 1)
        lay.addLayout(btns)

        self.title.returnPressed.connect(self._submit)
        self.reset()

    # ------------------------------------------------------------------
    @staticmethod
    def _label(text):
        lb = QLabel(text)
        lb.setStyleSheet("font-size:12px;color:#6b7695;")
        return lb

    def _toggle_time(self, on):
        self.due.setEnabled(on)

    def reset(self):
        self.editing_id = None
        self.head_title.setText("新建任务")
        self.btn_save.setText("保存任务")
        self.title.clear()
        self.note.clear()
        self.repeat.setCurrentIndex(0)
        self.with_time.setChecked(True)

        base = datetime.now() + timedelta(hours=1)
        base = base.replace(minute=base.minute - base.minute % 5, second=0, microsecond=0)
        self.due.set_value(base)

    def load(self, task: Task):
        self.editing_id = task.id
        self.head_title.setText("编辑任务")
        self.btn_save.setText("保存修改")
        self.title.setText(task.title)
        self.note.setPlainText(task.note)
        self.with_time.setChecked(task.due is not None)
        if task.due:
            self.due.set_value(task.due)
        idx = max(0, self.repeat.findData(task.repeat))
        self.repeat.setCurrentIndex(idx)
        self.title.setFocus()
        self.title.selectAll()

    def _values(self) -> dict | None:
        text = self.title.text().strip()
        if not text:
            self.title.setFocus()
            return None
        due = self.due.value() if self.with_time.isChecked() else None
        return {
            "id": self.editing_id,
            "title": text,
            "note": self.note.toPlainText().strip(),
            "due": due,
            "repeat": self.repeat.currentData() if due else "none",
        }

    def _submit(self):
        data = self._values()
        if data:
            self.submitted.emit(data)


class TaskDialog(QDialog):
    """浮在主窗口上的任务表单：半透明遮罩 + 居中卡片。"""

    submitted = Signal(dict)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(0)
        lay.addStretch(1)

        row = QHBoxLayout()
        row.setSpacing(0)
        row.addStretch(1)
        self.panel = TaskPanel(self)
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(18, 32, 66, 95))
        self.panel.setGraphicsEffect(shadow)
        row.addWidget(self.panel)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

        self.panel.submitted.connect(self._on_submit)
        self.panel.dismissed.connect(self.reject)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(170)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setWindowOpacity(0.0)

    # ------------------------------------------------------------------
    def open_for(self, task: Task | None = None) -> None:
        if task is None:
            self.panel.reset()
        else:
            self.panel.load(task)
        self.show()

    def showEvent(self, e):
        self._sync_geometry()
        super().showEvent(e)
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.start()
        self.panel.title.setFocus()

    def _sync_geometry(self):
        win = self.parentWidget()
        card = getattr(win, "card", None)
        if card is not None and card.width() > 200:
            self.setGeometry(QRect(card.mapToGlobal(QPoint(0, 0)), card.size()))
        elif win is not None:
            self.setGeometry(win.frameGeometry())

    def _on_submit(self, data):
        self.submitted.emit(data)
        self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if not self.panel.geometry().contains(e.position().toPoint()):
            self.reject()
            return
        super().mousePressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(16, 27, 52, 104))
        r = self.rect()
        p.drawRoundedRect(QRect(r.left(), r.top(), r.width() - 1, r.height() - 1), 18, 18)
