# -*- coding: utf-8 -*-
"""
小提醒 —— 桌面任务清单 + 定时提醒
纯标准库实现（tkinter + ctypes + winsound），常驻内存约 25MB，无第三方依赖。
"""
import os
import sys
import json
import re
import math
import time
import uuid
import queue
import ctypes
import ctypes.wintypes as wt
import threading
from datetime import datetime, timedelta, date, time as dtime

import tkinter as tk
from tkinter import font as tkfont

try:
    import winsound
except Exception:
    winsound = None

# ----------------------------------------------------------------------------
# DPI
# ----------------------------------------------------------------------------
def _enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

_enable_dpi()

_DPI = 96
try:
    _DPI = int(ctypes.windll.user32.GetDpiForSystem())
except Exception:
    pass
SC = max(1.0, _DPI / 96.0)


def S(v):
    return int(round(v * SC))


# ----------------------------------------------------------------------------
# 常量 / 配色
# ----------------------------------------------------------------------------
APP_NAME = "小提醒"
APP_ID = "ReminderDesk"
WIN_TITLE = "ReminderDeskMainWindow"

PALETTES = {
    "dark": dict(
        C_BG="#15161a", C_PANEL="#1b1d22", C_CARD="#212429", C_CARD_HI="#2a2e35",
        C_CARD_EDGE="#212429", C_LINE="#303540", C_SEP="#22252c",
        C_TEXT="#e9ebf0", C_SUB="#8b90a0", C_DIM="#5f6472", C_GHOST="#454b59",
        C_ACCENT="#4c7dff", C_ACCENT2="#3a63d6", C_ACCENT_SOFT="#1e2739",
        C_GREEN="#34d399", C_RED="#f87171", C_AMBER="#fbbf24",
        C_ON_ACCENT="#ffffff", C_ON_GREEN="#0f1a15",
        C_FIELD="#272b34", C_FIELD_HI="#2f333d",
        C_CHIP="#272b34", C_CHIP_HI="#333947",
        C_SCROLL="#333845", C_SCROLL_HI="#4a5162",
        C_WHEEL_SEL="#ffffff", C_WHEEL_NEAR="#8b90a0", C_WHEEL_FAR="#474c58",
        C_GROUP="#7a8091", C_GROUP_DONE="#6b7080", C_COUNT="#4b5059",
    ),
    "light": dict(
        C_BG="#eef1f5", C_PANEL="#ffffff", C_CARD="#ffffff", C_CARD_HI="#f6f8fb",
        C_CARD_EDGE="#e6eaf1", C_LINE="#dde2ea", C_SEP="#e6eaf0",
        C_TEXT="#1b1f27", C_SUB="#6b7280", C_DIM="#9aa2ae", C_GHOST="#c4cad4",
        C_ACCENT="#3b6ef6", C_ACCENT2="#2c56cc", C_ACCENT_SOFT="#eaf0ff",
        C_GREEN="#1fa971", C_RED="#e5484d", C_AMBER="#d97706",
        C_ON_ACCENT="#ffffff", C_ON_GREEN="#ffffff",
        C_FIELD="#f1f4f9", C_FIELD_HI="#e8eef8",
        C_CHIP="#f1f4f9", C_CHIP_HI="#e5ebf5",
        C_SCROLL="#c7cedb", C_SCROLL_HI="#a3adbe",
        C_WHEEL_SEL="#11151c", C_WHEEL_NEAR="#6b7280", C_WHEEL_FAR="#c4cad4",
        C_GROUP="#6b7280", C_GROUP_DONE="#8b93a1", C_COUNT="#b0b8c4",
    ),
}

THEME = "dark"


def set_palette(name):
    """切换当前配色：把调色板写进模块全局，所有绘制函数下次调用即生效"""
    global THEME
    pal = PALETTES.get(name) or PALETTES["dark"]
    THEME = name if name in PALETTES else "dark"
    globals().update(pal)


set_palette("dark")

YAHEI = "Microsoft YaHei UI"

DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_ID)
DATA_FILE = os.path.join(DATA_DIR, "tasks.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_config(cfg):
    try:
        ensure_dir()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except Exception:
        _log_line("保存配置失败: %r" % (sys.exc_info()[1],))


def ensure_dir():
    try:
        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR)
    except Exception:
        pass


def _log_line(text):
    """追加写入 error.log；超过 1MB 清空重写，同时尽力打到 stderr 便于调试"""
    try:
        ensure_dir()
        p = os.path.join(DATA_DIR, "error.log")
        try:
            if os.path.exists(p) and os.path.getsize(p) > (1 << 20):
                os.remove(p)
        except Exception:
            pass
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n===== %s =====\n%s\n" %
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text))
    except Exception:
        pass
    try:
        sys.stderr.write(text + "\n")
    except Exception:
        pass


# ----------------------------------------------------------------------------
# 绘图工具
# ----------------------------------------------------------------------------
def rrect(cv, x1, y1, x2, y2, r, **kw):
    """在 canvas 上画圆角矩形，返回 item id"""
    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    steps = 8
    pts = []

    def arc(cx, cy, a0, a1):
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / float(steps))
            pts.append(cx + math.cos(a) * r)
            pts.append(cy + math.sin(a) * r)

    arc(x1 + r, y1 + r, 180, 270)
    arc(x2 - r, y1 + r, 270, 360)
    arc(x2 - r, y2 - r, 0, 90)
    arc(x1 + r, y2 - r, 90, 180)
    return cv.create_polygon(pts, **kw)


def fit_text(fnt, text, max_px):
    if max_px <= 8:
        return ""
    if fnt.measure(text) <= max_px:
        return text
    out = text
    while out and fnt.measure(out + "…") > max_px:
        out = out[:-1]
    return (out + "…") if out else ""


