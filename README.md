# Reminder · 小提醒

提醒你到点了，做什么任务。

一个 Windows 桌面待办 + 定时提醒小工具。纯 Python 标准库实现（tkinter + ctypes），
无第三方依赖，打包后单个 exe 约 10 MB，常驻后台内存约 30 MB、空闲 CPU 接近 0。

## 功能

**任务清单**
- 输入标题即可添加；填了提醒时间就到点提醒，留空则作为普通待办
- 列表按时间自动分组：已逾期 / 今天 / 明天 / 本周内 / 以后 / 随时 / 已完成
- 逾期任务左侧红色竖条 + 红色勾选圈，副标题拆分为「时间（灰） + 已超时 N 分钟（红）」
- 点左侧圆圈 = 完成 / 取消完成；点行任意位置 = 编辑；行尾 ✕ = 删除
- 「已完成」默认折叠成可点击的标题，清单不会越用越长

**时间选择**
- 点击时间胶囊弹出三列滚轮（日期 / 小时 / 分钟）
- 滚一格走一整项，松手立即对位；带缓动动画
- 鼠标在弹层任意位置都能滚，落在哪一列就滚哪一列
- 键盘：↑ ↓ 调整当前列，Tab / ← → 切换列，Enter 确定，Esc 取消
- 右上角实时显示「1.5 小时后」这类相对提示，选到过去的时间会提示「已过去」
- 底部「不提醒」把任务设为纯待办

**到点提醒**
- 屏幕右下角弹出无焦点提醒卡片，不打断正在打字的窗口
- 同时播放提示音 + 托盘气泡
- 20 秒后自动收起，可点「完成」或「稍后 5 分钟」

**常驻与主题**
- 点 ✕ 收进系统托盘，到点照样提醒；双击托盘图标唤回窗口
- 重复双击桌面图标不会开第二个进程，只会唤起已有窗口
- 托盘右键菜单：打开清单 / 添加任务 / 深色模式 / 开机自动启动 / 退出（退出菜单需在托盘图标上右键）
- 深色 / 浅色主题一键切换，记在配置文件里，下次打开沿用

## 运行

需要 Python 3.8+（带 tkinter，Windows 官方安装包默认包含）。

```bash
pythonw reminder.pyw
```

`--silent` 参数为静默启动（只驻留托盘，不弹窗），开机自启用的就是这个。

## 打包成 exe

```bash
python make_icon.py                                        # 生成 icon.ico
python -m PyInstaller --noconsole --onefile --name Reminder \
       --icon icon.ico reminder.pyw
```

产物在 `dist/Reminder.exe`，双击即可运行，目标机无需安装 Python。
`Reminder.spec` 是打包配置，也可直接 `pyinstaller Reminder.spec`。

## 数据存储

| 文件 | 内容 |
| --- | --- |
| `%APPDATA%\ReminderDesk\tasks.json` | 任务清单 |
| `%APPDATA%\ReminderDesk\config.json` | 主题等设置 |
| `%APPDATA%\ReminderDesk\error.log` | 仅在出异常时写入 |

删除 exe 不会删除数据；要彻底清干净，把这些文件一并删掉即可。

## 测试

`test_logic.py` 覆盖时间解析、排序分组、逾期判断、弹窗按钮行为；
`test_flow.py` 覆盖增删改查与主题切换的完整交互流程。

```bash
python test_logic.py
python test_flow.py
```

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `reminder.pyw` | 主程序，单文件（GUI / 托盘 / 调度 / 持久化） |
| `make_icon.py` | 纯 Python 生成多尺寸 ico，不依赖 Pillow |
| `Reminder.spec` | PyInstaller 打包配置 |
| `test_logic.py` / `test_flow.py` | 逻辑与交互回归测试 |

## 已知限制

- 仅支持 Windows：托盘图标与提醒窗口依赖 `Shell_NotifyIconW` 等 Win32 API
- 系统休眠期间错过的提醒，恢复后在下一轮扫描（约 1 秒内）补发
- 未做代码签名，首次运行 SmartScreen 可能提示「未知发布者」，点「更多信息 → 仍要运行」即可
