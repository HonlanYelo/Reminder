# -*- coding: utf-8 -*-
"""逻辑自测：不打扰鼠标，直接调用 App 的方法验证核心行为"""
import importlib.util
import os
import sys
import time
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rm", os.path.join(HERE, "reminder.pyw"))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

# 用临时数据文件
tmpdir = tempfile.mkdtemp()
rm.DATA_DIR = tmpdir
rm.DATA_FILE = os.path.join(tmpdir, "tasks.json")
rm.ensure_dir()

fails = []


def check(name, cond, extra=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        print("  FAIL  %s  %s" % (name, extra))
        fails.append(name)


print("[1] 时间解析")
now = datetime.now()
cases = [
    ("18:30", (18, 30), True),
    ("0830", (8, 30), True),
    ("+30m", None, True),
    ("+2h", None, True),
    ("明天9点", (9, 0), True),
    ("今晚8点", (20, 0), True),
    ("下午3点", (15, 0), True),
    ("11-28 14:00", (14, 0), True),
    ("2026-12-01 07:05", (7, 5), True),
]
for text, hm, ok in cases:
    dt, valid = rm.parse_when(text)
    cond = valid == ok and (hm is None or (dt and (dt.hour, dt.minute) == hm))
    check("%r -> %s" % (text, dt.strftime("%m-%d %H:%M") if dt else None), cond, str(dt))

check("空字符串 -> None/合法", rm.parse_when("") == (None, True))
dt, ok = rm.parse_when("胡说八道")
check("非法输入被拒", (dt is None and ok is False), str((dt, ok)))

dt, _ = rm.parse_when("+30m")
check("相对时间 +30m 约等于 30 分钟后",
      dt and abs((dt - now).total_seconds() - 1800) < 70, str(dt))

dt, _ = rm.parse_when("18:30")
if dt:
    check("纯时间已过则顺延到明天", dt >= datetime.now() - timedelta(minutes=1), str(dt))

print("[2] 任务增删改")
app = rm.App()
app.root.withdraw()

app.e_title._showing = False
app.e_title.delete(0, "end")
app.e_title.insert(0, "测试任务 A")
app.e_when._showing = False
app.e_when.delete(0, "end")
app.e_when.insert(0, "明天 10:00")
app.add_task()
check("添加后任务数 = 1", len(app.tasks) == 1, str(len(app.tasks)))
check("标题正确", app.tasks[0]["title"] == "测试任务 A", app.tasks[0]["title"])
check("提醒时间已解析", app.tasks[0]["due"] > time.time(), str(app.tasks[0]["due"]))
check("列表生成了 1 行", len([r for r in app.rows if isinstance(r, rm.TaskRow)]) == 1)

app.e_title._showing = False
app.e_title.delete(0, "end")
app.e_title.insert(0, "无时间任务")
app.e_when._showing = False
app.e_when.delete(0, "end")
app.add_task()
check("无时间任务 due=0", app.tasks[1]["due"] == 0, str(app.tasks[1]["due"]))

tid = app.tasks[0]["id"]
app.toggle_task(tid)
check("标记完成", app.tasks[0]["done"] is True)
app.toggle_task(tid)
check("取消完成", app.tasks[0]["done"] is False)

print("[3] 持久化")
rm.save_tasks(app.tasks)
loaded = rm.load_tasks()
check("重新加载数量一致", len(loaded) == 2, str(len(loaded)))
check("字段完整", set(loaded[0].keys()) == {"id", "title", "due", "done", "notified", "created"},
      str(loaded[0].keys()))

print("[4] 到期提醒触发")
past = time.time() - 5
app.tasks.append({"id": "x1", "title": "马上就到点", "due": past,
                  "done": False, "notified": False, "created": time.time()})
app.refresh()
n_before = len(rm.Popup._live)
app._tick_reminders()
check("触发后标记为已提醒", app.tasks[-1]["notified"] is True)
check("弹出了提醒窗", len(rm.Popup._live) > n_before,
      "%d -> %d" % (n_before, len(rm.Popup._live)))

print("[4b] 弹窗按钮行为")
tk_task = {"id": "y1", "title": "按钮测试", "due": time.time() + 60,
           "done": False, "notified": True, "created": time.time()}
app.tasks.append(tk_task)
pop = rm.Popup(app, tk_task)
before = time.time()
pop._snooze()
check("稍后5分钟推迟了时间", abs(tk_task["due"] - (before + 300)) < 3, str(tk_task["due"] - before))
check("稍后后重新待提醒", tk_task["notified"] is False)
pop2 = rm.Popup(app, tk_task)
pop2._done()
check("点完成后标记完成", tk_task["done"] is True)
app.tasks.remove(tk_task)

print("[5] 删除与清理")
app.delete_task("x1")
check("删除后数量", len(app.tasks) == 2, str(len(app.tasks)))
for t in app.tasks:
    t["done"] = True
app.refresh()
app.clear_done()
check("清空已完成", len(app.tasks) == 0, str(len(app.tasks)))

print("[6] 托盘")
for _ in range(20):
    app.root.update()
    time.sleep(0.05)
check("托盘图标创建成功", app.tray.ok is True, str(app.tray.ok))

app.quit()
print("\n结果: %s" % ("全部通过" if not fails else "失败 %d 项: %s" % (len(fails), fails)))
sys.exit(0 if not fails else 1)
