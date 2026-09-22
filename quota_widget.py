#!/usr/bin/env python3
"""quota_widget.py — 桌面侧边额度挂件 v2（tkinter，零依赖，Windows 10/11）

参考 dsh-usage / AgentLimits / VibePulse 的设计语言：
  大号核心数字 + 小字注释 + 余额走势 sparkline + 状态色彩分级 + 深色卡片（可切浅色）。
无边框、置顶、可拖动；点 ↻ 刷新，点行展开详情，右键菜单含主题切换。
配置读取同目录 quotas.json（⚙ 图形化编辑），余额历史存 history.json。
"""

import json
import os
import re
import sys
import threading
import time
import tkinter as tk
import tkinter.messagebox
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quota   # 复用查询函数与配置加载
import mascot  # 纯标准库自绘的猫咪动画帧

AVATARS = {"deepseek": "🐳"}
NAME_CN = {"deepseek": "DeepSeek"}
AUTO_REFRESH_MS = 10 * 60 * 1000
WARN_BELOW = 10.0          # 余额低于此值变橙，低于 1/4 变红
UNIT_SYMBOL = {"CNY": "¥", "USD": "$", "EUR": "€"}

THEMES = {
    "dark": dict(bg="#1b1c1f", bar="#232427", card="#232427", hover="#303237",
                 detail="#2a2c31", line="#3a3c42", text="#e8e8ea", dim="#9a9ba1",
                 value="#ffffff", accent="#4c9aff", ok="#34c759", warn="#ff9f0a",
                 err="#ff453a", field="#1b1c1f"),
    "light": dict(bg="#eef0f3", bar="#f7f8fa", card="#ffffff", hover="#eef4ff",
                  detail="#f5f6f8", line="#dcdfe4", text="#1c1c1e", dim="#8e8e93",
                  value="#111111", accent="#1b6fd8", ok="#1b8a3d", warn="#b26a00",
                  err="#c62828", field="#ffffff"),
}


def _dir():
    return os.path.dirname(os.path.abspath(__file__))


