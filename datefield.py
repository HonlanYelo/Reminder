# -*- coding: utf-8 -*-
"""日期时间选择：一个显示框，点开只选时/分（日期沿用当天）。"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QListWidget, QPushButton, QVBoxLayout)

import icons
import theme

LIST_QSS = (
    "QListWidget{background:#f8fafe;border:1px solid #e6ebf8;border-radius:10px;"
    "padding:0;outline:0;font-size:13px;color:#3c4866;}"
    "QListWidget::item{height:28px;border-radius:7px;margin:1px 5px 1px 4px;}"
    "QListWidget::item:hover{background:#eef3ff;color:%s;}"
    "QListWidget::item:selected{background:%s;color:#ffffff;}"
    "QListWidget QScrollBar:vertical{background:transparent;width:5px;margin:3px 1px;}"
    "QListWidget QScrollBar::handle:vertical{background:#dfe6f4;border-radius:2px;"
    "min-height:24px;}"
    "QListWidget QScrollBar::handle:vertical:hover{background:#c8d4e8;}"
    "QListWidget QScrollBar::add-line:vertical,QListWidget QScrollBar::sub-line:vertical"
    "{height:0;}"
    "QListWidget QScrollBar::add-page:vertical,QListWidget QScrollBar::sub-page:vertical"
    "{background:transparent;}"
    % (theme.ACCENT, theme.ACCENT)
)

ROW_H = 30  # 28 + 上下各 1px 外边距，滚动时按整行对齐
SNAP_ROW = 2  # 选中项固定显示在列表第 3 行，两列齐平


def fmt_when(dt: datetime) -> str:
    """今天 09:30 / 明天 09:30 / 12月03日 09:30"""
    today = date.today()
    d = dt.date()
    hm = dt.strftime("%H:%M")
    if d == today:
        return "今天 " + hm
    if d == today + timedelta(days=1):
        return "明天 " + hm
    if d == today + timedelta(days=2):
        return "后天 " + hm
    if d.year == today.year:
        return dt.strftime("%m月%d日 ") + hm
    return dt.strftime("%Y年%m月%d日 ") + hm


class TimePopup(QFrame):
    """只有「时」「分」两列的浮层，确定后回传 datetime（日期沿用原值）。"""

    picked = Signal(object)

    def __init__(self, value: datetime, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(224)
        self._by_pick = False
        self._date = value.date()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 12)
        outer.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("PickerCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(24, 40, 78, 70))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(0)

        self.hint = QLabel(card)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.hint.setStyleSheet("font-size:22px;font-weight:700;color:%s;" % theme.INK)
        v.addWidget(self.hint)
        v.addSpacing(11)

        cols = QHBoxLayout()
        cols.setSpacing(8)
        for title, items, current, attr in (("时", ["%02d" % h for h in range(24)],
                                             value.hour, "hours"),
                                            ("分", ["%02d" % m for m in range(60)],
                                             value.minute, "mins")):
            col = QVBoxLayout()
            col.setSpacing(4)
            lb = QLabel(title, card)
            lb.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lb.setStyleSheet("font-size:12px;color:#9aa4bf;")
            col.addWidget(lb)
            wid = self._mini_list(card, items, current)
            setattr(self, attr, wid)
            col.addWidget(wid)
            cols.addLayout(col)
        v.addLayout(cols)
        v.addSpacing(13)

        # 底部
        foot = QHBoxLayout()
        foot.setSpacing(8)
        cancel = QPushButton("取消", card)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedHeight(34)
        cancel.setStyleSheet(
            "QPushButton{background:#f2f5fd;border:1px solid #e3e9f9;border-radius:10px;"
            "color:#4a5679;font-size:13px;}"
            "QPushButton:hover{background:#e9eeff;color:%s;}" % theme.ACCENT
        )
        cancel.clicked.connect(self.close)
        ok = QPushButton("确定", card)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setFixedHeight(34)
        ok.setStyleSheet(
            "QPushButton{background:%s;border:0;border-radius:10px;color:#ffffff;"
            "font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#2f5fe6;}" % theme.ACCENT
        )
        ok.clicked.connect(self._apply)
        foot.addWidget(cancel, 1)
        foot.addWidget(ok, 1)
        v.addLayout(foot)

        self._sync_hint()

    # ------------------------------------------------------------------
    def _mini_list(self, parent, items, current):
        w = QListWidget(parent)
        w.setStyleSheet(LIST_QSS)
        w.setFixedWidth(84)
        w.setFixedHeight(ROW_H * 6 + 2)
        w.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        w.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w.addItems(items)
        for i in range(w.count()):
            w.item(i).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        cur = w.item(max(0, min(len(items) - 1, current)))
        w.setCurrentItem(cur)
        w.scrollToItem(cur, QListWidget.ScrollHint.PositionAtCenter)
        w.currentRowChanged.connect(self._sync_hint)
        return w

    def showEvent(self, e):
        super().showEvent(e)
        # 两列都让选中项落在同一视觉行（第 3 行），行与行对齐、上下不切半格
        for w in (self.hours, self.mins):
            bar = w.verticalScrollBar()
            bar.setValue(max(0, (w.currentRow() - SNAP_ROW) * ROW_H))

    def hideEvent(self, e):
        super().hideEvent(e)
        # 不是“确定”关掉的，说明是被外面那一下点掉的：
        # 通知字段别把重放过来的同一次点击又当成“打开”
        if not self._by_pick:
            owner = self.parent()
            if owner is not None and hasattr(owner, "_guard_until"):
                owner._guard_until = time.monotonic() + 0.2

    def set_value(self, value: datetime):
        """复用同一个浮层，打开前把内容重置到当前值（日期沿用，只重置时分）。"""
        self._date = value.date()
        self.hours.setCurrentRow(value.hour)
        self.mins.setCurrentRow(value.minute)
        self._sync_hint()

    def _sync_hint(self):
        self.hint.setText("%02d:%02d" % (max(0, self.hours.currentRow()),
                                         max(0, self.mins.currentRow())))

    def _current(self) -> datetime:
        return datetime(self._date.year, self._date.month, self._date.day,
                        max(0, self.hours.currentRow()), max(0, self.mins.currentRow()))

    def _apply(self):
        self._by_pick = True
        self.picked.emit(self._current())
        self.close()
        self._by_pick = False


class DateTimeField(QFrame):
    """只读显示框，点击弹出 TimePopup。"""

    picked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DateTimeField")
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._value = datetime.now().replace(second=0, microsecond=0) + timedelta(hours=1)
        self._popup: TimePopup | None = None
        self._guard_until = 0.0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        self.ico = QLabel(self)
        self.ico.setFixedSize(15, 15)
        lay.addWidget(self.ico)

        self.text = QLabel(self)
        self.text.setStyleSheet("font-size:13px;color:%s;" % theme.TEXT)
        lay.addWidget(self.text, 1)

        self.arrow = QLabel(self)
        self.arrow.setFixedSize(13, 13)
        self.arrow.setPixmap(icons.pixmap("chevron-down", "#a8b2c8", 13, width=2.0))
        lay.addWidget(self.arrow)

        self._restyle()
        self._refresh()

    # ------------------------------------------------------------------
    def set_value(self, dt: datetime):
        self._value = dt.replace(second=0, microsecond=0)
        self._refresh()

    def value(self) -> datetime:
        return self._value

    def _refresh(self):
        self.text.setText(fmt_when(self._value))

    def _restyle(self):
        on = self.isEnabled()
        self.ico.setPixmap(icons.pixmap("calendar", theme.ACCENT if on else "#b6c0d4", 15,
                                        width=1.7))
        self.text.setStyleSheet(
            "font-size:13px;color:%s;" % (theme.TEXT if on else "#aab3c8"))
        self.arrow.setVisible(on)
        self.setProperty("off", not on)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor if on
                       else Qt.CursorShape.ArrowCursor)

    def setEnabled(self, on):
        super().setEnabled(on)
        if not on and self._popup is not None and self._popup.isVisible():
            self._popup.close()
        self._restyle()

    def _open_popup(self):
        pop = self._popup
        if pop is None:
            pop = TimePopup(self._value, self)
            pop.picked.connect(self._take)
            self._popup = pop
        pop.set_value(self._value)
        pop.adjustSize()
        pop.move(self._popup_pos(pop.size()))
        pop.show()

    def _popup_pos(self, size: QSize) -> QPoint:
        anchor = self.mapToGlobal(QPoint(0, 0))
        scr = self.screen().availableGeometry()
        # 右对齐到字段，像下拉一样展开
        x = anchor.x() + self.width() - size.width()
        x = min(max(scr.left() + 4, x), scr.right() - size.width())
        y = anchor.y() + self.height() + 6
        if y + size.height() > scr.bottom():
            y = anchor.y() - size.height() - 6
        return QPoint(x, max(scr.top() + 4, y))

    def _take(self, dt: datetime):
        self.set_value(dt)
        self.picked.emit(dt)

    def mousePressEvent(self, e):
        # 浮层开着时点自己 = 收起（按下的瞬间就处理，不等抬起）
        if e.button() == Qt.MouseButton.LeftButton and self._popup is not None \
                and self._popup.isVisible():
            self._popup.close()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return
        if not self.rect().contains(e.position().toPoint()):
            return
        if self._popup is not None and self._popup.isVisible():
            self._popup.close()
            return
        if time.monotonic() < self._guard_until:
            # 这一下就是刚才关掉浮层的那次点击被重放回来的，别再打开
            self._guard_until = 0.0
            return
        self._open_popup()