def human_left(due, now=None):
    now = now or time.time()
    d = due - now
    if d < 0:
        d = -d
        pre = "已超时 "
    else:
        pre = "还有 "
    if d < 60:
        return pre + "不到 1 分钟"
    if d < 3600:
        return pre + "%d 分钟" % int(d // 60)
    if d < 86400:
        h = int(d // 3600)
        m = int((d % 3600) // 60)
        return pre + ("%d 小时" % h if m == 0 else "%d 小时 %d 分" % (h, m))
    return pre + "%d 天" % int(d // 86400)


def fmt_due(due):
    dt = datetime.fromtimestamp(due)
    now = datetime.now()
    today = now.date()
    d = dt.date()
    if d == today:
        pre = "今天"
    elif d == today + timedelta(days=1):
        pre = "明天"
    elif d == today - timedelta(days=1):
        pre = "昨天"
    elif d.year == now.year:
        pre = "%d月%d日" % (dt.month, dt.day)
    else:
        pre = "%d-%02d-%02d" % (dt.year, dt.month, dt.day)
    return "%s %02d:%02d" % (pre, dt.hour, dt.minute)


def fmt_short(due):
    """紧凑时间：今天 18:30 / 明天 09:00 / 11/28 14:00"""
    dt = datetime.fromtimestamp(due)
    today = date.today()
    d = dt.date()
    if d == today:
        pre = "今天 "
    elif d == today + timedelta(days=1):
        pre = "明天 "
    elif d == today + timedelta(days=2):
        pre = "后天 "
    else:
        pre = "%d/%d " % (dt.month, dt.day)
    return pre + "%02d:%02d" % (dt.hour, dt.minute)


# ----------------------------------------------------------------------------
# 时间解析
# ----------------------------------------------------------------------------
def _parse_date_part(dp, now):
    dp = dp.replace("/", "-").replace(".", "-").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", dp)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})-(\d{1,2})$", dp)
    if m:
        try:
            d = date(now.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        if (now.date() - d).days > 180:
            try:
                d = date(now.year + 1, int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None
        return d
    return None


def _parse_time_part(tp):
    tp = tp.strip().replace(" ", "")
    if not tp:
        return None
    if tp.isdigit() and len(tp) in (3, 4):
        try:
            return int(tp[:-2]), int(tp[-2:])
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})(?::(\d{1,2}))?$", tp)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return None
    return h, mi


def parse_when(text):
    """解析时间输入。返回 (datetime 或 None, 是否合法)。空字符串 -> (None, True)"""
    raw = (text or "").strip()
    if not raw:
        return None, True
    now = datetime.now()
    s = raw.replace("：", ":").replace("　", " ").strip()

    # 相对时长：+30m / +2h / +1d
    m = re.match(r"^\+\s*(\d+(?:\.\d+)?)\s*(m|min|mins|分钟|分|h|hr|hour|小时|时|d|day|天)?$",
                 s, re.I)
    if m:
        v = float(m.group(1))
        u = (m.group(2) or "m").lower()
        if u in ("h", "hr", "hour", "小时", "时"):
            return now + timedelta(hours=v), True
        if u in ("d", "day", "天"):
            return now + timedelta(days=v), True
        return now + timedelta(minutes=v), True

    # 中文时段前缀
    day_off = None
    ampm = None
    prefixes = (
        ("今天", 0, None), ("明天", 1, None), ("后天", 2, None),
        ("今晚", 0, "pm"), ("今夜", 0, "pm"), ("明晚", 1, "pm"),
        ("明早", 1, "am"), ("早上", 0, "am"), ("上午", 0, "am"),
        ("下午", 0, "pm"), ("晚上", 0, "pm"), ("中午", 0, None),
    )
    for kw, off, ap in prefixes:
        if s.startswith(kw):
            day_off = off
            ampm = ap
            s = s[len(kw):].strip()
            break

    s = s.replace("点", ":").replace("时", ":")
    s = s.replace(":半", ":30")
    s = re.sub(r":$", ":00", s)
    s = s.replace("分", "")
    s = s.replace("：", ":")
    s = s.strip()

    date_part = None
    time_part = None

    parts = s.split()
    if len(parts) >= 2 and re.search(r"\d", parts[0]) and ("-" in parts[0] or "/" in parts[0]):
        date_part = parts[0]
        time_part = " ".join(parts[1:])
    else:
        joined = "".join(parts)
        if re.match(r"^\d{1,4}[-/]\d{1,2}([-/]\d{1,2})?$", joined):
            date_part = joined
        else:
            time_part = joined

    if date_part is not None:
        d = _parse_date_part(date_part, now)
        if d is None:
            return None, False
    elif day_off is not None:
        d = (now + timedelta(days=day_off)).date()
    else:
        d = now.date()

    if time_part:
        tp = _parse_time_part(time_part)
        if tp is None:
            return None, False
    elif date_part is not None:
        tp = (9, 0)
    else:
        return None, False

    h, mi = tp
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0

    dt = datetime.combine(d, dtime(h, mi))
    if date_part is None and day_off is None and dt < now - timedelta(minutes=1):
        dt = dt + timedelta(days=1)
    return dt, True


# ----------------------------------------------------------------------------
# 标题行内时间提取
# ----------------------------------------------------------------------------
_TIME_HINT_RE = re.compile(
    r"(点|时|分|半|今天|明天|后天|今晚|今夜|明晚|明早|早上|上午|下午|晚上|中午)")


def _looks_like_time(s):
    """粗判一段词是否想表达时间，避免把普通标题误当成时间"""
    if s.startswith("+"):
        return True
    if re.match(r"^\d{3,4}$", s):                              # 0830 / 1830
        return True
    if re.match(r"^\d{1,4}[-/.]\d{1,2}([-/.]\d{1,2})?$", s):   # 11-28 / 2026-12-01
        return True
    if re.match(r"^\d{1,2}[:：]\d{1,2}$", s):                  # 18:30
        return True
    return bool(_TIME_HINT_RE.search(s))


def split_time_phrase(text):
    """标题末尾若带时间短语（如「回电话 明天9点」「整理报告 +2h」）则拆出来。
    返回 (纯标题, due 秒 或 0)。拆不出来就原样返回，不影响普通标题。"""
    parts = (text or "").split()
    for n in (2, 1):          # 先试末尾两词（如「明天 10:00」「11-28 14:00」），再试一词
        if len(parts) < n:
            continue
        cand = " ".join(parts[-n:])
        if not _looks_like_time(cand):
            continue
        dt, _ok = parse_when(cand)
        if dt is not None:
            rest = " ".join(parts[:-n]).strip()
            return (rest or cand), dt.timestamp()
    return (text or "").strip(), 0


# ----------------------------------------------------------------------------
# 数据
# ----------------------------------------------------------------------------
def load_tasks():
    ensure_dir()
    tasks = []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for t in data.get("tasks", []):
            tasks.append({
                "id": str(t.get("id") or "%d%03d" % (int(time.time()), len(tasks))),
                "title": str(t.get("title", "")).strip() or "未命名任务",
                "due": float(t.get("due") or 0),
                "done": bool(t.get("done")),
                "notified": bool(t.get("notified")),
                "created": float(t.get("created") or time.time()),
            })
        return tasks
    except FileNotFoundError:
        return []          # 首次运行，正常
    except Exception:
        # 文件损坏：先把坏文件备份出来，避免下次保存时无声丢掉全部任务
        try:
            os.replace(DATA_FILE, DATA_FILE + ".bad")
        except Exception:
            pass
        _log_line("tasks.json 损坏，已备份为 tasks.json.bad: %r" % (sys.exc_info()[1],))
        return []


def save_tasks(tasks):
    ensure_dir()
    tmp = DATA_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks, "ver": 1}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DATA_FILE)
    except Exception:
        _log_line("保存任务失败: %r" % (sys.exc_info()[1],))


def new_id():
    return uuid.uuid4().hex[:16]


# ----------------------------------------------------------------------------
# 托盘
# ----------------------------------------------------------------------------
wm = ctypes.windll
user32 = wm.user32
shell32 = wm.shell32
kernel32 = wm.kernel32

WM_DESTROY = 0x0002
WM_APP = 0x8000
WM_TRAYMSG = WM_APP + 11
WM_SHOW = WM_APP + 12
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04
NIF_INFO = 0x10
NIIF_INFO = 0x01

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.SetWindowTextW.argtypes = [wt.HWND, wt.LPCWSTR]
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]

kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HINSTANCE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.GetLastError.restype = wt.DWORD

shell32.ExtractIconExW.argtypes = [wt.LPCWSTR, ctypes.c_int,
                                   ctypes.POINTER(wt.HICON), ctypes.POINTER(wt.HICON),
                                   wt.UINT]
shell32.ExtractIconExW.restype = wt.UINT

user32.LoadIconW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = wt.HICON
user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.RegisterClassExW.restype = wt.WORD
user32.GetParent.argtypes = [wt.HWND]
user32.GetParent.restype = wt.HWND
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostThreadMessageW.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.MessageBoxW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT]
user32.MessageBoxW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.GetClassLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetClassLongW.restype = wt.DWORD
user32.SetClassLongW.argtypes = [wt.HWND, ctypes.c_int, wt.DWORD]
user32.SetClassLongW.restype = wt.DWORD


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
                ("Data4", ctypes.c_byte * 8)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uTimeout", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wt.HICON),
    ]


class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class Tray(object):
    def __init__(self, ui_queue):
        self.q = ui_queue
        self.ok = False
        self.hwnd = None
        self.hicon = None
        self._proc = None
        self._cls = "ReminderDeskTrayWnd"

    def start(self):
        # 窗口必须创建在泵消息的同一个线程：Win32 把消息投递到创建线程的队列，
        # 否则 _loop 里的 GetMessageW 收不到任何托盘消息
        def run():
            try:
                self._tid = threading.get_ident()
                self._create()
                self._add()
                self.ok = True
                self._loop()
            except Exception:
                self.ok = False
                try:
                    _log_exc(*sys.exc_info())
                except Exception:
                    pass
        threading.Thread(target=run, name="tray", daemon=True).start()

    def stop(self):
        """删除托盘图标并结束托盘线程的消息循环"""
        self.destroy()
        tid = getattr(self, "_tid", 0)
        if tid:
            try:
                user32.PostThreadMessageW(tid, 0x0012, 0, 0)   # WM_QUIT
            except Exception:
                pass

    def _create(self):
        hinst = kernel32.GetModuleHandleW(None)
        self.hicon = self._load_icon()

        def proc(hwnd, msg, wp, lp):
            if msg == WM_SHOW:
                self.q.put(("tray_show", 0, 0))
                return 0
            if msg == WM_TRAYMSG:
                low = lp & 0xFFFF
                if low in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    pt = wt.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    self.q.put(("tray_show", pt.x, pt.y))
                elif low == WM_RBUTTONUP:
                    pt = wt.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    self.q.put(("tray_menu", pt.x, pt.y))
                return 0
            return user32.DefWindowProcW(hwnd, msg, wp, lp)

        self._proc = WNDPROC(proc)

        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX)
        wc.lpfnWndProc = ctypes.cast(self._proc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = self._cls
        wc.hIcon = self.hicon
        user32.RegisterClassExW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            0, self._cls, self._cls, 0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise RuntimeError("create window failed")

    def _load_icon(self):
        try:
            large = wt.HICON()
            small = wt.HICON()
            n = shell32.ExtractIconExW(sys.executable, 0,
                                       ctypes.byref(large), ctypes.byref(small), 1)
            if n and large.value:
                return large.value
            if n and small.value:
                return small.value
        except Exception:
            pass
        try:
            hinst = kernel32.GetModuleHandleW(None)
            return user32.LoadIconW(hinst, ctypes.c_void_p(32512))
        except Exception:
            return None

    def _add(self):
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYMSG
        nid.hIcon = self.hicon
        nid.szTip = APP_NAME
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _loop(self):
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def notify(self, title, text):
        if not self.ok or not self.hwnd:
            return
        try:
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = self.hwnd
            nid.uID = 1
            nid.uFlags = NIF_INFO
            nid.szInfoTitle = title[:60]
            nid.szInfo = text[:250]
            nid.dwInfoFlags = NIIF_INFO
            nid.uTimeout = 5000
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            pass

    def destroy(self):
        try:
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = self.hwnd
            nid.uID = 1
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        except Exception:
            pass


# ----------------------------------------------------------------------------
# 通用控件
# ----------------------------------------------------------------------------
class Chip(tk.Canvas):
    """小胶囊按钮"""

    def __init__(self, parent, text, command, fnt, bg=None, fg=None,
                 bg_hover=None, fg_hover=None, radius=11, padx=10, h=24):
        bg = bg or C_PANEL
        fg = fg or C_SUB
        bg_hover = bg_hover or C_CARD_HI
        fg_hover = fg_hover or C_TEXT
        tk.Canvas.__init__(self, parent, bd=0, highlightthickness=0, bg=parent["bg"])
        self.command = command
        self._bg = bg
        self._fg = fg
        self._bgh = bg_hover
        self._fgh = fg_hover
        self._r = S(radius)
        w = fnt.measure(text) + S(padx) * 2
        hh = S(h)
        self.configure(width=w, height=hh)
        self._bgid = rrect(self, 0, 0, w, hh, self._r, fill=bg, outline="")
        self._tid = self.create_text(w / 2.0, hh / 2.0, text=text, fill=fg, font=fnt)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.configure(cursor="hand2")

    def _enter(self, e):
        self.itemconfig(self._bgid, fill=self._bgh)
        self.itemconfig(self._tid, fill=self._fgh)

    def _leave(self, e):
        self.itemconfig(self._bgid, fill=self._bg)
        self.itemconfig(self._tid, fill=self._fg)

    def _click(self, e):
        try:
            self.command()
        except Exception:
            pass


class SlimScroll(tk.Canvas):
    """自绘细滚动条"""

    def __init__(self, parent, target):
        tk.Canvas.__init__(self, parent, width=S(7), bg=C_BG,
                           highlightthickness=0, bd=0)
        self.target = target
        self.first = 0.0
        self.last = 1.0
        self._drag_y = None
        self._drag_first = 0.0
        self._hover = False
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)

    def _wheel(self, e):
        self.target.yview_scroll(int(-1 * (e.delta / 120) * 3), "units")

    def _enter(self, e):
        self._hover = True
        self.redraw()

    def _leave(self, e):
        self._hover = False
        self.redraw()

    def set(self, a, b):
        self.first = float(a)
        self.last = float(b)
        self.redraw()

    def redraw(self):
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h < 20 or w < 2:
            return
        if self.last - self.first >= 0.999:
            return
        y1 = self.first * h
        y2 = self.last * h
        minh = S(26)
        if y2 - y1 < minh:
            y2 = y1 + minh
            if y2 > h:
                y2 = h
                y1 = max(0, y2 - minh)
        col = C_SCROLL_HI if self._hover else C_SCROLL
        rrect(self, 0.5, y1, w - 0.5, y2, (w - 1) / 2.0, fill=col, outline="")

    def _press(self, e):
        self._drag_y = e.y
        self._drag_first = self.first
        h = self.winfo_height()
        span = self.last - self.first
        if h > 0 and (e.y < self.first * h or e.y > self.last * h):
            self.target.yview_moveto(max(0.0, min(1.0 - span, e.y / float(h) - span / 2.0)))
            self._drag_first = self.target.yview()[0]

    def _move(self, e):
        if self._drag_y is None:
            return
        h = self.winfo_height()
        if h <= 0:
            return
        span = self.last - self.first
        f = self._drag_first + (e.y - self._drag_y) / float(h)
        self.target.yview_moveto(max(0.0, min(1.0 - span, f)))

    def _release(self, e):
        self._drag_y = None