def _load_ui():
    try:
        with open(os.path.join(_dir(), "data", "ui.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_ui(ui):
    try:
        with open(os.path.join(_dir(), "data", "ui.json"), "w", encoding="utf-8") as f:
            json.dump(ui, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_history():
    try:
        with open(os.path.join(_dir(), "data", "history.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def record_history(name, value):
    """每次成功查询把余额点存进 history.json（最多 120 个点）。"""
    if value is None:
        return
    hist = load_history()
    pts = hist.setdefault(name, [])
    pts.append({"t": time.strftime("%m-%d %H:%M"), "v": round(float(value), 4)})
    hist[name] = pts[-120:]
    try:
        with open(os.path.join(_dir(), "data", "history.json"), "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False)
    except OSError:
        pass


def fmt_value(value, unit):
    if value is None:
        return "—"
    sym = UNIT_SYMBOL.get(unit, "")
    if sym:
        return f"{sym}{value:,.2f}"
    if abs(value) >= 10000:
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


class MascotLabel(tk.Label):
    """标题栏里的会动猫咪：状态跟着余额/刷新走（idle/tap/happy/worried/panic）。"""

    INTERVALS = {"idle": 430, "tap": 110, "happy": 300, "worried": 520, "panic": 260}

    def __init__(self, parent, bg, size=(32, 29)):
        super().__init__(parent, bg=bg, bd=0, cursor="hand2")
        self.frames = {k: [tk.PhotoImage(data=b) for b in v]
                       for k, v in mascot.frames_b64(*size).items()}
        self.state, self.i = "idle", 0
        self.config(image=self.frames["idle"][0])
        self._tick()

    def set_state(self, state):
        if state != self.state and state in self.frames:
            self.state, self.i = state, 0
            self.config(image=self.frames[state][0])

    def _tick(self):
        frames = self.frames[self.state]
        self.i = (self.i + 1) % len(frames)
        self.config(image=frames[self.i])
        self.after(self.INTERVALS.get(self.state, 400), self._tick)


class Row:
    """一行：头像 + 名称/注释 + 右侧大号数值 + sparkline；点击展开详情。"""

    def __init__(self, app, name, avatar, theme):
        self.name = name
        self.th = theme
        self.expanded = False
        self.lines = []
        self.value = None
        self.unit = ""

        th = theme
        self.frame = tk.Frame(app.body, bg=th["card"])
        self.head = tk.Frame(self.frame, bg=th["card"])
        self.head.pack(fill="x")

        self.lbl_avatar = tk.Label(self.head, text=avatar, bg=th["card"],
                                   font=("Segoe UI Emoji", 14))
        self.lbl_avatar.pack(side="left", padx=(9, 6), pady=(7, 7))

        col = tk.Frame(self.head, bg=th["card"])
        col.pack(side="left", fill="x", expand=True)
        self.lbl_name = tk.Label(col, text=NAME_CN.get(name, name), bg=th["card"],
                                 fg=th["text"], font=("Microsoft YaHei UI", 10, "bold"),
                                 anchor="w")
        self.lbl_name.pack(fill="x", anchor="w")
        self.lbl_status = tk.Label(col, text="待刷新", bg=th["card"], fg=th["dim"],
                                   font=("Microsoft YaHei UI", 8), anchor="w",
                                   justify="left", wraplength=140)
        self.lbl_status.pack(fill="x", anchor="w")

        right = tk.Frame(self.head, bg=th["card"])
        right.pack(side="right", padx=(4, 10))
        self.lbl_value = tk.Label(right, text="—", bg=th["card"], fg=th["value"],
                                  font=("Microsoft YaHei UI", 14, "bold"), anchor="e")
        self.lbl_value.pack(anchor="e")
        self.spark = tk.Canvas(right, width=68, height=16, bg=th["card"],
                               highlightthickness=0)
        self.spark.pack(anchor="e", pady=(0, 2))

        self.lbl_detail = tk.Label(self.frame, text="", bg=th["detail"], fg=th["dim"],
                                   font=("Microsoft YaHei UI", 8), anchor="w",
                                   justify="left", wraplength=240)

        for w in (self.frame, self.head, self.lbl_avatar, self.lbl_name,
                  self.lbl_status, self.lbl_value, self.spark, col, right):
            w.bind("<Button-1>", lambda e: app.toggle(self))
            w.bind("<Enter>", lambda e: app.row_hover(self, True))
            w.bind("<Leave>", lambda e: app.row_hover(self, False))

    # ---- 状态更新 ----
    def set_pending(self):
        self.lbl_status.config(text="查询中…", fg=self.th["warn"])
        self.lbl_value.config(fg=self.th["dim"])

    def set_skipped(self):
        self.lbl_status.config(text="未配置 key · 点 ⚙ 填", fg=self.th["dim"])
        self.lbl_value.config(text="—", fg=self.th["dim"])
        self._draw_spark()

    def set_error(self, msg):
        self.lines = [msg]
        self.lbl_status.config(text=msg[:60], fg=self.th["err"])
        self.lbl_value.config(text="!", fg=self.th["err"])
        self.show_detail(False)

    def set_ok(self, sub, lines, value, unit):
        self.lines = lines or []
        self.value, self.unit = value, unit
        self.lbl_status.config(text=(sub or (lines[0] if lines else ""))[:64],
                               fg=self.th["dim"])
        fg = self.th["value"]
        if value is not None:
            if value < WARN_BELOW / 4:
                fg = self.th["err"]
            elif value < WARN_BELOW:
                fg = self.th["warn"]
        self.lbl_value.config(text=fmt_value(value, unit), fg=fg)
        self._draw_spark()

    def show_detail(self, show):
        self.expanded = show
        if show and self.lines:
            self.lbl_detail.config(text="\n".join(self.lines))
            self.lbl_detail.pack(fill="x", padx=9, pady=(0, 7))
        else:
            self.lbl_detail.pack_forget()

    # ---- sparkline ----
    def _draw_spark(self):
        c = self.spark
        c.delete("all")
        pts = [p["v"] for p in load_history().get(self.name, [])
               if isinstance(p.get("v"), (int, float))]
        if len(pts) < 2:
            return
        w, h, pad = 68, 16, 2
        lo, hi = min(pts), max(pts)
        span = (hi - lo) or 1.0
        n = len(pts)
        xy = []
        for i, v in enumerate(pts):
            x = pad + (w - 2 * pad) * i / (n - 1)
            y = h - pad - (h - 2 * pad) * (v - lo) / span
            xy += [x, y]
        color = self.th["chart"] if pts[-1] >= pts[0] else self.th["warn"]
        c.create_line(*xy, fill=color, width=1, smooth=True)
        c.create_oval(xy[-2] - 1.5, xy[-1] - 1.5, xy[-2] + 1.5, xy[-1] + 1.5,
                      fill=color, outline="")


class Widget(tk.Tk):
    def __init__(self, cfg, path):
        super().__init__()
        self.cfg = cfg
        self.cfg_path = path
        self.ui = _load_ui()
        self.theme_name = self.ui.get("theme", "dark")
        self.rows = {}
        self.last_results = {}
        self.refreshing = False
        self.auto = self.ui.get("auto", True)
        self._drag = None
        self._spin_angle = 0

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.96)
        self._build_ui()

        self.after(400, self.refresh)
        if self.auto:
            self.after(AUTO_REFRESH_MS, self._auto_tick)

    @property
    def th(self):
        return THEMES[self.theme_name]

    # ---------- UI 构建（主题切换时整窗重建） ----------
    def _build_ui(self):
        th = self.th
        for w in self.winfo_children():
            w.destroy()
        self.rows = {}
        self.configure(bg=th["bg"])

        # 标题栏
        bar = tk.Frame(self, bg=th["bar"], highlightthickness=1,
                       highlightbackground=th["line"])
        bar.pack(fill="x")
        self._bind_drag(bar)
        self.mascot = MascotLabel(bar, th["bar"])
        self.mascot.pack(side="left", padx=(7, 3), pady=2)
        self.mascot.bind("<Button-1>", lambda e: self._mascot_click())
        tk.Label(bar, text="Token 额度", bg=th["bar"], fg=th["text"],
                 font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=(0, 9), pady=5)
        btns = tk.Frame(bar, bg=th["bar"])
        btns.pack(side="right", padx=2)
        self._bind_drag(btns)

        self.spin = tk.Canvas(btns, width=18, height=18, bg=th["bar"],
                              highlightthickness=0, cursor="hand2")
        self.spin.pack(side="left", padx=3)
        self.spin.bind("<Button-1>", lambda e: self.refresh())
        self._draw_spinner()

        for txt, cmd, fg in (("⚙", self.open_settings, th["dim"]),
                             ("—", self.dim_temporarily, th["dim"]),
                             ("✕", self.destroy, th["err"])):
            b = tk.Label(btns, text=txt, bg=th["bar"], fg=fg,
                         font=("Microsoft YaHei UI", 10), cursor="hand2", width=2)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            self._bind_drag(b)

        # 行容器
        self.body = tk.Frame(self, bg=th["bg"])
        self.body.pack(fill="both", expand=True, padx=1, pady=1)
        self._build_rows()

        # 底栏
        foot = tk.Frame(self, bg=th["bg"])
        foot.pack(fill="x")
        self.lbl_foot = tk.Label(foot, text="未刷新", bg=th["bg"], fg=th["dim"],
                                 font=("Microsoft YaHei UI", 8))
        self.lbl_foot.pack(side="left", padx=9, pady=3)
        tk.Label(foot, text="右键菜单", bg=th["bg"], fg=th["dim"],
                 font=("Microsoft YaHei UI", 8)).pack(side="right", padx=9)

        # 右键菜单
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="↻ 立即刷新", command=self.refresh)
        self.menu.add_command(label=f"⏱ 自动刷新(10min)：{'开' if self.auto else '关'}",
                              command=self._toggle_auto)
        self.menu.add_command(label="📌 置顶开关", command=self._toggle_top)
        self.menu.add_command(label="🎨 切换主题(深/浅)", command=self._toggle_theme)
        self.menu.add_command(label="▦ 恢复任务栏显示", command=self._restore_taskbar)
        self.menu.add_separator()
        self.menu.add_command(label="✕ 退出", command=self.destroy)
        self.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

        self.update_idletasks()
        if not getattr(self, "_placed", False):
            x = self.winfo_screenwidth() - self.winfo_reqwidth() - 24
            y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
            self.geometry(f"+{x}+{y}")
            self._placed = True
        self._update_mascot()

    # ---- 猫咪情绪：刷新=敲键盘，余额低=担忧，告急/出错=惊恐，健康=开心/idle ----
    def _mood(self):
        if self.refreshing:
            return "tap"
        if time.time() < getattr(self, "_happy_until", 0):
            return "happy"
        results = list(self.last_results.values())
        if any(r.get("status") == "error" for r in results):
            return "panic"
        vals = [r.get("value") for r in results
                if isinstance(r.get("value"), (int, float))]
        if vals and min(vals) < WARN_BELOW / 4:
            return "panic"
        if vals and min(vals) < WARN_BELOW:
            return "worried"
        if results and all(r.get("status") in ("ok", "skipped") for r in results):
            return "idle"
        return "idle"

    def _update_mascot(self):
        m = getattr(self, "mascot", None)
        if m:
            m.set_state(self._mood())

    def _mascot_click(self):
        """摸猫：开心 3 秒并立即刷新一次。"""
        self._happy_until = time.time() + 3
        self._update_mascot()
        self.refresh()

    def _build_rows(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.rows = {}
        for name in quota.BUILTIN:
            self._add_row(name)
        for item in self.cfg.get("custom", []):
            self._add_row(item.get("name", "custom"), "✨")
        # 已有结果直接回填（主题切换不丢数据）
        for name, res in self.last_results.items():
            self._apply_one(name, res)

    def _add_row(self, name, avatar=None):
        row = Row(self, name, avatar or AVATARS.get(name, "✨"), self.th)
        row.frame.pack(fill="x", padx=4, pady=(4, 0))
        self.rows[name] = row
        pts = load_history().get(name)
        if pts:
            row._draw_spark()

    # ---- 转圈动画 ----
    def _draw_spinner(self):
        c = self.spin
        c.delete("all")
        th = self.th
        c.create_oval(3, 3, 15, 15, outline=th["line"], width=2)
        if self.refreshing:
            c.create_arc(3, 3, 15, 15, start=self._spin_angle, extent=100,
                         style="arc", outline=th["accent"], width=2)
        else:
            c.create_line(5, 12, 8, 6, 11, 12, 14, 4, fill=th["accent"], width=1.5,
                          smooth=True)

    def _spin_tick(self):
        if not self.refreshing:
            self._draw_spinner()
            return
        self._spin_angle = (self._spin_angle - 30) % 360
        self._draw_spinner()
        self.after(80, self._spin_tick)

    def row_hover(self, row, on):
        bg = self.th["hover"] if on else self.th["card"]
        for w in (row.frame, row.head, row.lbl_avatar, row.lbl_name,
                  row.lbl_status, row.lbl_value, row.spark,
                  *row.head.winfo_children()):
            try:
                w.config(bg=bg)
            except tk.TclError:
                pass

    def toggle(self, row):
        if not row.lines:
            return
        row.show_detail(not row.expanded)

    # ---- 拖动 / 菜单动作 ----
    def _bind_drag(self, w):
        w.bind("<Button-1>", self._drag_start, add="+")
        w.bind("<B1-Motion>", self._drag_move, add="+")

    def _drag_start(self, e):
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e):
        if self._drag:
            self.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def dim_temporarily(self):
        self.attributes("-alpha", 0.35)
        self.after(3000, lambda: self.attributes("-alpha", 0.96))

    def _restore_taskbar(self):
        self.overrideredirect(False)
        self.update_idletasks()

    def _toggle_top(self):
        self._pinned = not getattr(self, "_pinned", True)
        self.attributes("-topmost", self._pinned)

    def _toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.ui["theme"] = self.theme_name
        _save_ui(self.ui)
        self.overrideredirect(True)
        self._build_ui()

    def _toggle_auto(self):
        self.auto = not self.auto
        self.ui["auto"] = self.auto
        _save_ui(self.ui)
        if self.auto:
            self.after(AUTO_REFRESH_MS, self._auto_tick)
        self.menu.entryconfigure(1, label=f"⏱ 自动刷新(10min)：{'开' if self.auto else '关'}")

    def _auto_tick(self):
        if self.auto:
            self.refresh()
            self.after(AUTO_REFRESH_MS, self._auto_tick)

    # ---- 查询 ----
    def refresh(self):
        if self.refreshing:
            return
        self.refreshing = True
        self._spin_tick()
        self._update_mascot()
        tasks = quota.collect(self.cfg, None)
        for name, _ in tasks:
            r = self.rows.get(name)
            if r:
                r.set_pending()
        threading.Thread(target=self._worker, args=(tasks,), daemon=True).start()

    def _worker(self, tasks):
        results = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(fn): name for name, fn in tasks if fn}
            for name, fn in tasks:
                if fn is None:
                    results[name] = {"status": "skipped"}
            for fut in futs:
                name = futs[fut]
                try:
                    res = fut.result() or {}
                    results[name] = {"status": "ok", "lines": res.get("lines", []),
                                     "value": res.get("value"),
                                     "unit": res.get("unit", ""),
                                     "sub": res.get("sub")}
                except Exception as e:
                    results[name] = {"status": "error", "msg": str(e)[:120]}
        self.after(0, self._apply, results)

    def _apply(self, results):
        for name, res in results.items():
            self.last_results[name] = res
            self._apply_one(name, res)
        self.lbl_foot.config(text=f"更新于 {time.strftime('%H:%M:%S')}")
        self.refreshing = False
        self._draw_spinner()
        if results and all(r.get("status") == "ok" for r in results.values()) \
                and any(r.get("value") is not None for r in results.values()):
            self._happy_until = time.time() + 4  # 查得顺利，猫开心一会儿
        self._update_mascot()

    def _apply_one(self, name, res):
        row = self.rows.get(name)
        if not row:
            return
        st = res.get("status")
        if st == "skipped":
            row.set_skipped()
        elif st == "error":
            row.set_error(res.get("msg", "查询失败"))
        elif st == "ok":
            if res.get("value") is not None:
                record_history(name, res["value"])
            row.set_ok(res.get("sub"), res.get("lines"), res.get("value"),
                       res.get("unit", ""))

    def open_settings(self):
        SettingsDialog(self)

    def apply_config(self, cfg, path):
        """配置窗口保存后回调：更新配置、重建行、立即刷新。"""
        self.cfg = cfg
        self.cfg_path = path
        self.last_results = {}
        self._build_rows()
        self.refresh()


class SettingsDialog(tk.Toplevel):
    """可视化编辑 quotas.json：key + 自定义提供商，保存即生效（跟随挂件主题）。"""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.th = app.th
        self.BG, self.FG, self.FG_DIM = self.th["bg"], self.th["text"], self.th["dim"]
        self.cfg = json.loads(json.dumps(app.cfg))
        self.key_entries = []
        self.custom_rows = []
        self._show_key = False

        self.title("额度挂件 · 配置")
        self.attributes("-topmost", True)
        self.configure(bg=self.BG, padx=14, pady=10)
        self.resizable(False, False)
        self.bind("<Escape>", lambda e: self.destroy())

        self.canvas = tk.Canvas(self, bg=self.BG, highlightthickness=0, width=470)
        vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=self.BG)
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.bind("<MouseWheel>",
                  lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vsb.set)

        tk.Label(self.inner, text="API 密钥", bg=self.BG, fg=self.FG,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        tk.Label(self.inner, text="留空则回退读环境变量；保存后自动刷新",
                 bg=self.BG, fg=self.FG_DIM,
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(0, 4))

        for name in quota.BUILTIN:
            self._key_row(name)

        head = tk.Frame(self.inner, bg=self.BG)
        head.pack(fill="x", pady=(10, 2))
        tk.Label(head, text="自定义提供商", bg=self.BG, fg=self.FG,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        tk.Button(head, text="＋ 添加", command=self._add_custom, relief="flat",
                  fg=self.th["accent"], bg=self.BG, font=("Microsoft YaHei UI", 9),
                  cursor="hand2").pack(side="right")
        tk.Label(self.inner, text="任何返回 JSON 的余额接口均可接入；headers/更多字段请直接编辑 quotas.json",
                 bg=self.BG, fg=self.FG_DIM, font=("Microsoft YaHei UI", 8)).pack(anchor="w")
        self.custom_box = tk.Frame(self.inner, bg=self.th["detail"])
        self.custom_box.pack(fill="x", pady=4)
        for item in self.cfg.get("custom", []):
            self._custom_row(item)

        foot = tk.Frame(self, bg=self.BG)
        foot.pack(fill="x", pady=(12, 0))
        self.chk_show = tk.Checkbutton(foot, text="显示密钥", command=self._toggle_show,
                                       bg=self.BG, fg=self.FG, selectcolor=self.th["card"],
                                       activebackground=self.BG, activeforeground=self.FG,
                                       font=("Microsoft YaHei UI", 9))
        self.chk_show.pack(side="left")
        tk.Button(foot, text="保存并应用", command=self._save, bg=self.th["accent"],
                  fg="white", relief="flat", padx=14, pady=3, cursor="hand2",
                  font=("Microsoft YaHei UI", 9, "bold")).pack(side="right")
        tk.Button(foot, text="取消", command=self.destroy, bg=self.th["bar"], fg=self.FG,
                  relief="flat", padx=14, pady=3, cursor="hand2",
                  font=("Microsoft YaHei UI", 9)).pack(side="right", padx=6)

        self.update_idletasks()
        h = min(self.inner.winfo_reqheight() + 8, self.winfo_screenheight() - 180)
        self.canvas.config(height=h)
        x = self.app.winfo_x() - self.winfo_reqwidth() - 12
        if x < 0:
            x = self.app.winfo_x() + self.app.winfo_width() + 12
        y = min(self.app.winfo_y(), self.winfo_screenheight() - self.winfo_reqheight() - 40)
        self.geometry(f"+{x}+{max(y, 0)}")

    def _entry(self, parent, var, masked=False, width=None):
        return tk.Entry(parent, textvariable=var, show="*" if masked else "",
                        font=("Consolas", 9), relief="flat", bd=1, width=width,
                        bg=self.th["field"], fg=self.FG, insertbackground=self.FG,
                        highlightthickness=1, highlightbackground=self.th["line"],
                        highlightcolor=self.th["accent"])

    def _key_row(self, name):
        row = tk.Frame(self.inner, bg=self.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=AVATARS.get(name, "✨"), bg=self.BG,
                 font=("Segoe UI Emoji", 11), width=2).pack(side="left")
        tk.Label(row, text=NAME_CN.get(name, name), bg=self.BG, fg=self.FG,
                 font=("Microsoft YaHei UI", 9), width=10, anchor="w").pack(side="left")
        var = tk.StringVar(value=self.cfg.get(name, ""))
        ent = self._entry(row, var, masked=True)
        ent.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self.key_entries.append((name, ent))
        env = quota.ENV_FALLBACK.get(name, "")
        env_on = bool(os.environ.get(env))
        tk.Label(row, text="env✓" if env_on and not var.get() else "",
                 bg=self.BG, fg=self.th["ok"],
                 font=("Microsoft YaHei UI", 8)).pack(side="left")
        var.trace_add("write", lambda *_: self._remember(name, var))

    def _remember(self, name, var):
        self.cfg[name] = var.get().strip()

    # ---------- 自定义提供商 ----------
    def _add_custom(self):
        item = {"name": "", "url": "", "headers": {"Authorization": "Bearer {key}"}, "path": ""}
        self._custom_row(item)

    def _custom_row(self, item):
        box = tk.Frame(self.custom_box, bg=self.th["detail"], bd=1, relief="solid",
                       highlightbackground=self.th["line"])
        box.pack(fill="x", padx=6, pady=4)
        r1 = tk.Frame(box, bg=self.th["detail"]); r1.pack(fill="x", padx=4, pady=(3, 0))
        r2 = tk.Frame(box, bg=self.th["detail"]); r2.pack(fill="x", padx=4, pady=(2, 4))
        widgets = {"item": item, "box": box}
        for parent, field, label, width in (
                (r1, "name", "名称", 12), (r1, "url", "查询 URL", 42),
                (r2, "key", "key", 22), (r2, "path", "JSON 取值路径(点号)", 32)):
            tk.Label(parent, text=label, bg=self.th["detail"], fg=self.FG_DIM,
                     font=("Microsoft YaHei UI", 8)).pack(side="left")
            var = tk.StringVar(value=item.get(field, ""))
            ent = self._entry(parent, var, masked=(field == "key"), width=width)
            ent.pack(side="left", fill="x", expand=True, padx=(2, 6))
            var.trace_add("write", lambda *_s, v=var, f=field: self._custom_set(widgets, f, v))
            widgets[field] = ent
        tk.Button(r1, text="✕", command=lambda: self._remove_custom(widgets),
                  bg=self.th["detail"], fg=self.th["err"], relief="flat", cursor="hand2",
                  font=("Microsoft YaHei UI", 9)).pack(side="right")
        self.custom_rows.append(widgets)

    def _custom_set(self, widgets, field, var):
        widgets["item"][field] = var.get().strip()

    def _remove_custom(self, widgets):
        widgets["box"].destroy()
        self.custom_rows.remove(widgets)

    # ---------- 保存 / 显示切换 ----------
    def _toggle_show(self):
        self._show_key = bool(self.chk_show.select())
        show = "" if self._show_key else "*"
        for _, ent in self.key_entries:
            ent.config(show=show)
        for w in self.custom_rows:
            w["key"].config(show=show)

    def _save(self):
        customs = []
        for w in self.custom_rows:
            item = w["item"]
            if not item.get("name") or not item.get("url"):
                continue  # 空行忽略
            if not re.match(r"^https?://", item["url"]):
                tk.messagebox.showwarning("配置有误", f"[{item['name']}] URL 需以 http(s):// 开头",
                                          parent=self)
                return
            entry = {"name": item["name"], "url": item["url"],
                     "headers": item.get("headers") or {"Authorization": "Bearer {key}"},
                     "path": item.get("path") or ""}
            if item.get("key"):
                entry["key"] = item["key"]
            customs.append(entry)
        self.cfg["custom"] = customs
        path = self.app.cfg_path or os.path.join(_dir(), "data", quota.CONFIG_NAME)
        try:
            quota.save_config(self.cfg, path)  # DPAPI 加密后落盘
        except OSError as e:
            tk.messagebox.showerror("保存失败", str(e), parent=self)
            return
        self.app.apply_config(self.cfg, path)
        self.destroy()


def main():
    cfg, path = quota.load_config()
    if cfg is None:
        print("未找到 quotas.json，请先运行: python quota.py --init")
        return
    Widget(cfg, path).mainloop()


if __name__ == "__main__":
    main()