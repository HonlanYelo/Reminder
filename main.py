# -*- coding: utf-8 -*-
"""小提醒 · 入口
PySide6 + SQLite + 系统托盘。双击本文件、或 `python main.py` 均可启动；
若当前解释器没有 PySide6，会自动切到同目录的 .venv 重新拉起。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_VENV_DIR = os.path.join(_HERE, ".venv")
_VENV_PYW = os.path.join(_VENV_DIR, "Scripts", "pythonw.exe")
_VENV_PY = os.path.join(_VENV_DIR, "Scripts", "python.exe")
_IN_VENV = os.path.normcase(os.path.abspath(sys.executable)).startswith(
    os.path.normcase(_VENV_DIR))


def _relaunch_in_venv() -> None:
    """用项目自带 .venv 重新拉起自己。

    这样双击 main.py、或在任意 python 下运行都能打开，且不往系统环境装东西。
    """
    exe = _VENV_PYW if os.path.exists(_VENV_PYW) else _VENV_PY
    import subprocess
    subprocess.Popen(
        [exe, os.path.abspath(__file__)] + sys.argv[1:],
        cwd=_HERE,
        close_fds=True,
    )
    sys.exit(0)


# 不在项目环境里就直接切过去，省掉一次注定失败的 import 尝试（约 100~200ms）
if not _IN_VENV and (os.path.exists(_VENV_PYW) or os.path.exists(_VENV_PY)):
    _relaunch_in_venv()


try:
    from PySide6.QtCore import QEventLoop, QEasingCurve, QPropertyAnimation, QTimer
    from PySide6.QtGui import QColor, QFont, QPalette
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
except ModuleNotFoundError:
    if sys.stderr is not None:
        sys.stderr.write(
            "当前 Python 缺少 PySide6：\n"
            "  %s (Python %s)\n\n"
            "项目内的 .venv 不存在或不可用，请先重建：\n"
            "  python -m venv .venv\n"
            "  .venv\\Scripts\\python.exe -m pip install PySide6\n"
            % (sys.executable, ".".join(map(str, sys.version_info[:3])))
        )
    sys.exit(1)

import icons
import theme
from mainwindow import APP_TITLE, MainWindow
from splash import Splash

SINGLETON = "ReminderDesk.PySide6.v2"


def _notify_running_instance() -> bool:
    """已有实例在跑时，通知它把窗口显示出来。"""
    sock = QLocalSocket()
    sock.connectToServer(SINGLETON)
    if sock.waitForConnected(250):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(250)
        sock.disconnectFromServer()
        return True
    return False


def _build_tray(app: QApplication, win: MainWindow) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(icons.app_icon(), win)
    tray.setToolTip("%s · 后台提醒中" % APP_TITLE)

    menu = QMenu()
    act_open = menu.addAction("打开主界面")
    act_open.triggered.connect(win.show_window)
    act_new = menu.addAction("新建任务")
    act_new.triggered.connect(lambda: (win.show_window(), win._focus_form()))
    menu.addSeparator()
    act_pause = menu.addAction("暂停提醒")
    act_pause.setCheckable(True)
    act_pause.toggled.connect(lambda on: win.toggle_pause(on))
    menu.addSeparator()
    act_quit = menu.addAction("退出")
    act_quit.triggered.connect(win.quit_app)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: win.show_window()
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick)
        else None
    )
    tray.show()
    return tray


def _reveal(win: MainWindow, splash: Splash) -> None:
    """主窗口淡入，启动画面同时淡出。"""
    anim = QPropertyAnimation(win, b"windowOpacity", win)
    anim.setDuration(260)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: win.setWindowOpacity(1.0))
    anim.start()
    splash.finish()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    # 统一浅色调，避免系统深色模式把原生控件染黑
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#edf1fd"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Text, QColor(theme.INK))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(theme.INK))
    pal.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(theme.TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(theme.ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "PingFang SC"])
    font.setPixelSize(13)
    app.setFont(font)

    selftest = "--selftest" in sys.argv
    if not selftest and _notify_running_instance():
        return 0

    # 启动过渡：主窗口构建要一秒左右，先把启动卡片亮出来，就绪后再淡入
    splash: Splash | None = None
    on_stage = None
    if not selftest:
        splash = Splash()
        splash.start()          # 先出卡片骨架，几十毫秒可见
        splash.reveal_text()    # 再补文字（首次要初始化字体引擎）

        def on_stage(value: float, text: str | None = None) -> None:
            splash.set_progress(value, text)
            # 构建期间主线程是占满的，这里主动放行一帧，进度条才动得起来
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    # 全局样式表会触发一遍控件 polish，放到启动画面之后套，免得拖慢第一帧
    app.setStyleSheet(theme.qss())

    win = MainWindow(on_stage=on_stage)
    tray = _build_tray(app, win)
    win.tray = tray
    if tray is None:
        app.setQuitOnLastWindowClosed(True)

    if splash is not None:
        win.setWindowOpacity(0.0)
    win.show()
    win.raise_()
    if splash is not None:
        QTimer.singleShot(splash.rest_ms(), lambda: _reveal(win, splash))
        # 兜底：万一淡入动画没跑起来，也不能留一个全透明的窗口
        QTimer.singleShot(3000, lambda: win.setWindowOpacity(1.0))

    # 单实例：后续启动只唤起窗口
    server = QLocalServer()
    QLocalServer.removeServer(SINGLETON)
    if server.listen(SINGLETON):
        def _on_conn():
            conn = server.nextPendingConnection()
            if conn:
                conn.readyRead.connect(lambda: conn.readAll())
                win.show_window()
        server.newConnection.connect(_on_conn)

    if selftest:
        QTimer.singleShot(1500, win.quit_app)

    code = app.exec()

    # 兜底：任何非正常退出路径（自检、系统会话结束）都要先停掉后台线程，
    # 否则 QThread 在运行中被析构会让进程直接 abort。
    try:
        if win.scheduler.isRunning():
            win.scheduler.stop()
    except Exception:
        pass
    server.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