class Btn(tk.Canvas):
    """圆角实心按钮"""

    def __init__(self, parent, text, command, fnt, w=76, h=34,
                 bg=None, bg_hover=None, fg=None, radius=9):
        bg = bg or C_ACCENT
        bg_hover = bg_hover or C_ACCENT2
        fg = fg or C_ON_ACCENT
        tk.Canvas.__init__(self, parent, bd=0, highlightthickness=0, bg=parent["bg"])
        self.command = command
        self._bg = bg
        self._bgh = bg_hover
        ww = S(w)
        hh = S(h)
        self.configure(width=ww, height=hh)
        self._bgid = rrect(self, 0, 0, ww, hh, S(radius), fill=bg, outline="")
        self._tid = self.create_text(ww / 2.0, hh / 2.0 - 1, text=text, fill=fg, font=fnt)
        self.bind("<Enter>", lambda e: self.itemconfig(self._bgid, fill=self._bgh))
        self.bind("<Leave>", lambda e: self.itemconfig(self._bgid, fill=self._bg))
        self.bind("<Button-1>", lambda e: self.command())
        self.configure(cursor="hand2")


class IconBtn(tk.Canvas):
    """无边框图标按钮（Segoe MDL2 字形），带圆角悬停底色"""

    def __init__(self, parent, glyph, command, fnt, size=28, fg=None,
                 hover_fg=None, tip=None):
        tk.Canvas.__init__(self, parent, width=S(size), height=S(size),
                           bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self._base_bg = parent["bg"]
        self._fg = fg or C_SUB
        self._fgh = hover_fg or C_TEXT
        s = S(size)
        self._bgid = rrect(self, 0, 0, s, s, S(8), fill=self._base_bg, outline="")
        self._tid = self.create_text(s / 2.0, s / 2.0, text=glyph,
                                     fill=self._fg, font=fnt)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", lambda e: self.command())
        self.configure(cursor="hand2")

    def _enter(self, e):
        self.itemconfig(self._bgid, fill=C_CARD_HI)
        self.itemconfig(self._tid, fill=self._fgh)

    def _leave(self, e):
        self.itemconfig(self._bgid, fill=self._base_bg)
        self.itemconfig(self._tid, fill=self._fg)


class TimeButton(tk.Canvas):
    """点开滚轮选时间的胶囊按钮"""

    def __init__(self, parent, app):
        tk.Canvas.__init__(self, parent, bg=C_BG, highlightthickness=0, bd=0,
                           height=S(38))
        self.app = app
        self.ts = 0
        self.hover = False
        self.W = 1
        self.bind("<Configure>", self._on_conf)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.configure(cursor="hand2")

    def _on_conf(self, e):
        self.W = e.width
        self.draw()

    def _enter(self, e):
        self.hover = True
        self.draw()

    def _leave(self, e):
        self.hover = False
        self.draw()

    def _click(self, e):
        if self.ts and e.x >= self.W - S(34):
            self.set_ts(0)
            return
        self.open_picker()

    def set_ts(self, ts):
        self.ts = ts
        self.draw()

    def open_picker(self):
        DateTimePicker(self.app, self, self.ts, self.set_ts)

    def draw(self):
        self.delete("all")
        W = self.W
        if W < 20:
            return
        H = S(38)
        bg = C_CARD_HI if self.hover else C_CARD
        rrect(self, 1, 1, W - 1, H - 1, S(12), fill=bg, outline="")

        cx, cy, r = S(19), H / 2.0, S(6.5)
        col = C_ACCENT if self.ts else C_DIM
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col,
                         width=max(1, S(1.6)))
        self.create_line(cx, cy, cx, cy - r * 0.52, fill=col,
                         width=max(1, S(1.6)), capstyle="round")
        self.create_line(cx, cy, cx + r * 0.46, cy + r * 0.28, fill=col,
                         width=max(1, S(1.6)), capstyle="round")

        txt = fmt_short(self.ts) if self.ts else "不提醒"
        tcol = C_TEXT if self.ts else C_DIM
        self.create_text(S(36), cy, anchor="w", text=txt, fill=tcol,
                         font=self.app.f_body)

        if self.ts:
            self.create_text(W - S(18), cy, text="✕",
                             fill=C_RED if self.hover else C_GHOST,
                             font=self.app.f_icon)
        else:
            self.create_text(W - S(18), cy, text="▾", fill=C_GHOST,
                             font=self.app.f_icon)


class RoundEntry(tk.Canvas):
    """圆角输入框：Canvas 圆角底 + 内嵌 Entry；点一下提示文字就消失"""

    def __init__(self, parent, placeholder, fnt, height=44, radius=13,
                 bg=None, fill=None):
        bg = bg or C_BG
        fill = fill or C_CARD
        tk.Canvas.__init__(self, parent, bg=bg, highlightthickness=0, bd=0,
                           height=S(height))
        self._fill = fill
        self._fill_focus = C_FIELD_HI
        self._radius = S(radius)
        self._ph = placeholder
        self._showing = False
        self._armed = False
        self._cw = 0
        self._bgid = None

        self.entry = tk.Entry(self, font=fnt, bd=0, relief="flat",
                              bg=fill, fg=C_TEXT, insertbackground=C_ACCENT,
                              highlightthickness=0, selectbackground=C_ACCENT2,
                              selectforeground=C_ON_ACCENT)
        self._cwin = self.create_window(0, 0, window=self.entry, anchor="w")

        self.bind("<Configure>", self._on_conf)
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<Button-1>", self._on_click, add="+")
        self.entry.bind("<KeyPress>", self._on_click, add="+")
        self._show_ph()

    def _on_conf(self, e):
        w, h = e.width, e.height
        if w < 10:
            return
        if w != self._cw or self._bgid is None:
            self._cw = w
            if self._bgid is not None:
                self.delete(self._bgid)
            if getattr(self, "_ringid", None) is not None:
                self.delete(self._ringid)
            self._bgid = rrect(self, 1, 1, w - 1, h - 1, self._radius,
                               fill=self._fill, outline="")
            self._ringid = rrect(self, 1, 1, w - 1, h - 1, self._radius,
                                 fill="", outline=C_LINE, width=1)
            self.tag_lower(self._bgid)
            self.tag_raise(self._ringid, self._bgid)
            pad = self._radius
            self.coords(self._cwin, pad, h / 2.0)
            self.itemconfigure(self._cwin, width=max(10, w - 2 * pad))

    def _focus_in(self, e):
        if not self.entry.get() and not self._armed:
            self._show_ph()
        if self._bgid:
            self.itemconfig(self._bgid, fill=self._fill_focus)
        if getattr(self, "_ringid", None) is not None:
            self.itemconfig(self._ringid, outline=C_ACCENT)
        try:
            self.entry.configure(bg=self._fill_focus)
        except Exception:
            pass

    def _focus_out(self, e):
        self._armed = False
        if self._bgid:
            self.itemconfig(self._bgid, fill=self._fill)
        if getattr(self, "_ringid", None) is not None:
            self.itemconfig(self._ringid, outline=C_LINE)
        try:
            self.entry.configure(bg=self._fill)
        except Exception:
            pass
        if not self.entry.get().strip():
            self._show_ph()

    def _on_click(self, e):
        if self._showing:
            self._armed = True
            self._showing = False
            self.entry.delete(0, "end")
            self.entry.configure(fg=C_TEXT)

    def _show_ph(self):
        self._showing = True
        self.entry.delete(0, "end")
        self.entry.insert(0, self._ph)
        self.entry.configure(fg=C_DIM)

    def value(self):
        return "" if self._showing else self.entry.get().strip()

    def clear(self):
        self._showing = False
        self._armed = False
        self.entry.delete(0, "end")
        self.entry.configure(fg=C_TEXT)
        self._show_ph()

    def set_text(self, text):
        self._showing = False
        self._armed = False
        self.entry.delete(0, "end")
        self.entry.configure(fg=C_TEXT)
        if text:
            self.entry.insert(0, text)
        else:
            self._show_ph()

    def focus(self):
        self.entry.focus_set()
        self.entry.icursor("end")


