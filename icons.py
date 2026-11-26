# -*- coding: utf-8 -*-
"""线性矢量图标：SVG 源串 → 运行时按颜色渲染成 QPixmap / QIcon，不依赖任何图片资源。"""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" '
    'stroke-linejoin="round">{inner}</svg>'
)

_PATHS = {
    "clock": '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.4V12l3.2 1.9"/>',
    "list": '<path d="M8.6 6.5h11M8.6 12h11M8.6 17.5h11"/>'
            '<circle cx="4.4" cy="6.5" r="1.1"/><circle cx="4.4" cy="12" r="1.1"/>'
            '<circle cx="4.4" cy="17.5" r="1.1"/>',
    "calendar": '<rect x="3.4" y="5.2" width="17.2" height="15.2" rx="3.2"/>'
                '<path d="M8.2 3.2v3.6M15.8 3.2v3.6M3.4 10.2h17.2"/>',
    "bell": '<path d="M18.2 15.6V11a6.2 6.2 0 1 0-12.4 0v4.6L4 18.3h16l-1.8-2.7Z"/>'
            '<path d="M9.8 21a2.5 2.5 0 0 0 4.4 0"/>',
    "check-circle": '<circle cx="12" cy="12" r="8.6"/><path d="M8.1 12.2l2.7 2.7 5.1-5.4"/>',
    "check": '<path d="M5 12.6l4.5 4.5L19 6.8"/>',
    "sliders": '<path d="M4 7.2h8.2M17.4 7.2H20M4 16.8h3.4M12.6 16.8H20"/>'
               '<circle cx="14.8" cy="7.2" r="2.2"/><circle cx="10" cy="16.8" r="2.2"/>',
    "search": '<circle cx="11" cy="11" r="6.3"/><path d="M15.7 15.7l4.2 4.2"/>',
    "plus": '<path d="M12 5.2v13.6M5.2 12h13.6"/>',
    "close": '<path d="M6.4 6.4l11.2 11.2M17.6 6.4L6.4 17.6"/>',
    "trash": '<path d="M4.6 7h14.8M9.6 7V4.9h4.8V7M6.8 7l.9 12.6h8.6L17.2 7"/>',
    "minus": '<path d="M5.4 12h13.2"/>',
    "chevron-down": '<path d="M6.2 9.4l5.8 5.8 5.8-5.8"/>',
    "inbox": '<path d="M3.6 5.6h16.8v8.6l-3.1 5.2H6.7l-3.1-5.2V5.6Z"/>'
             '<path d="M3.6 14.2h4.1l1.4 2.4h5.8l1.4-2.4h4.1"/>',
    "folder": '<path d="M3.4 7.2a2 2 0 0 1 2-2h3.8l2 2.4h7.4a2 2 0 0 1 2 2v7.2a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V7.2Z"/>',
    "info": '<circle cx="12" cy="12" r="8.6"/><path d="M12 11v5.2"/>'
            '<circle cx="12" cy="7.9" r="0.9" fill="{c}" stroke="none"/>',
}

_cache = {}


def pixmap(name, color, size=16, width=1.7, dpr=2.0):
    """按名字与颜色生成矢量图标位图（内部按 2x 渲染，高分屏不虚）。"""
    key = (name, color, size, width, dpr)
    hit = _cache.get(key)
    if hit is not None:
        return hit

    inner = _PATHS.get(name)
    if inner is None:
        raise KeyError("unknown icon: %s" % name)
    svg = _TEMPLATE.format(c=color, w=width, inner=inner.replace("{c}", color))
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)

    _cache[key] = pm
    return pm


def icon(name, color, size=16, width=1.7):
    return QIcon(pixmap(name, color, size, width))


def app_icon(color="#3468f5"):
    """多尺寸拼一个窗口 / 托盘图标。"""
    ico = QIcon()
    for s in (16, 20, 24, 32, 48, 64, 128):
        ico.addPixmap(pixmap("clock", color, s, width=1.9))
    return ico
