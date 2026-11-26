# -*- coding: utf-8 -*-
"""配色、字体与全局样式表。"""
import os

FONT_FAMILY = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'

# ---- 颜色 ----
ACCENT = "#3468f5"
ACCENT_DARK = "#2757e9"
ACCENT_SOFT = "#e6eeff"
INK = "#17213c"
TEXT = "#26324f"
LINE = "#e3e8f7"
RED = "#e5484d"
AMBER = "#d98a0b"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
CHECK_SVG = os.path.join(ASSETS, "check.svg").replace("\\", "/")
CHEVRON_SVG = os.path.join(ASSETS, "chevron-down.svg").replace("\\", "/")


def qss() -> str:
    return f"""
QWidget {{
    color: {INK};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QToolTip {{
    background: #ffffff; color: {TEXT};
    border: 1px solid {LINE}; border-radius: 6px; padding: 5px 8px;
}}

#Card {{
    background: qlineargradient(x1:0, y1:0, x2:0.85, y2:1,
        stop:0 #fbfcff, stop:0.45 #edf2ff, stop:1 #e3ebfc);
    border: 1px solid #ffffff;
    border-radius: 18px;
}}
#Sidebar {{
    background: #f3f6ff;
    border-top-left-radius: 18px;
    border-bottom-left-radius: 18px;
    border-right: 1px solid #e2e8fa;
}}
#StatusCard {{
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid #e6ebfa;
    border-radius: 12px;
}}

#TaskCard {{
    background: #ffffff;
    border: 1px solid #e6ebf8;
    border-radius: 14px;
}}
#TaskCard:hover {{
    background: #fdfeff;
    border-color: #cfdcff;
}}
#Panel {{
    background: #ffffff;
    border: 1px solid #e6ebf8;
    border-radius: 16px;
}}
#SettingCard {{
    background: #ffffff;
    border: 1px solid #e6ebf8;
    border-radius: 14px;
}}

#Search {{
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid #e2e8f8;
    border-radius: 19px;
    padding: 8px 15px 8px 34px;
    color: {INK};
    font-size: 13px;
    selection-background-color: {ACCENT};
}}
#Search:focus {{ border-color: #a8bfff; background: #ffffff; }}

#Field {{
    background: #f7f9ff;
    border: 1px solid #e3e9f9;
    border-radius: 11px;
    padding: 8px 12px;
    color: {TEXT};
    font-size: 13px;
    selection-background-color: {ACCENT};
}}
#Field:focus {{ border-color: #9db8ff; background: #ffffff; }}
QPlainTextEdit#Field {{ padding: 9px 12px; }}

QComboBox#Field::drop-down {{ border: 0; width: 24px; }}
QComboBox#Field::down-arrow {{ image: url({CHEVRON_SVG}); width: 12px; height: 12px; }}
QComboBox#Field::down-arrow:disabled {{ image: none; }}
QComboBox QAbstractItemView {{
    background: #ffffff;
    border: 1px solid #e3e9f9;
    border-radius: 10px;
    padding: 4px;
    outline: 0;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT};
}}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding-left: 8px; }}

QPushButton#Primary {{
    background: {ACCENT};
    border: 0; border-radius: 12px;
    color: #ffffff; font-size: 13px; font-weight: 600;
    padding: 10px 18px;
}}
QPushButton#Primary:hover {{ background: #2f5fe6; }}
QPushButton#Primary:pressed {{ background: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background: #b9c6e8; }}

QPushButton#Ghost {{
    background: #f2f5fd;
    border: 1px solid #e3e9f9;
    border-radius: 12px;
    color: #4a5679;
    font-size: 13px;
    padding: 10px 16px;
}}
QPushButton#Ghost:hover {{ background: #e9eeff; color: {ACCENT}; }}

#DateTimeField {{
    background: #f7f9ff;
    border: 1px solid #e3e9f9;
    border-radius: 10px;
}}
#DateTimeField:hover {{ border-color: #b7c9ff; background: #ffffff; }}
#DateTimeField[off="true"] {{
    background: #f5f6fa;
    border-color: #e8ebf4;
}}
#PickerCard {{
    background: #ffffff;
    border: 1px solid #e6ebf8;
    border-radius: 14px;
}}

#ScrollArea {{ background: transparent; border: 0; }}
#ScrollArea > QWidget > QWidget {{ background: transparent; }}
#ListHost {{ background: transparent; }}
#Stack {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: #cbd7ea; border-radius: 3px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #b3c2dd; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QCheckBox {{ color: #3a4665; spacing: 9px; font-size: 13px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1.5px solid #bcc7de;
    border-radius: 5px;
    background: #ffffff;
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url("{CHECK_SVG}");
}}
"""