class Wheel(tk.Canvas):
    """滚轮选择器：一格一格走，松手对齐到整数项"""

    ITEM_H = 36
    VISIBLE = 5

    def __init__(self, parent, items, index=0, width=80,
                 on_change=None, fnt=None, fnt_sel=None, bg=None):
        bg = bg or C_CARD
        tk.Canvas.__init__(self, parent, width=S(width),
                           height=S(self.ITEM_H * self.VISIBLE), bg=bg,
                           highlightthickness=0, bd=0)
        self.items = items
        self.offset = float(max(0, min(len(items) - 1, index)))
        self.on_change = on_change
        self.item_h = S(self.ITEM_H)
        self.fnt = fnt
        self.fnt_sel = fnt_sel
        self._bg = bg
        self._anim = None
        self._drag = None
        self._moved = False
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.configure(cursor="hand2")
        self.redraw()

    def value(self):
        return int(round(self.offset))

    def set_index(self, i, notify=False):
        self.offset = float(max(0, min(len(self.items) - 1, i)))
        self.redraw()
        if notify and self.on_change:
            self.on_change(self.value())

    # ---------- 滚动 ----------
    def _limit(self, v):
        return max(0, min(len(self.items) - 1, v))

    def _wheel(self, e):
        # 一格滚一个，立刻响应；不依赖松手后的 130ms 延迟
        d = e.delta if e.delta else 0
        if d == 0:
            return "break"
        step = -1 if d > 0 else 1
        if abs(d) >= 360:          # 高速滚动时一次走两格
            step *= 2
        self.step(step)

    def step(self, n):
        cur = int(round(self.offset))
        tgt = self._limit(cur + n)
        if tgt == cur and abs(self.offset - tgt) < 0.01:
            return
        self._slide_to(float(tgt))

    def _slide_to(self, target):
        if self._anim:
            try:
                self.after_cancel(self._anim)
            except Exception:
                pass
            self._anim = None
        target = self._limit(target)

        def step():
            d = target - self.offset
            if abs(d) < 0.05:
                self.offset = target
                self._anim = None
                self.redraw()
                if self.on_change:
                    self.on_change(int(round(target)))
                return
            self.offset += d * 0.55
            self.redraw()
            self._anim = self.after(12, step)

        step()

    # 兼容旧调用
    def _snap(self):
        self._slide_to(float(int(round(self.offset))))

    def _index_at(self, y):
        h = self.winfo_height()
        i = int(round(self.offset + (y - h / 2.0) / self.item_h))
        return i if 0 <= i < len(self.items) else None

    def _press(self, e):
        self._drag = [e.y, self.offset, False]
        self._moved = False

    def _motion(self, e):
        if not self._drag:
            return
        dy = e.y - self._drag[0]
        if abs(dy) > 4:
            self._drag[2] = True
        o = self._drag[1] - dy / float(self.item_h)
        self.offset = self._limit(o)
        self.redraw()

    def _release(self, e):
        moved = bool(self._drag and self._drag[2])
        self._drag = None
        if not moved:
            idx = self._index_at(e.y)
            if idx is not None and idx != int(round(self.offset)):
                self._slide_to(float(idx))
                return
        self._slide_to(float(int(round(self.offset))))

    # ---------- 绘制 ----------
    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 6 or h < 20:
            return
        cy = h / 2.0
        ih = self.item_h

        # 选中带：上下两条渐隐细线，中间留出"窗口"
        bw = 0
        for off in (-ih / 2.0, ih / 2.0):
            self.create_line(bw, cy + off, w - bw, cy + off,
                             fill=C_LINE, width=1)

        lo = max(0, int(math.floor(self.offset)) - 3)
        hi = min(len(self.items), int(math.floor(self.offset)) + 4)
        for i in range(lo, hi):
            y = cy + (i - self.offset) * ih
            d = abs(i - self.offset)
            if d > 2.4:
                continue
            if d < 0.35:
                col, fnt = C_WHEEL_SEL, self.fnt_sel
            elif d < 1.4:
                col, fnt = C_WHEEL_NEAR, self.fnt
            else:
                col, fnt = C_WHEEL_FAR, self.fnt
            self.create_text(w / 2.0, y, text=self.items[i], fill=col, font=fnt)


WEEK_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


