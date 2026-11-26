# -*- coding: utf-8 -*-
"""启动过渡画面：小卡片 + 进度条，主窗口就绪后淡出。

纯 QPainter 自绘，不依赖全局 QSS —— 它要在样式表应用之前就先亮出来。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

import icons
import theme

W, H = 360, 208
PAD = 10                      # 四周留给阴影的边距
RADIUS = 18
MIN_SHOW_MS = 320             # 文字出现后至少停留多久，够看清再过渡


class Splash(QWidget):
    def __init__(self):
        super().__init__(None,
                         Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(W, H)

        self._progress = 0.05
        self._status = "正在启动…"
        self._shown_at = 0.0
        self._text_at = 0.0
        self._text_ready = False
        self._anim: QPropertyAnimation | None = None
        self._icon = icons.pixmap("clock", theme.ACCENT, 42, width=1.7)

        screen = QApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            self.move(g.center() - self.rect().center())

    # ------------------------------------------------------------- 对外接口
    def start(self) -> None:
        """直接显示骨架：这一步只画图形，几十毫秒就能上屏。

        这里不做透明度淡入 —— 紧接着的字体初始化会占满主线程，
        动画一帧都推不动，窗口反而会卡在全透明状态。
        """
        self._shown_at = time.perf_counter()
        self.show()
        QApplication.processEvents()

    def reveal_text(self) -> None:
        """补上文字。首次渲染文字要初始化字体引擎（约一秒），
        让这段时间花在卡片已经可见之后，不要变成一片空白。"""
        if self._text_ready:
            return
        self._text_ready = True
        self.update()
        QApplication.processEvents()
        # 等文字真正画上去之后再开始计时停留
        self._text_at = time.perf_counter()

    def rest_ms(self) -> int:
        """还要停留多久才到最短展示时长（从文字出现算起）。"""
        base = self._text_at or self._shown_at
        if not base:
            return 0
        elapsed = (time.perf_counter() - base) * 1000
        return max(0, int(MIN_SHOW_MS - elapsed))

    def set_progress(self, value: float, status: str | None = None) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        if status:
            self._status = status
        self.update()

    def finish(self) -> None:
        """淡出，结束后关闭。"""
        self.set_progress(1.0, "准备就绪")
        anim = self._fade(1.0, 0.0, 200)
        anim.finished.connect(self.close)
        anim.start()
        self._anim = anim

    # ---------------------------------------------------------------- 内部
    def _fade(self, start: float, end: float, ms: int) -> QPropertyAnimation:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        card = QRectF(PAD, PAD, W - PAD * 2, H - PAD * 2)

        # 柔和投影：由外向内叠若干层半透明圆角矩形
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(7, 0, -1):
            p.setBrush(QColor(41, 62, 112, 5))
            p.drawRoundedRect(card.adjusted(-i, -i + 2, i, i + 2), RADIUS + i, RADIUS + i)

        # 卡片底
        bg = QLinearGradient(card.topLeft(), card.bottomRight())
        bg.setColorAt(0.0, QColor("#ffffff"))
        bg.setColorAt(1.0, QColor("#f2f6ff"))
        p.setBrush(bg)
        p.setPen(QPen(QColor(231, 237, 251), 1))
        p.drawRoundedRect(card, RADIUS, RADIUS)

        cx = card.center().x()

        # 图标
        iw = self._icon.width() / self._icon.devicePixelRatio()
        p.drawPixmap(int(cx - iw / 2), int(card.top() + 34), self._icon)

        # 文字要等字体引擎初始化，第一次要近一秒 —— 骨架帧先不画，
        # 卡片立刻可见，随后 reveal_text() 再把字补上
        if self._text_ready:
            p.setPen(QColor(theme.INK))
            f = QFont()
            f.setFamilies(["Microsoft YaHei UI", "Segoe UI"])
            f.setPixelSize(20)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(card.left(), card.top() + 86, card.width(), 30),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                       "小提醒")

            p.setPen(QColor("#6f7d9c"))
            f2 = QFont(f)
            f2.setPixelSize(12)
            f2.setBold(False)
            p.setFont(f2)
            p.drawText(QRectF(card.left(), card.top() + 128, card.width(), 18),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                       self._status)
        else:
            # 文字还没准备好：用两条浅色占位条，看起来是骨架屏而不是缺字
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e9eefb"))
            p.drawRoundedRect(QRectF(cx - 48, card.top() + 96, 96, 11), 5.5, 5.5)
            p.setBrush(QColor("#eef2fc"))
            p.drawRoundedRect(QRectF(cx - 66, card.top() + 133, 132, 8), 4, 4)

        # 进度条
        bar_w, bar_h = 208.0, 5.0
        bx = cx - bar_w / 2
        by = card.top() + 164
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e6ecfa"))
        p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), bar_h / 2, bar_h / 2)

        filled = max(bar_h, bar_w * self._progress)
        grad = QLinearGradient(bx, by, bx + filled, by)
        grad.setColorAt(0.0, QColor(theme.ACCENT))
        grad.setColorAt(1.0, QColor("#7ba2ff"))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(bx, by, filled, bar_h), bar_h / 2, bar_h / 2)

        p.end()
