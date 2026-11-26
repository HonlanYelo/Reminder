# -*- coding: utf-8 -*-
"""交互流程自测：添加 / 编辑 / 滚轮选时间"""
import importlib.util
import os
import tempfile
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rm", os.path.join(HERE, "reminder.pyw"))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

tmp = tempfile.mkdtemp()
rm.DATA_DIR = tmp
rm.DATA_FILE = os.path.join(tmp, "tasks.json")
rm.ensure_dir()

fails = []


def check(name, cond, extra=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        print("  FAIL  %s  %s" % (name, extra))
        fails.append(name)


app = rm.App()
app.root.deiconify()
for _ in range(20):
    app.root.update()
    time.sleep(0.02)

print("[1] 添加任务")
app.e_title.set_text("测试一条任务")
t_ts = (datetime.now() + timedelta(hours=2)).replace(second=0, microsecond=0).timestamp()
app.time_btn.set_ts(t_ts)
app.add_task()
check("任务已加入", len(app.tasks) == 1, str(len(app.tasks)))
check("标题正确", app.tasks[0]["title"] == "测试一条任务", app.tasks[0]["title"])
check("时间写入", abs(app.tasks[0]["due"] - t_ts) < 1)
check("添加后清空输入", app.e_title.value() == "")
check("添加后时间复位", app.time_btn.ts == 0)
check("生成了一行", len([r for r in app.rows if isinstance(r, rm.TaskRow)]) == 1)

print("[2] 空标题拦截")
n = len(app.tasks)
app.add_task()
check("空标题不添加", len(app.tasks) == n)

print("[3] 滚轮时间选择器")
picked = {}


def on_ok(ts):
    picked["ts"] = ts


app.time_btn.set_ts(0)
p = rm.DateTimePicker(app, app.time_btn, 0, on_ok)
pump_end = time.time() + 0.2
while time.time() < pump_end:
    app.root.update()
check("滚轮默认是 30 分钟后",
      abs(p._selected() - datetime.now()).total_seconds() < 2000)

p.w_date.set_index(2)   # 后天
p.w_hour.set_index(15)  # 15 时
p.w_min.set_index(6)    # 30 分
sel = p._selected()
check("滚轮组合正确",
      (sel.hour, sel.minute) == (15, 30) and
      sel.date() == (datetime.now() + timedelta(days=2)).date(), str(sel))
p._confirm()
check("确定回调拿到时间", abs(picked.get("ts", 0) - sel.timestamp()) < 1, str(picked))

print("[4] 不提醒")
picked.clear()
p2 = rm.DateTimePicker(app, app.time_btn, 0, on_ok)
two_days = datetime.now() + timedelta(days=2)
p2.w_date.set_index(3)  # 超过 2 天应显示日期
lbl = p2.w_date.items[3]
check("日期列显示月日", ("月" in lbl and "日" in lbl), lbl)
p2._pick_none()
check("不提醒返回 0", picked.get("ts") == 0, str(picked))

print("[5] 编辑任务")
task = app.tasks[0]
dlg = rm.EditDialog(app, task)
for _ in range(10):
    app.root.update()
check("编辑框预填标题", dlg.e_title.value() == task["title"], dlg.e_title.value())
new_ts = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0,
                                                     microsecond=0).timestamp()
dlg.e_title.set_text("改过的标题")
dlg._set_due(new_ts)
dlg.save()
check("标题已更新", task["title"] == "改过的标题", task["title"])
check("时间已更新", abs(task["due"] - new_ts) < 1)
check("重新待提醒", task["notified"] is False)

print("[6] 编辑为不提醒")
dlg2 = rm.EditDialog(app, task)
for _ in range(10):
    app.root.update()
dlg2.clear_time()
dlg2.save()
check("时间被清除", task["due"] == 0, str(task["due"]))
check("分组变为随时", app._group_of(task, time.time(), datetime.now().date()) == "someday")

print("[7] 勾选与删除")
app.toggle_task(task["id"])
check("标记完成", task["done"] is True)
check("分组变为已完成", app._group_of(task, time.time(), datetime.now().date()) == "done")
app.delete_task(task["id"])
check("任务被删除", len(app.tasks) == 0, str(len(app.tasks)))
check("回到空状态", len([r for r in app.rows if isinstance(r, rm.TaskRow)]) == 0)

print("[8] 分组判定")
now = time.time()
today = datetime.now().date()
cases = [
    ({"done": False, "due": now - 60}, "overdue"),
    ({"done": False, "due": now + 600}, "today"),
    ({"done": False, "due": (datetime.now() + timedelta(days=1)).replace(hour=23).timestamp()}, "tomorrow"),
    ({"done": False, "due": (datetime.now() + timedelta(days=4)).timestamp()}, "week"),
    ({"done": False, "due": (datetime.now() + timedelta(days=20)).timestamp()}, "later"),
    ({"done": False, "due": 0}, "someday"),
    ({"done": True, "due": now}, "done"),
]
for t, expect in cases:
    got = app._group_of(t, now, today)
    check("group %s -> %s" % (expect, got), got == expect)

print("[9] 持久化往返")
app.tasks.append({"id": "z1", "title": "持久化", "due": now + 100,
                  "done": False, "notified": False, "created": now})
app.save()
loaded = rm.load_tasks()
check("重新加载", len(loaded) == 1 and loaded[0]["title"] == "持久化")

app.quit()
print("\n结果: %s" % ("全部通过" if not fails else "失败 %d 项: %s" % (len(fails), fails)))