class DateTimePicker(object):
    """滚轮式时间选择弹层"""

    def __init__(self, app, anchor, initial, on_ok):
        self.app = app
        self.on_ok = on_ok
        self.finished = False

        base = datetime.fromtimestamp(initial) if initial else \
            (datetime.now() + timedelta(minutes=30))
        base = base.replace(second=0, microsecond=0)
        if base < datetime.now() - timedelta(minutes=2):
            base = datetime.now() + timedelta(minutes=30)

        today = date.today()
        self.dates = [today + timedelta(days=i) for i in range(90)]
        labels = []
        for i, d in enumerate(self.dates):
            if i == 0:
                labels.append("今天  %d日" % d.day)
            elif i == 1:
                labels.append("明天  %d日" % d.day)
            elif i == 2:
                labels.append("后天  %d日" % d.day)
            else:
                labels.append("%d月%d日 %s" % (d.month, d.day, WEEK_CN[d.weekday()]))

        d_idx = (base.date() - today).days
        d_idx = 0 if d_idx < 0 or d_idx >= len(self.dates) else d_idx
        m_idx = int(round(base.minute / 5.0))
        if m_idx > 11:
            m_idx = 0
            if base.hour < 23:
                pass

        W = S(318)
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.title("ReminderDeskPicker")
        self.win.configure(bg=C_BG)
        self.win.attributes("-topmost", True)

        box = tk.Frame(self.win, bg=C_CARD, highlightthickness=1,
                       highlightbackground=C_LINE)
        box.pack(fill="both", expand=True)

        head = tk.Frame(box, bg=C_CARD)
        head.pack(fill="x", padx=S(16), pady=(S(13), S(4)))
        tk.Label(head, text="提醒时间", font=app.f_body_b, bg=C_CARD,
                 fg=C_TEXT).pack(side="left")
        self.lbl_info = tk.Label(head, text="", font=app.f_small, bg=C_CARD, fg=C_ACCENT)
        self.lbl_info.pack(side="right")

        body = tk.Frame(box, bg=C_CARD)
        body.pack(padx=S(10), pady=(S(2), S(2)))
        self.w_date = Wheel(body, labels, d_idx, width=140,
                            on_change=lambda i: self._update_info(),
                            fnt=app.f_wheel, fnt_sel=app.f_wheel_sel, bg=C_CARD)
        self.w_date.pack(side="left")
        self.w_hour = Wheel(body, ["%02d 时" % h for h in range(24)], base.hour,
                            width=76, on_change=lambda i: self._update_info(),
                            fnt=app.f_wheel, fnt_sel=app.f_wheel_sel, bg=C_CARD)
        self.w_hour.pack(side="left", padx=(S(2), 0))
        self.w_min = Wheel(body, ["%02d 分" % m for m in range(0, 60, 5)], m_idx,
                           width=76, on_change=lambda i: self._update_info(),
                           fnt=app.f_wheel, fnt_sel=app.f_wheel_sel, bg=C_CARD)
        self.w_min.pack(side="left", padx=(S(2), 0))

        self.focus_wheel = self.w_date
        for w in (self.w_date, self.w_hour, self.w_min):
            w.bind("<Enter>", lambda e, ww=w: self._focus_wheel(ww), add="+")
            w.bind("<Button-1>", lambda e, ww=w: self._focus_wheel(ww), add="+")

        # 鼠标落在弹层任何位置都能滚动到对应列
        self.win.bind("<MouseWheel>", self._route_wheel)
        self.win.bind("<Up>", lambda e: self._key_step(-1))
        self.win.bind("<Down>", lambda e: self._key_step(1))

        rule = tk.Frame(box, bg=C_SEP, height=1)
        rule.pack(fill="x", padx=S(12), pady=(S(6), 0))

        foot = tk.Frame(box, bg=C_CARD)
        foot.pack(fill="x", padx=S(14), pady=(S(8), S(12)))
        clear = tk.Label(foot, text="不提醒", font=app.f_small, bg=C_CARD,
                         fg=C_SUB, cursor="hand2")
        clear.pack(side="left")
        clear.bind("<Button-1>", lambda e: self._pick_none())
        clear.bind("<Enter>", lambda e: clear.configure(fg=C_RED))
        clear.bind("<Leave>", lambda e: clear.configure(fg=C_SUB))

        Btn(foot, "确定", self._confirm, app.f_small, w=68, h=30).pack(side="right")

        self.win.update_idletasks()
        H = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        ax = anchor.winfo_rootx()
        ay = anchor.winfo_rooty() + anchor.winfo_height() + S(6)
        if ax + W > sw - S(12):
            ax = sw - W - S(12)
        if ax < S(8):
            ax = S(8)
        if ay + H > sh - S(56):
            ay = anchor.winfo_rooty() - H - S(6)
        if ay < S(8):
            ay = S(8)
        self.win.geometry("%dx%d+%d+%d" % (W, H, ax, ay))

        self._binds = []
        targets = [app.root] + [w for w in app.root.winfo_children()
                                if isinstance(w, tk.Toplevel) and w is not self.win]
        for t in targets:
            try:
                fid = t.bind("<Button-1>", self._outside, add="+")
                self._binds.append((t, fid))
            except Exception:
                pass

        self._update_info()

        # 键盘可用：方向键滚动，Esc 关闭
        try:
            self._prev_focus = app.root.focus_get()
        except Exception:
            self._prev_focus = None
        try:
            self.win.focus_force()
        except Exception:
            pass
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<Return>", lambda e: self._confirm())

    def _selected(self):
        d = self.dates[self.w_date.value()]
        h = self.w_hour.value()
        m = self.w_min.value() * 5
        return datetime(d.year, d.month, d.day, h, m)

    def _focus_wheel(self, w):
        self.focus_wheel = w
        for x in (self.w_date, self.w_hour, self.w_min):
            try:
                x.configure(highlightthickness=1,
                            highlightbackground=C_ACCENT if x is w else C_CARD)
            except Exception:
                pass

    def _route_wheel(self, e):
        w = e.widget
        try:
            while w is not None and not isinstance(w, Wheel):
                w = getattr(w, "master", None)
        except Exception:
            w = None
        if isinstance(w, Wheel):
            self._focus_wheel(w)
            w._wheel(e)
        return "break"

    def _key_step(self, n):
        w = getattr(self, "focus_wheel", None) or self.w_date
        w.step(n)
        return "break"

    def _update_info(self):
        dt = self._selected()
        left = (dt - datetime.now()).total_seconds()
        col = C_ACCENT
        if left < 0:
            txt = "已过去"
            col = C_RED
        elif left < 3600:
            txt = "%d 分钟后" % max(1, int(left // 60))
        elif left < 86400:
            txt = "%.1f 小时后" % (left / 3600.0)
        else:
            txt = "%d 天后" % int(left // 86400)
        try:
            self.lbl_info.configure(text=txt, fg=col)
        except Exception:
            pass

    def _confirm(self):
        dt = self._selected()
        self.finished = True
        cb = self.on_ok
        self.close()
        if cb:
            cb(dt.timestamp())

    def _pick_none(self):
        self.finished = True
        cb = self.on_ok
        self.close()
        if cb:
            cb(0)

    def _outside(self, e):
        self.close()

    def close(self):
        for t, fid in self._binds:
            try:
                t.unbind("<Button-1>", fid)
            except Exception:
                pass
        self._binds = []
        try:
            self.win.destroy()
        except Exception:
            pass
        try:
            pf = getattr(self, "_prev_focus", None)
            if pf is not None and pf.winfo_exists():
                pf.focus_set()
        except Exception:
            pass


class EditDialog(object):
    """任务编辑弹层"""

    def __init__(self, app, task):
        self.app = app
        self.task = task
        self.due = task.get("due", 0)
        self.finished = False

        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.title("ReminderDeskEdit")
        self.win.configure(bg=C_BG)
        self.win.attributes("-topmost", True)

        W = S(360)
        box = tk.Frame(self.win, bg=C_CARD, highlightthickness=1,
                       highlightbackground=C_LINE)
        box.pack(fill="both", expand=True)

        head = tk.Frame(box, bg=C_CARD)
        head.pack(fill="x", padx=S(18), pady=(S(16), S(12)))
        tk.Label(head, text="编辑任务", font=app.f_body_b, bg=C_CARD,
                 fg=C_TEXT).pack(side="left")
        close = tk.Label(head, text="✕", font=app.f_small, bg=C_CARD,
                         fg=C_DIM, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.close())
        close.bind("<Enter>", lambda e: close.configure(fg=C_RED))
        close.bind("<Leave>", lambda e: close.configure(fg=C_DIM))

        self.e_title = RoundEntry(box, "任务内容", app.f_body, height=42,
                                  bg=C_CARD, fill=C_FIELD)
        self.e_title.pack(fill="x", padx=S(18))
        self.e_title.set_text(task.get("title", ""))
        self.e_title.entry.bind("<Return>", lambda e: self.save())

        tk.Label(box, text="提醒时间", font=app.f_small, bg=C_CARD, fg=C_SUB,
                 anchor="w").pack(fill="x", padx=S(18), pady=(S(14), S(6)))
        self.tbox = tk.Frame(box, bg=C_CARD)
        self.tbox.pack(fill="x", padx=S(18))
        self._render_time()

        btns = tk.Frame(box, bg=C_CARD)
        btns.pack(fill="x", padx=S(18), pady=(S(14), S(18)))
        rm = tk.Label(btns, text="删除", font=app.f_small, bg=C_CARD,
                      fg=C_RED, cursor="hand2")
        rm.pack(side="left")
        rm.bind("<Button-1>", lambda e: self.remove())
        Btn(btns, "保存", self.save, app.f_small, w=70, h=32).pack(side="right")
        cancel = tk.Label(btns, text="取消", font=app.f_small, bg=C_CARD,
                          fg=C_SUB, cursor="hand2", padx=S(10))
        cancel.pack(side="right", padx=(0, S(6)))
        cancel.bind("<Button-1>", lambda e: self.close())
        cancel.bind("<Enter>", lambda e: cancel.configure(fg=C_TEXT))
        cancel.bind("<Leave>", lambda e: cancel.configure(fg=C_SUB))

        self.win.update_idletasks()
        H = self.win.winfo_reqheight()
        r = app.root
        x = r.winfo_rootx() + (r.winfo_width() - W) // 2
        y = r.winfo_rooty() + (r.winfo_height() - H) // 2 - S(24)
        if y < S(10):
            y = S(10)
        self.win.geometry("%dx%d+%d+%d" % (W, H, x, y))

        self._binds = []
        targets = [app.root] + [w for w in app.root.winfo_children()
                                if isinstance(w, tk.Toplevel)]
        for t in targets:
            try:
                fid = t.bind("<Button-1>", self._outside, add="+")
                self._binds.append((t, fid))
            except Exception:
                pass

        self.win.bind("<Escape>", lambda e: self.close())
        self.e_title.focus()

    def _render_time(self):
        for w in self.tbox.winfo_children():
            w.destroy()
        if self.due:
            txt = fmt_due(self.due)
            fg = C_TEXT
        else:
            txt = "不提醒"
            fg = C_SUB
        c = Chip(self.tbox, txt, self.pick_time, self.app.f_small,
                 bg=C_CHIP, fg=fg, bg_hover=C_CHIP_HI, fg_hover=C_TEXT,
                 radius=14, padx=13, h=27)
        c.pack(side="left")
        if self.due:
            x = tk.Label(self.tbox, text="✕", font=self.app.f_icon,
                         bg=C_CARD, fg=C_DIM, cursor="hand2", padx=S(4))
            x.pack(side="left", padx=(S(10), 0))
            x.bind("<Button-1>", lambda e: self.clear_time())
            x.bind("<Enter>", lambda e: x.configure(fg=C_RED))
            x.bind("<Leave>", lambda e: x.configure(fg=C_DIM))

    def pick_time(self):
        self._picker = DateTimePicker(self.app, self.tbox, self.due, self._set_due)

    def _set_due(self, ts):
        self.due = ts
        self._render_time()

    def clear_time(self):
        self.due = 0
        self._render_time()

    def save(self):
        title = self.e_title.value()
        if not title:
            return
        self.task["title"] = title
        old = self.task.get("due", 0)
        self.task["due"] = self.due
        if self.due and (abs(self.due - old) > 1 or self.task.get("done")):
            self.task["notified"] = self.due <= time.time()
        elif not self.due:
            self.task["notified"] = False
        self.app.save()
        self.app.refresh()
        self.close()

    def remove(self):
        tid = self.task["id"]
        self.close()
        self.app.delete_task(tid)

    def _outside(self, e):
        try:
            w = self.win.winfo_containing(e.x_root, e.y_root)
        except Exception:
            w = None
        if w is not None:
            p = w
            while p is not None:
                if p is self.win:
                    return
                p = getattr(p, "master", None)
        self.close()

    def close(self):
        for t, fid in self._binds:
            try:
                t.unbind("<Button-1>", fid)
            except Exception:
                pass
        self._binds = []
        try:
            self.win.destroy()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# 任务行
# ----------------------------------------------------------------------------
ROW_H = 66


class TaskRow(tk.Canvas):
    def __init__(self, parent, app, task):
        tk.Canvas.__init__(self, parent, bd=0, highlightthickness=0,
                           bg=parent["bg"], height=S(ROW_H))
        self.app = app
        self.task = task
        self.W = 1
        self.hover = False
        self.bind("<Configure>", self._on_conf)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.configure(cursor="hand2")

    def _on_conf(self, e):
        self.W = e.width
        self.draw()

    def _enter(self, e):
        self.hover = True
        self.draw()

    def _leave(self, e):
        self.hover = False
        self.draw()

    def _click(self, e):
        if e.x <= S(48):
            self.app.toggle_task(self.task["id"])
        elif e.x >= self.W - S(36):
            self.app.delete_task(self.task["id"])
        else:
            self.app.edit_task(self.task["id"])

    def draw(self):
        self.delete("all")
        W = self.W
        if W < 10:
            return
        H = S(ROW_H) - S(6)
        done = self.task["done"]
        due = self.task["due"]
        now = time.time()
        over = bool((not done) and due and due < now)

        bgc = C_CARD_HI if self.hover else C_CARD
        rrect(self, 0, 0, W, H, S(14), fill=bgc, outline=C_CARD_EDGE, width=1)
        if over:
            rrect(self, 0, S(16), S(3.2), H - S(16), S(1.6), fill=C_RED, outline="")

        # 勾选圈
        cx, cy = S(26), H / 2.0
        rad = S(9)
        if done:
            self.create_oval(cx - rad, cy - rad, cx + rad, cy + rad,
                             fill=C_GREEN, outline="")
            self.create_line(cx - S(4.4), cy, cx - S(1), cy + S(3.4), cx + S(5), cy - S(4),
                             fill=C_ON_GREEN, width=max(2, S(2)), capstyle="round",
                             joinstyle="round")
        else:
            col = C_RED if over else C_GHOST
            self.create_oval(cx - rad, cy - rad, cx + rad, cy + rad,
                             outline=col, width=max(1, S(1.6)))

        # 标题
        tx = S(48)
        tw = W - tx - S(72)
        if done:
            title_fnt = self.app.f_strike
            tcol = C_DIM
        else:
            title_fnt = self.app.f_title
            tcol = C_TEXT
        self.create_text(tx, cy - S(9.5), anchor="w",
                         text=fit_text(title_fnt, self.task["title"], tw),
                         fill=tcol, font=title_fnt)

        # 副标题
        sy = cy + S(11)
        if due:
            t1 = fmt_due(due)
            if done:
                self.create_text(tx, sy, anchor="w", text=t1,
                                 fill=C_DIM, font=self.app.f_small)
            elif over:
                self.create_text(tx, sy, anchor="w", text=t1,
                                 fill=C_DIM, font=self.app.f_small)
                off = self.app.f_small.measure(t1) + S(9)
                self.create_text(tx + off, sy, anchor="w",
                                 text=human_left(due, now), fill=C_RED,
                                 font=self.app.f_small)
            else:
                sub = t1 + "  ·  " + human_left(due, now)
                self.create_text(tx, sy, anchor="w",
                                 text=fit_text(self.app.f_small, sub, tw),
                                 fill=C_SUB, font=self.app.f_small)
        else:
            self.create_text(tx, sy, anchor="w", text="随时",
                             fill=C_DIM, font=self.app.f_small)

        # 右侧操作
        if self.hover:
            self.create_text(W - S(52), cy, text="✎", fill=C_SUB,
                             font=self.app.f_icon)
        self.create_text(W - S(23), cy, text="✕",
                         fill=C_RED if self.hover else C_GHOST,
                         font=self.app.f_icon)


# ----------------------------------------------------------------------------
# 提醒弹窗
# ----------------------------------------------------------------------------
class Popup(object):
    _live = []

    def __init__(self, app, task):
        self.app = app
        self.task = task
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.title("ReminderDeskPopup")
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.configure(bg=C_BG)

        W = S(360)
        H = S(126)
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        try:
            rc = wt.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)
            sh = rc.bottom
            sw = rc.right
        except Exception:
            pass

        idx = len(Popup._live)
        x = sw - W - S(22)
        y = sh - S(22) - H - idx * (H + S(10))
        if y < S(30):
            y = S(30)
        self.win.geometry("%dx%d+%d+%d" % (W, H, x, y))

        cv = tk.Canvas(self.win, width=W, height=H, bg=C_BG, highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)

        rrect(cv, 0, 0, W, H, S(13), fill=C_CARD, outline=C_LINE)
        rrect(cv, 0, S(16), S(4), H - S(16), S(2), fill=C_ACCENT, outline="")

        cv.create_text(S(18), S(24), anchor="w", text="⏰   提醒",
                       fill=C_ACCENT, font=app.f_small_b)
        title = task["title"]
        cv.create_text(S(18), S(53), anchor="w",
                       text=fit_text(app.f_pop, title, W - S(40)),
                       fill=C_TEXT, font=app.f_pop)
        cv.create_text(S(18), S(77), anchor="w",
                       text=fmt_due(task["due"]) if task["due"] else "",
                       fill=C_SUB, font=app.f_small)

        # 按钮（右对齐，从右往左排）
        bh = S(25)
        by1 = H - S(10)
        by0 = by1 - bh
        w2 = S(104)
        x2r = W - S(13)
        x2l = x2r - w2
        w1 = S(60)
        x1r = x2l - S(8)
        x1l = x1r - w1

        def mk(text, x0, x1, bg, fg, cmd):
            bid = rrect(cv, x0, by0, x1, by1, S(7), fill=bg, outline="")
            tid = cv.create_text((x0 + x1) / 2.0, (by0 + by1) / 2.0 - 1, text=text,
                                 fill=fg, font=app.f_small)
            cv.tag_bind(bid, "<Button-1>", lambda e: cmd())
            cv.tag_bind(tid, "<Button-1>", lambda e: cmd())
            cv.tag_bind(bid, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(tid, "<Enter>", lambda e: cv.configure(cursor="hand2"))

        mk("完成", x1l, x1r, C_GREEN, C_ON_GREEN, self._done)
        mk("稍后 5 分钟", x2l, x2r, C_CARD_HI, C_TEXT, self._snooze)
        # 关闭按钮
        cid = cv.create_text(W - S(16), S(16), text="✕", fill=C_DIM, font=app.f_small)
        cv.tag_bind(cid, "<Button-1>", lambda e: self.close())

        # 剩余进度条
        self.pbar = cv.create_rectangle(0, H - S(3), W, H, fill=C_ACCENT, outline="")
        self.cv = cv
        self.W = W
        self.H = H
        self.life = 20000.0
        self.deadline = time.time() + self.life / 1000.0

        Popup._live.append(self)
        self._fade_in(0.0)
        self._tick()

        try:
            if winsound:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def _fade_in(self, a):
        if not self.win.winfo_exists():
            return
        a = min(0.99, a + 0.12)
        self.win.attributes("-alpha", a)
        if a < 0.99:
            self.win.after(16, lambda: self._fade_in(a))

    def _tick(self):
        if not self.win.winfo_exists():
            return
        left = self.deadline - time.time()
        if left <= 0:
            self.close()
            return
        try:
            w = max(0, int(self.W * (left / (self.life / 1000.0))))
            self.cv.coords(self.pbar, 0, self.H - S(3), w, self.H)
        except Exception:
            pass
        self.win.after(100, self._tick)

    def _done(self):
        self.task["done"] = True
        self.app.save()
        self.app.refresh()
        self.close()

    def _snooze(self):
        self.task["due"] = time.time() + 300
        self.task["notified"] = False
        self.app.save()
        self.app.refresh()
        self.close()

    def close(self):
        try:
            if self in Popup._live:
                Popup._live.remove(self)
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        try:
            self.app.relayout_popups()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# 主程序
# ----------------------------------------------------------------------------
class App(object):
    def __init__(self):
        self.cfg = load_config()
        set_palette(self.cfg.get("theme", "dark"))
        self.theme = THEME

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(WIN_TITLE)
        self.root.configure(bg=C_BG)
        self.root.overrideredirect(True)

        self.root.tk.call("tk", "scaling", SC * 96.0 / 72.0)

        self.f_title = tkfont.Font(family=YAHEI, size=10)
        self.f_strike = tkfont.Font(family=YAHEI, size=10, overstrike=1)
        self.f_small = tkfont.Font(family=YAHEI, size=8)
        self.f_small_b = tkfont.Font(family=YAHEI, size=8, weight="bold")
        self.f_body = tkfont.Font(family=YAHEI, size=10)
        self.f_body_b = tkfont.Font(family=YAHEI, size=10, weight="bold")
        self.f_h1 = tkfont.Font(family=YAHEI, size=13, weight="bold")
        self.f_pop = tkfont.Font(family=YAHEI, size=11, weight="bold")
        self.f_icon = tkfont.Font(family=YAHEI, size=9)
        self.f_mdl = tkfont.Font(family="Segoe MDL2 Assets", size=9)
        self.f_wheel = tkfont.Font(family=YAHEI, size=9)
        self.f_wheel_sel = tkfont.Font(family=YAHEI, size=11, weight="bold")

        self.tasks = load_tasks()
        self.ui_queue = queue.Queue()
        self.rows = []
        self._drag = None
        self._first_hide = True
        self.show_done = False

        self._build_window()
        self._build_ui()
        self.refresh()

        self.tray = Tray(self.ui_queue)
        self.tray.start()

        self.root.report_callback_exception = _log_exc
        self.root.after(60, self._first_show)
        self.root.after(200, self._poll)
        self.root.after(1000, self._tick_reminders)

        # 启动时把太久以前的过期任务静默掉
        now = time.time()
        for t in self.tasks:
            if (not t["done"]) and t["due"] and (not t["notified"]) and t["due"] < now - 86400:
                t["notified"] = True
        save_tasks(self.tasks)

    # ---------------- 窗口 ----------------
    def f_icon_mdl(self):
        if not hasattr(self, "_f_mdl_btn"):
            self._f_mdl_btn = tkfont.Font(family="Segoe MDL2 Assets", size=10)
        return self._f_mdl_btn

    def set_theme(self, name, persist=True):
        if name not in PALETTES or name == self.theme:
            return
        set_palette(name)
        self.theme = name
        if persist:
            self.cfg["theme"] = name
            save_config(self.cfg)
        try:
            self.root.configure(bg=C_BG)
        except Exception:
            pass
        self.rebuild_ui()

    def toggle_theme(self):
        self.set_theme("light" if self.theme == "dark" else "dark")

    def rebuild_ui(self):
        for p in list(Popup._live):
            try:
                p.win.destroy()
            except Exception:
                pass
        try:
            del Popup._live[:]
        except Exception:
            pass
        for w in list(self.root.winfo_children()):
            if isinstance(w, tk.Menu):
                continue
            try:
                w.destroy()
            except Exception:
                pass
        self.rows = []
        self._drag = None
        self._build_ui()
        self.refresh()
        try:
            self.e_title.clear()      # 保证提示文字处于干净状态
            self.e_title.focus()
        except Exception:
            pass

    def _build_window(self):
        W = S(430)
        H = S(680)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        try:
            rc = wt.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)
            sh = rc.bottom - rc.top
        except Exception:
            pass
        H = min(H, sh - S(70))
        x = (sw - W) // 2
        y = max(S(20), (sh - H) // 2 - S(20))
        self.root.geometry("%dx%d+%d+%d" % (W, H, x, y))
        self.W = W
        self.H = H

        self.root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        try:
            self.root.update()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        except Exception:
            pass
        if not hwnd:
            hwnd = self.root.winfo_id()
        self.hwnd = hwnd
        try:
            user32.SetWindowTextW(hwnd, WIN_TITLE)
        except Exception:
            pass
        # Win11 圆角
        try:
            v = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(v), 4)
        except Exception:
            pass
        # 阴影
        try:
            GWL_STYLE = -26
            CS_DROPSHADOW = 0x00020000
            st = user32.GetClassLongW(hwnd, GWL_STYLE)
            user32.SetClassLongW(hwnd, GWL_STYLE, st | CS_DROPSHADOW)
        except Exception:
            pass

    def _build_ui(self):
        root = self.root
        outer = tk.Frame(root, bg=C_BG, bd=0, highlightthickness=1,
                         highlightbackground=C_LINE, highlightcolor=C_LINE)
        outer.pack(fill="both", expand=True)

        # ---- header ----
        header = tk.Frame(outer, bg=C_BG, height=S(56))
        header.pack(fill="x", padx=S(16), pady=(S(12), 0))
        header.pack_propagate(False)

        logo = tk.Canvas(header, width=S(26), height=S(26), bg=C_BG,
                         highlightthickness=0, bd=0)
        logo.pack(side="left", pady=(S(2), 0))
        logo.create_oval(S(1), S(1), S(25), S(25), fill=C_ACCENT, outline="")
        logo.create_line(S(7), S(13), S(11.5), S(18), S(19.5), S(8),
                         fill=C_ON_ACCENT, width=max(2, S(2.4)),
                         capstyle="round", joinstyle="round")

        titles = tk.Frame(header, bg=C_BG)
        titles.pack(side="left", padx=(S(10), 0), pady=(S(2), 0))
        ttl = tk.Label(titles, text=APP_NAME, font=self.f_h1, bg=C_BG,
                       fg=C_TEXT, anchor="w")
        ttl.pack(anchor="w")
        d = date.today()
        self.lbl_date = tk.Label(titles, text="%d月%d日  %s" % (d.month, d.day,
                                                               WEEK_CN[d.weekday()]),
                                 font=self.f_small, bg=C_BG, fg=C_SUB, anchor="w")
        self.lbl_date.pack(anchor="w", pady=(S(1), 0))

        close = IconBtn(header, "\ue8bb", self.hide_window, self.f_icon_mdl(),
                        size=26, fg=C_SUB, hover_fg=C_RED)
        close.pack(side="right", pady=(S(2), 0))
        mini = IconBtn(header, "\ue921", self.hide_window, self.f_icon_mdl(),
                       size=26, fg=C_SUB, hover_fg=C_TEXT)
        mini.pack(side="right", padx=(0, S(2)), pady=(S(2), 0))
        self.btn_theme = IconBtn(header, "\ue706" if THEME == "dark" else "\ue708",
                                 self.toggle_theme, self.f_icon_mdl(),
                                 size=26, fg=C_SUB, hover_fg=C_ACCENT)
        self.btn_theme.pack(side="right", padx=(0, S(2)), pady=(S(2), 0))

        for w in (header, ttl, logo, titles):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # ---- 输入区 ----
        inp = tk.Frame(outer, bg=C_BG)
        inp.pack(fill="x", padx=S(16), pady=(S(14), S(4)))

        self.e_title = RoundEntry(inp, "要做什么？例如：给客户回电话 明天9点", self.f_body,
                                  height=48, radius=14)
        self.e_title.pack(fill="x")
        self.e_title.entry.bind("<Return>", lambda e: self.add_task())
        self.e_title.entry.bind("<Down>", lambda e: self.time_btn.open_picker())

        row2 = tk.Frame(inp, bg=C_BG)
        row2.pack(fill="x", pady=(S(10), 0))

        self.btn_add = Btn(row2, "添 加", self.add_task, self.f_body,
                           w=86, h=40, radius=13)
        self.btn_add.pack(side="right", padx=(S(10), 0))

        self.time_btn = TimeButton(row2, self)
        self.time_btn.pack(side="left", fill="x", expand=True)

        self.msg = tk.Label(inp, text="", font=self.f_small, bg=C_BG, fg=C_RED,
                            anchor="w", height=1)
        self.msg.pack(fill="x", pady=(S(2), 0))

        sp0 = tk.Frame(outer, bg=C_BG, height=S(2))
        sp0.pack(fill="x")

        # ---- 列表 ----
        listwrap = tk.Frame(outer, bg=C_BG)
        listwrap.pack(fill="both", expand=True, padx=(S(14), S(4)))

        self.canvas = tk.Canvas(listwrap, bg=C_BG, highlightthickness=0, bd=0)
        self.sb = SlimScroll(listwrap, self.canvas)
        self.canvas.configure(yscrollcommand=self._on_scroll_set)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=C_BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._inner_conf)
        self.canvas.bind("<Configure>", self._canvas_conf)
        for w in (self.canvas, self.inner):
            w.bind("<MouseWheel>", self._on_wheel)

        # ---- footer ----
        sep = tk.Frame(outer, bg=C_SEP, height=1)
        sep.pack(fill="x", padx=S(14))
        foot = tk.Frame(outer, bg=C_BG, height=S(34))
        foot.pack(fill="x", padx=S(16), pady=(0, S(8)))
        foot.pack_propagate(False)
        self.lbl_foot = tk.Label(foot, text="", font=self.f_small, bg=C_BG, fg=C_DIM)
        self.lbl_foot.pack(side="left", pady=(S(6), 0))
        self.lnk_clear = tk.Label(foot, text="清空已完成", font=self.f_small, bg=C_BG,
                                  fg=C_DIM, cursor="hand2")
        self.lnk_clear.pack(side="right", pady=(S(6), 0))
        self.lnk_clear.bind("<Button-1>", lambda e: self.clear_done())
        self.lnk_clear.bind("<Enter>", lambda e: self.lnk_clear.configure(fg=C_TEXT))
        self.lnk_clear.bind("<Leave>", lambda e: self.lnk_clear.configure(fg=C_DIM))

        self.e_title.focus()

    def _drag_start(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        if not self._drag:
            return
        x = e.x_root - self._drag[0]
        y = e.y_root - self._drag[1]
        self.root.geometry("+%d+%d" % (x, y))

    def _on_scroll_set(self, a, b):
        self.sb.set(a, b)

    def _inner_conf(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._on_scroll_set(*self.canvas.yview())

    def _canvas_conf(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)

    def _on_wheel(self, e):
        if self.canvas.bbox("all") is None:
            return
        x1, y1, x2, y2 = self.canvas.bbox("all")
        if (y2 - y1) <= self.canvas.winfo_height():
            return
        self.canvas.yview_scroll(int(-1 * (e.delta / 120) * 3), "units")

    # ---------------- 逻辑 ----------------
    def add_task(self):
        raw = self.e_title.value()
        if not raw:
            self._flash("先写一下要做什么吧")
            self.e_title.focus()
            return

        # 标题末尾带时间短语（如「回电话 明天9点」）则直接采用；否则用时间选择器
        title, inline_due = split_time_phrase(raw)
        due = inline_due or (self.time_btn.ts or 0)
        self.tasks.append({
            "id": new_id(),
            "title": title,
            "due": due,
            "done": False,
            "notified": False,
            "created": time.time(),
        })
        self.save()
        self.e_title.clear()
        self.time_btn.set_ts(0)
        self.msg.configure(text="")
        self.refresh()
        self.e_title.focus()
        self.canvas.yview_moveto(0)

    def edit_task(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                EditDialog(self, t)
                return

    def _flash(self, text):
        self.msg.configure(text=text)
        if getattr(self, "_flash_after", None):
            try:
                self.root.after_cancel(self._flash_after)
            except Exception:
                pass
        self._flash_after = self.root.after(2600, lambda: self.msg.configure(text=""))

    def toggle_task(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                t["done"] = not t["done"]
                if t["done"]:
                    t["notified"] = True
                break
        self.save()
        self.refresh()

    def delete_task(self, tid):
        self.tasks = [t for t in self.tasks if t["id"] != tid]
        self.save()
        self.refresh()

    def clear_done(self):
        n = len([t for t in self.tasks if t["done"]])
        if not n:
            return
        self.tasks = [t for t in self.tasks if not t["done"]]
        self.save()
        self.refresh()

    @staticmethod
    def _group_of(t, now, today):
        if t["done"]:
            return "done"
        due = t["due"]
        if not due:
            return "someday"
        if due < now:
            return "overdue"
        d = datetime.fromtimestamp(due).date()
        if d == today:
            return "today"
        if d == today + timedelta(days=1):
            return "tomorrow"
        if d <= today + timedelta(days=7):
            return "week"
        return "later"

    def _add_group(self, label, n, danger=False, key=None):
        f = tk.Frame(self.inner, bg=C_BG)
        f.pack(fill="x", pady=(S(10), S(6)))
        if key == "done":
            arrow = "▾ " if self.show_done else "▸ "
            lbl = tk.Label(f, text=arrow + label, font=self.f_small_b, bg=C_BG,
                           fg=C_GROUP_DONE, cursor="hand2")
            lbl.bind("<Button-1>", lambda e: self.toggle_done())
        else:
            lbl = tk.Label(f, text=label, font=self.f_small_b, bg=C_BG,
                           fg=C_RED if danger else C_GROUP)
        lbl.pack(side="left", padx=(S(3), 0))
        num = tk.Label(f, text=str(n), font=self.f_small, bg=C_BG,
                       fg=C_RED if danger else C_COUNT)
        num.pack(side="left", padx=(S(6), 0))
        if key == "done":
            num.bind("<Button-1>", lambda e: self.toggle_done())
        line = tk.Frame(f, bg=C_SEP, height=1)
        line.pack(side="left", fill="x", expand=True, padx=(S(10), S(3)), pady=(S(1), 0))
        self.rows.append(f)

    def toggle_done(self):
        self.show_done = not self.show_done
        self.refresh()

    def refresh(self):
        for r in self.rows:
            r.destroy()
        self.rows = []
        now = time.time()
        today = date.today()

        self._empty = None
        if not self.tasks:
            self._build_empty()
        else:
            buckets = {}
            for t in self.tasks:
                buckets.setdefault(self._group_of(t, now, today), []).append(t)
            for key, label in (("overdue", "已逾期"), ("today", "今天"),
                               ("tomorrow", "明天"), ("week", "本周内"),
                               ("later", "以后"), ("someday", "随时"),
                               ("done", "已完成")):
                items = buckets.get(key)
                if not items:
                    continue
                items.sort(key=lambda x: (1 if not x["due"] else 0,
                                          x["due"] or x["created"]))
                self._add_group(label, len(items), key == "overdue", key)
                if key == "done" and not self.show_done:
                    continue
                for t in items:
                    row = TaskRow(self.inner, self, t)
                    row.pack(fill="x", pady=(0, S(5)))
                    self.rows.append(row)

        sp = tk.Frame(self.inner, bg=C_BG, height=S(4))
        sp.pack(fill="x")
        self.rows.append(sp)

        n_open = len([t for t in self.tasks if not t["done"]])
        n_done = len([t for t in self.tasks if t["done"]])
        if not self.tasks:
            self.lbl_foot.configure(text="共 0 个任务")
        else:
            self.lbl_foot.configure(text="%d 个待办 · %d 个已完成" % (n_open, n_done))
        self.lnk_clear.configure(text=("清空已完成 (%d)" % n_done) if n_done else "")

        self.inner.update_idletasks()
        if self._empty is not None:
            try:
                vis = self.canvas.winfo_height()
                need = self._empty.winfo_reqheight()
                pad = max(S(30), (vis - need) // 2 - S(6))
                self._empty.pack_configure(pady=(pad, 0))
                self.inner.update_idletasks()
            except Exception:
                pass
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._on_scroll_set(*self.canvas.yview())

    def save(self):
        save_tasks(self.tasks)

    def _build_empty(self):
        f = tk.Frame(self.inner, bg=C_BG)
        f.pack(fill="x", pady=(S(40), 0))
        self._empty = f
        c = tk.Canvas(f, width=S(84), height=S(84), bg=C_BG, highlightthickness=0)
        c.pack()
        c.create_oval(0, 0, S(84), S(84), fill=C_ACCENT_SOFT, outline="")
        cx = cy = S(42)
        c.create_oval(cx - S(18), cy - S(18), cx + S(18), cy + S(18),
                      outline=C_ACCENT, width=max(2, S(2.2)))
        c.create_line(cx, cy, cx, cy - S(10), fill=C_ACCENT,
                      width=max(2, S(2.2)), capstyle="round")
        c.create_line(cx, cy, cx + S(8), cy + S(5), fill=C_ACCENT,
                      width=max(2, S(2.2)), capstyle="round")
        c.create_oval(cx - S(2), cy - S(2), cx + S(2), cy + S(2),
                      fill=C_ACCENT, outline="")
        tk.Label(f, text="还没有任务", font=self.f_body_b, bg=C_BG,
                 fg=C_TEXT).pack(pady=(S(16), 0))
        tk.Label(f, text="在上面写一条，时间也可以直接带在标题里",
                 font=self.f_small, bg=C_BG, fg=C_DIM).pack(pady=(S(5), 0))
        self.rows.append(f)

    # ---------------- 提醒 ----------------
    def _tick_reminders(self):
        now = time.time()
        fired = []
        for t in self.tasks:
            if t["done"] or t.get("notified") or not t["due"]:
                continue
            if t["due"] <= now:
                t["notified"] = True
                fired.append(t)
        if fired:
            self.save()
            self.refresh()
            for t in fired[:4]:
                Popup(self, t)
            if len(fired) > 4:
                self.tray.notify(APP_NAME, "还有 %d 个任务同时到点了" % (len(fired) - 4))
        self.root.after(1000, self._tick_reminders)

    def relayout_popups(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        try:
            rc = wt.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)
            sh, sw = rc.bottom, rc.right
        except Exception:
            pass
        for i, p in enumerate(list(Popup._live)):
            try:
                W = p.W
                H = p.H
                x = sw - W - S(22)
                y = sh - S(22) - H - i * (H + S(10))
                p.win.geometry("+%d+%d" % (x, y))
            except Exception:
                pass

    # ---------------- 托盘交互 ----------------
    def _poll(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                if kind == "tray_show":
                    self.show_window()
                elif kind == "tray_menu":
                    self._popup_menu(item[1], item[2])
        except queue.Empty:
            pass
        except Exception:
            _log_exc(*sys.exc_info())
        self.root.after(150, self._poll)

    def _popup_menu(self, x, y):
        for w in list(self.root.winfo_children()):
            if isinstance(w, tk.Menu):
                try:
                    w.destroy()
                except Exception:
                    pass
        m = tk.Menu(self.root, tearoff=0, bg=C_CARD, fg=C_TEXT,
                    activebackground=C_ACCENT, activeforeground=C_ON_ACCENT,
                    bd=0, relief="flat", font=self.f_small)
        m.add_command(label="   打开清单   ", command=self.show_window)
        m.add_command(label="   添加任务   ", command=self.show_window)
        m.add_separator()
        self._var_startup = tk.BooleanVar(value=self.is_startup())
        m.add_checkbutton(label="开机自动启动", variable=self._var_startup,
                          command=self.toggle_startup)
        self._var_dark = tk.BooleanVar(value=(THEME == "dark"))
        m.add_checkbutton(label="深色模式", variable=self._var_dark,
                          command=self._toggle_dark_var)
        m.add_separator()
        m.add_command(label="   退出   ", command=self.quit)
        try:
            m.tk_popup(x, y)
        finally:
            try:
                m.grab_release()
            except Exception:
                pass

    def show_window(self, force=True):
        try:
            self.root.deiconify()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.after(140, lambda: self.root.attributes("-topmost", False))
            self.root.lift()
            if force:
                self.root.focus_force()
                if not self.e_title.value():
                    self.e_title.clear()
                self.e_title.focus_set()
        except Exception:
            pass

    def _first_show(self):
        if "--silent" in sys.argv:
            self.root.withdraw()
            self.root.after(900, lambda: self.tray.notify(
                APP_NAME, "已在后台运行，到点会提醒你。双击托盘图标打开清单。"))
            return
        self.show_window(force=True)
        try:
            self.root.attributes("-alpha", 0.0)
            self._fade(0.0)
        except Exception:
            pass

    def _fade(self, a):
        a = min(1.0, a + 0.14)
        try:
            self.root.attributes("-alpha", a)
        except Exception:
            return
        if a < 1.0:
            self.root.after(14, lambda: self._fade(a))

    def hide_window(self):
        if not getattr(self, "tray", None) or not self.tray.ok:
            self.quit()
            return
        self.root.withdraw()
        if self._first_hide:
            self._first_hide = False
            self.root.after(300, lambda: self.tray.notify(
                APP_NAME + " 仍在运行",
                "已最小化到托盘，到点会自动弹出提醒。双击托盘图标可重新打开。"))

    def _toggle_dark_var(self):
        want = "dark" if self._var_dark.get() else "light"
        try:
            self.root.after(90, lambda: self.set_theme(want))
        except Exception:
            pass

    def is_startup(self):
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run")
            try:
                winreg.QueryValueEx(k, APP_ID)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(k)
        except Exception:
            return False

    def toggle_startup(self):
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                               winreg.KEY_SET_VALUE)
            if self._var_startup.get():
                if getattr(sys, "frozen", False):
                    cmd = '"%s" --silent' % sys.executable
                else:
                    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                    if not os.path.exists(pyw):
                        pyw = sys.executable
                    cmd = '"%s" "%s" --silent' % (pyw, os.path.abspath(__file__))
                winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, APP_ID)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(k)
        except Exception:
            pass

    def quit(self):
        try:
            self.save()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


# ----------------------------------------------------------------------------
def _log_exc(exc_type, exc, tb):
    import traceback
    _log_line("".join(traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = _log_exc


def single_instance_ok():
    """已有实例时提示并返回 False"""
    try:
        kernel32.CreateMutexW(None, False, "Local\\ReminderDesk_Instance")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            hwnd = user32.FindWindowW(None, "ReminderDeskTrayWnd")
            if hwnd:
                user32.PostMessageW(ctypes.c_void_p(hwnd), WM_SHOW, 0, 0)
                return False
            hwnd = user32.FindWindowW(None, WIN_TITLE)
            if hwnd:
                user32.ShowWindow(ctypes.c_void_p(hwnd), 9)
                user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
                return False
            user32.MessageBoxW(None,
                               "「小提醒」已经在运行了，\n请查看屏幕右下角的托盘图标。",
                               APP_NAME, 0x40)
            return False
    except Exception:
        pass
    return True


def main():
    if not single_instance_ok():
        sys.exit(0)
    app = App()
    app.run()


if __name__ == "__main__":
    main()
