#!/usr/bin/env python3
"""quota_pet.py — DeepSeek 鲸鱼娘桌宠 · 帮你盯余额（tkinter，零依赖）

素材：鲸鱼娘·大肥鱼 三视图（来自 1190fasheqi/dafeiyu-pet，MIT License，二创形象）
功能：
  · 透明置顶桌宠，发呆呼吸、左右散步（侧视图自动镜像）、拖拽移动
  · 点一下摸头 → 弹出余额气泡（样式参考 MeteorNOX/DeepSeek-Balance-Whale-Widget）
  · 余额低于阈值时气泡告警 + 抖动提醒
  · 右键菜单：刷新余额 / 自动刷新 / 尺寸 / 置顶 / 退出
复用 quota.py 的查询与 DPAPI 加密配置。
"""

import json
import os
import random
import sys
import threading
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quota    # 查询与配置（含 DPAPI 加密）
import pngtool  # 纯标准库 PNG 编解码（键位点亮图）

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "pet_assets")
KEY = "#ff00fe"          # 色键（窗口里这个颜色即透明）
SELF_CONTAINED = True    # front.png 已自带键盘和手，不再叠加分层
MANIFEST_FILE = os.path.join(ASSETS, "manifest.json")
ASSET_DEFAULTS = {
    "front": ["front.png"],
    "front_typing": ["front_typing.png"],
    "side_l": ["side_l.png", "side_l_1.png", "side_l_2.png", "side_l_3.png"],
    "side_r": ["side_r.png", "side_r_1.png", "side_r_2.png", "side_r_3.png"],
    "run_l": ["run_l.png", "run_l_1.png", "run_l_2.png", "run_l_3.png"],
    "run_r": ["run_r.png", "run_r_1.png", "run_r_2.png", "run_r_3.png"],
    "ride_l": ["ride_l.png", "ride_l_1.png", "ride_l_2.png", "ride_l_3.png"],
    "ride_r": ["ride_r.png", "ride_r_1.png", "ride_r_2.png", "ride_r_3.png"],
    "duo_l": ["duo_l.png", "duo_l_1.png", "duo_l_2.png", "duo_l_3.png"],
    "duo_r": ["duo_r.png", "duo_r_1.png", "duo_r_2.png", "duo_r_3.png"],
    "back": ["back.png"],
    "blink": ["blink_1.png", "blink_2.png"],
    "sleep": ["sleep_1.png", "sleep_2.png"],
}
SINGLE_ASSET_ROLES = {"front", "front_typing", "back"}
MOVE_STYLE_ROLES = {
    "walk": ("side_l", "side_r"),
    "run": ("run_l", "run_r"),
    "ride": ("ride_l", "ride_r"),
    "duo": ("duo_l", "duo_r"),
}
MOVE_ANIMATION_ROLES = {role for roles in MOVE_STYLE_ROLES.values() for role in roles}
OPTIONAL_MOVE_ROLES = MOVE_ANIMATION_ROLES - {"side_l", "side_r"}
MOVE_STEP_PIXELS = {"walk": 3, "run": 6, "ride": 3, "duo": 4}
MOVE_FRAME_HOLD_TICKS = {"walk": 3, "run": 2, "ride": 3, "duo": 2}
MOVE_TICK_MS = 40
GIF_DEBUG_BACKGROUND = (238, 238, 242)
WARN_BELOW = 10.0        # 余额告警阈值
AUTO_MS = 10 * 60 * 1000
BUBBLE_MS = 8000
IDLE_SPAWN_MS = 90 * 1000     # 挂机多久触发自动增殖
SLEEP_AFTER_MS = 90 * 1000    # 有 sleep 素材时，挂机多久进入睡眠
BLINK_FRAME_MS = 120
SLEEP_FRAME_MS = 700
AUTO_SPAWN_DEFAULT = False    # 自动增殖默认关闭（调试时不会被刷屏）
MAX_PETS = 8                  # 增殖上限，避免刷爆屏幕
TYPING_HOLD = 0.22            # 敲键后保持抬指姿势的时长
TYPING_LOCK = 2.5             # 最后一次敲键后多久内锁住行为（不散步、不换姿势）
KEY_POLL_MS = 40              # 轻量轮询，减少快速按键漏采样
KEY_GLOW_HOLD = 0.16          # 松键后保留极短高亮，保证肉眼可见
# front.png 内嵌键盘键帽在 215x215 舞台中的实际区域；坐标系沿用 keys_map.json。
# 只覆盖键帽区，不把下方键盘外壳当成可点亮区域。
EMBEDDED_KEYBOARD_BBOX = (68, 155, 80, 18)
KEYBOARD_MAP_SIZE = (150.0, 58.0)
KEY_GLOW_RGB = (86, 232, 255)
INITIAL_MARGIN = 20           # 首次出生点距主屏工作区右下角的安全边距

# Shared foot baseline pad (walk target canvas 215x264, feet at y=261).
# Layout-only alignment: do not resize/patch pet_assets pixels.
FOOT_PAD_PX = 3
CONTENT_ALPHA_MIN = 16


def _get_primary_work_area(widget):
    """返回 Windows 主显示器工作区；失败时回退到 Tk 主屏尺寸。"""
    fallback = (0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())
    if sys.platform != "win32":
        return fallback
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        spi = ctypes.windll.user32.SystemParametersInfoW
        spi.argtypes = [wintypes.UINT, wintypes.UINT,
                        ctypes.POINTER(wintypes.RECT), wintypes.UINT]
        spi.restype = wintypes.BOOL
        if spi(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return (int(rect.left), int(rect.top),
                    int(rect.right), int(rect.bottom))
    except Exception:
        pass
    return fallback


def _initial_position(work_area, width, height, margin=INITIAL_MARGIN):
    """把首次窗口原点放在工作区右下角，并夹回工作区范围。"""
    left, top, right, bottom = (int(v) for v in work_area)
    width, height = max(0, int(width)), max(0, int(height))
    margin = max(0, int(margin))
    max_x = max(left, right - width)
    max_y = max(top, bottom - height)
    x = min(max(left, right - width - margin), max_x)
    y = min(max(top, bottom - height - margin), max_y)
    return x, y


def _draw_embedded_key_glow(rgba, width, height, image_origin_x,
                            bbox, key_rects, pressed_vks):
    """在完整正面图的内嵌键盘区域画小范围不透明高亮。"""
    if not pressed_vks:
        return rgba
    bx, by, bw, bh = bbox
    map_w, map_h = KEYBOARD_MAP_SIZE
    out = bytearray(rgba)
    for key in key_rects:
        if key.get("vk") not in pressed_vks:
            continue
        x0, y0, x1, y1 = key.get("rect", (0, 0, 0, 0))
        left = max(0, int(round(image_origin_x + bx + x0 / map_w * bw)))
        top = max(0, int(round(by + y0 / map_h * bh)))
        right = min(width, int(round(image_origin_x + bx + x1 / map_w * bw)))
        bottom = min(height, int(round(by + y1 / map_h * bh)))
        if right <= left:
            right = min(width, left + 1)
        if bottom <= top:
            bottom = min(height, top + 1)
        for y in range(top, bottom):
            for x in range(left, right):
                i = (y * width + x) * 4
                out[i:i + 4] = bytes((*KEY_GLOW_RGB, 255))
    return out


def _get_monitor_work_areas(widget):
    """返回所有真实显示器工作区；Win32 查询失败时退回主屏工作区。"""
    fallback = [_get_primary_work_area(widget)]
    if sys.platform != "win32":
        return fallback
    try:
        import ctypes
        from ctypes import wintypes

        class _MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]

        user32 = ctypes.windll.user32
        get_monitor_info = user32.GetMonitorInfoW
        get_monitor_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MonitorInfo)]
        get_monitor_info.restype = wintypes.BOOL

        areas = []

        def on_monitor(hmonitor, _hdc, _clip, _data):
            info = _MonitorInfo()
            info.cbSize = ctypes.sizeof(_MonitorInfo)
            if get_monitor_info(hmonitor, ctypes.byref(info)):
                rect = info.rcWork
                area = (int(rect.left), int(rect.top),
                        int(rect.right), int(rect.bottom))
                if area[2] > area[0] and area[3] > area[1]:
                    areas.append(area)
            return True

        enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(wintypes.RECT), ctypes.c_void_p
        )(on_monitor)
        enum_monitors = user32.EnumDisplayMonitors
        enum_monitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.c_void_p]
        enum_monitors.restype = wintypes.BOOL
        if enum_monitors(None, None, enum_proc, None) and areas:
            return areas
    except Exception:
        pass
    return fallback


def _rect_contains(outer, inner):
    """判断 inner 是否完整包含在 outer 内。"""
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def _clamp_window_to_rect(x, y, width, height, rect):
    """把窗口原点夹回矩形；正常屏幕尺寸下结果保证窗口完整可见。"""
    left, top, right, bottom = rect
    max_x = max(left, right - width)
    max_y = max(top, bottom - height)
    return min(max(int(x), left), max_x), min(max(int(y), top), max_y)


def _monitor_for_window(monitors, x, y, width, height):
    """优先找完整容纳窗口的显示器，否则返回重叠最多的显示器。"""
    window = (x, y, x + width, y + height)
    for monitor in monitors:
        if _rect_contains(monitor, window):
            return monitor

    def score(monitor):
        overlap_w = max(0, min(window[2], monitor[2]) - max(window[0], monitor[0]))
        overlap_h = max(0, min(window[3], monitor[3]) - max(window[1], monitor[1]))
        overlap = overlap_w * overlap_h
        center_distance = abs((window[0] + window[2]) - (monitor[0] + monitor[2]))
        return overlap, -center_distance

    return max(monitors, key=score, default=None)


def _adjacent_monitor(monitors, current, direction, y, height):
    """找同一水平行上、方向相邻的显示器，允许显示器之间存在 gap。"""
    if current is None:
        return None
    vertical_overlap = lambda monitor: monitor[3] > y and monitor[1] < y + height
    candidates = []
    for monitor in monitors:
        if monitor == current or not vertical_overlap(monitor):
            continue
        if direction > 0 and monitor[2] > current[2]:
            gap = max(0, monitor[0] - current[2])
            candidates.append((gap, abs(monitor[1] - y), monitor))
        elif direction < 0 and monitor[0] < current[0]:
            gap = max(0, current[0] - monitor[2])
            candidates.append((gap, abs(monitor[1] - y), monitor))
    return min(candidates, key=lambda item: (item[0], item[1]))[2] if candidates else None


def _next_walk_position(monitors, x, y, width, height, direction, step=3):
    """计算一次自动散步，跨屏时从当前边缘跳到相邻屏幕边缘。"""
    if not monitors:
        return x, y, direction, None
    current = _monitor_for_window(monitors, x, y, width, height)
    if current is None:
        return x, y, direction, None
    x, y = _clamp_window_to_rect(x, y, width, height, current)
    candidate = (x + direction * step, y,
                 x + direction * step + width, y + height)
    if _rect_contains(current, candidate):
        return candidate[0], candidate[1], direction, current

    target = _adjacent_monitor(monitors, current, direction, y, height)
    if target is not None:
        if direction > 0:
            target_x = max(current[2], target[0])
        else:
            target_x = min(current[0] - width, target[2] - width)
        target_x, target_y = _clamp_window_to_rect(
            target_x, y, width, height, target
        )
        return target_x, target_y, direction, target

    edge_x = current[2] - width if direction > 0 else current[0]
    edge_x, edge_y = _clamp_window_to_rect(edge_x, y, width, height, current)
    return edge_x, edge_y, -direction, current

# 只轮询可打印键与常用编辑键，避开控制/鼠标/手柄键
def _watch_vks():
    vks = list(range(0x30, 0x5B))          # 0-9, A-Z
    vks += list(range(0x60, 0x6A))         # 小键盘 0-9
    vks += [0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE,
            0x08, 0x0D, 0x1B, 0x09, 0x20]  # 符号键 + 退格/回车/Esc/Tab/空格
    return tuple(vks)


_WATCH_VKS = _watch_vks()


def key_state():
    """读取按键状态：返回 frozenset(按下的虚拟键码)。非 Windows 返回 None。

    用 GetAsyncKeyState 轮询（GetKeyboardState 需要 256 字节缓冲，易越界）。
    """
    try:
        import ctypes
        u = ctypes.windll.user32
        held = set()
        for vk in _WATCH_VKS:
            if u.GetAsyncKeyState(vk) & 0x8000:
                held.add(vk)
        return frozenset(held)
    except Exception:
        return None


UI_FILE = os.path.join(HERE, "data", "ui.json")


def _load_ui():
    """读取界面偏好（主题、自动增殖等）。文件不存在或损坏时返回空 dict。"""
    try:
        with open(UI_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_asset_manifest():
    """读取可选素材 manifest；缺失或损坏时回退到默认文件名。"""
    try:
        with open(MANIFEST_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _manifest_files(manifest, role):
    """返回一个动作的文件名列表，保持旧版固定命名兼容。"""
    value = manifest.get(role, ASSET_DEFAULTS[role])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = ASSET_DEFAULTS[role]
    files = [v.strip() for v in value if isinstance(v, str) and v.strip()]
    if role in SINGLE_ASSET_ROLES:
        files = files[:1]
    return files


def _normalize_move_style(value):
    """Return a supported movement style; unknown or malformed values use walk."""
    return value if isinstance(value, str) and value in MOVE_STYLE_ROLES else "walk"


def _export_animation_gif(style, direction, frame_keys, asset_paths,
                          duration_ms, output_dir=None):
    """Export the existing runtime PNG sequence over a neutral debug background."""
    from PIL import Image

    if style not in MOVE_STYLE_ROLES or direction not in ("left", "right"):
        raise ValueError("unsupported animation selection")
    if not frame_keys:
        raise ValueError("animation has no runtime frames")

    output_dir = output_dir or os.path.join(HERE, "debug_capture")
    os.makedirs(output_dir, exist_ok=True)
    frames = []
    expected_size = None
    for key in frame_keys:
        path = asset_paths.get(key)
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(path or key)
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
        image = Image.new("RGB", rgba.size, GIF_DEBUG_BACKGROUND)
        source_pixels = rgba.getdata()
        output_pixels = []
        for red, green, blue, alpha in source_pixels:
            if (alpha < 128 or (red, green, blue) == (255, 0, 254)):
                output_pixels.append(GIF_DEBUG_BACKGROUND)
            elif alpha == 255:
                output_pixels.append((red, green, blue))
            else:
                output_pixels.append(tuple(
                    (channel * alpha + background * (255 - alpha) + 127) // 255
                    for channel, background in zip(
                        (red, green, blue), GIF_DEBUG_BACKGROUND)
                ))
        image.putdata(output_pixels)
        if expected_size is None:
            expected_size = image.size
        elif image.size != expected_size:
            raise ValueError("runtime animation frames have inconsistent dimensions")
        pixels = list(image.getdata())
        image.putdata([
            GIF_DEBUG_BACKGROUND if pixel == (255, 0, 254) else pixel
            for pixel in pixels
        ])
        frames.append(image)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    stem = f"{style}_{direction}_{timestamp}"
    path = os.path.join(output_dir, stem + ".gif")
    suffix = 1
    while os.path.exists(path):
        path = os.path.join(output_dir, f"{stem}_{suffix}.gif")
        suffix += 1
    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=int(duration_ms),
        loop=0,
        disposal=2,
        optimize=False,
    )
    return path



def _opaque_content_bbox(rgba, width, height, alpha_min=CONTENT_ALPHA_MIN,
                         colorkey=(255, 0, 254)):
    """Inclusive bbox of visible pixels (non-transparent, non-colorkey)."""
    minx, miny, maxx, maxy = width, height, -1, -1
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            i = row + x * 4
            red, green, blue, alpha = rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]
            if alpha < alpha_min:
                continue
            if (red, green, blue) == colorkey:
                continue
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y
    if maxx < 0:
        return 0, 0, max(0, width - 1), max(0, height - 1)
    return minx, miny, maxx, maxy


def _frame_anchor_from_png(path):
    """Native-pixel foot y (content bottom) and horizontal content center."""
    with open(path, "rb") as f:
        width, height, rgba = pngtool.decode(f.read())
    left, _top, right, bottom = _opaque_content_bbox(rgba, width, height)
    return {
        "foot_y": bottom,
        "center_x": (left + right) / 2.0,
        "left": left,
        "right": right,
        "width": width,
        "height": height,
    }


def _asset_key(role, index):
    """把 manifest 中的动作帧映射到兼容现有代码的素材 key。"""
    if role in SINGLE_ASSET_ROLES:
        return role
    if role in MOVE_ANIMATION_ROLES:
        return role if index == 0 else f"{role}_{index}"
    return f"{role}_{index + 1}"


def _save_ui(ui):
    try:
        with open(UI_FILE, "w", encoding="utf-8") as f:
            json.dump(ui, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _win_alive(widget):
    """窗口是否仍存在；已销毁时 winfo_exists() 本身会抛 TclError，需一并捕获。"""
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


USAGE_FILE = os.path.join(HERE, "data", "usage.json")


def _load_usage():
    """本地消耗记账。结构：{date: {"spent": float, "samples": int}}"""
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_usage(u):
    try:
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(u, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def record_spend(old_value, new_value, when=None):
    """记录一次余额变化算出的消耗。只在余额下降时记（充值不算消耗）。

    返回 (今日消耗, 本次消耗)。仅统计桌宠运行期间的消耗——关掉桌宠期间的
    用量会被合并进下一次刷新，所以是近似值。
    """
    if old_value is None or new_value is None:
        return None, 0.0
    delta = float(old_value) - float(new_value)
    if delta <= 0.0001:                      # 没变或余额增加（充值）→ 不算消耗
        return _today_spent(when), 0.0
    import datetime
    day = (when or datetime.date.today()).isoformat()
    u = _load_usage()
    rec = u.setdefault(day, {"spent": 0.0, "samples": 0})
    rec["spent"] = round(rec["spent"] + delta, 4)
    rec["samples"] += 1
    # 只保留最近 60 天
    if len(u) > 60:
        for k in sorted(u)[:-60]:
            u.pop(k, None)
    _save_usage(u)
    return round(rec["spent"], 2), round(delta, 2)


def _today_spent(when=None):
    import datetime
    day = (when or datetime.date.today()).isoformat()
    rec = _load_usage().get(day)
    return round(rec["spent"], 2) if rec else 0.0


def daily_average(days=7):
    """最近 N 天的日均消耗（按有记录的天数算）。"""
    import datetime
    u = _load_usage()
    if not u:
        return 0.0
    today = datetime.date.today()
    vals = []
    for i in range(days):
        d = (today - datetime.timedelta(days=i)).isoformat()
        if d in u:
            vals.append(u[d]["spent"])
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def days_left(balance):
    """按最近日均消耗估算还能用几天。"""
    avg = daily_average(7)
    if not avg or balance is None:
        return None
    return max(0, int(float(balance) / avg))


def fmt(v, unit=""):
    if v is None:
        return "?"
    sym = {"CNY": "¥", "USD": "$"}.get(unit, "")
    return f"{sym}{v:,.2f}" if sym else f"{v:,.2f}"


class Bubble(tk.Toplevel):
    """气泡：圆角白底 + 深蓝描边（对齐参考设计的样式）。多屏安全 + 跟随桌宠。"""

    W, H = 300, 104

    def __init__(self, pet):
        self.pet = pet                     # 保留 Pet 引用（Toplevel 的 master 是窗口）
        super().__init__(pet.win)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=KEY)
        self.attributes("-transparentcolor", KEY)
        self.canvas = tk.Canvas(self, bg=KEY, highlightthickness=0, width=self.W,
                                height=self.H)
        self.canvas.pack()
        self._hide_id = None
        self._follow_id = None
        self._text, self._warn = "", False

    def alive(self):
        """气泡窗口是否仍然存在（宿主实例可能已被销毁）。"""
        return _win_alive(self)

    def show(self, text, warn=False):
        if not self.alive():
            return                        # 已随宿主销毁，静默忽略
        self._text, self._warn = text, warn
        self._render()
        self.deiconify()
        self._place()
        if self._hide_id:
            self.after_cancel(self._hide_id)
        self._hide_id = self.after(BUBBLE_MS, self.withdraw)
        if self._follow_id:
            self.after_cancel(self._follow_id)
        self._follow()

    def _render(self):
        if not self.alive():
            return
        c = self.canvas
        try:
            c.delete("all")
        except tk.TclError:
            return
        edge = "#c62828" if self._warn else "#2b3a6b"
        fill = "#fff4f4" if self._warn else "#f8faff"
        c.create_polygon(10, 8, 290, 8, 290, 72, 162, 72, 150, 86, 138, 72, 10, 72,
                         smooth=True, splinesteps=12, fill=fill, outline=edge, width=3)
        c.create_text(150, 40, text=self._text, width=250, justify="center",
                      font=("Microsoft YaHei UI", 10, "bold"),
                      fill="#8c1d1d" if self._warn else "#22315f")

    def _place(self):
        """定位到桌宠头顶；贴屏幕边缘时自动翻到下方；跨屏不越界。"""
        mw = self.pet.win
        if not _win_alive(mw):
            return
        mx, my = mw.winfo_x(), mw.winfo_y()
        mwd, mh = mw.winfo_width(), mw.winfo_height()
        # 跨屏几何查询较贵，且屏幕布局不会频繁变化 → 缓存
        if getattr(self, "_bounds_cache", None) is None:
            self._bounds_cache = self.pet.screen_bounds()
        vx0, vy0, vx1, vy1 = self._bounds_cache
        x = max(vx0 + 6, min(mx + mwd // 2 - self.W // 2, vx1 - self.W - 6))
        y = my - self.H + 16                     # 默认在头顶
        if y < vy0 + 6:                          # 顶部放不下 → 翻到脚下
            y = min(my + mh - 16, vy1 - self.H - 6)
        y = max(vy0 + 6, min(y, vy1 - self.H - 6))
        pos = (self.W, self.H, x, y)
        if getattr(self, "_last_pos", None) != pos:
            self._last_pos = pos
            self.geometry(f"{self.W}x{self.H}+{x}+{y}")

    def _follow(self):
        """跟随桌宠移动。只在气泡可见且有宿主时运行；位置没变就不重设几何。"""
        if not self.alive() or not self.winfo_viewable():
            self._follow_id = None
            return
        try:
            self._place()
            self._follow_id = self.after(120, self._follow)
        except tk.TclError:
            self._follow_id = None

    def hide(self):
        self.withdraw()


class PetSettings(tk.Toplevel):
    """桌宠自带的 DeepSeek Key 配置窗：填写 → 测试 → 保存（DPAPI 加密）。"""

    def __init__(self, pet):
        super().__init__(pet.win)
        self.pet = pet
        self.title("鲸鱼娘 · 配置")
        self.attributes("-topmost", True)
        self.configure(bg="#f4f6fb", padx=16, pady=12)
        self.resizable(False, False)
        self.bind("<Escape>", lambda e: self.destroy())

        tk.Label(self, text="DeepSeek API Key", bg="#f4f6fb", fg="#2b3a6b",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        tk.Label(self, text="在 platform.deepseek.com/api_keys 获取；保存时本地加密（DPAPI，仅本机可解密）",
                 bg="#f4f6fb", fg="#7a8095", font=("Microsoft YaHei UI", 8),
                 wraplength=380, justify="left").pack(anchor="w", pady=(0, 6))

        row = tk.Frame(self, bg="#f4f6fb")
        row.pack(fill="x")
        self.var_key = tk.StringVar(value=(pet.cfg or {}).get("deepseek", ""))
        self.ent = tk.Entry(row, textvariable=self.var_key, show="*", width=42,
                            font=("Consolas", 9), relief="solid", bd=1)
        self.ent.pack(side="left", fill="x", expand=True)
        self.var_show = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text="显示", variable=self.var_show, command=self._toggle_show,
                       bg="#f4f6fb", activebackground="#f4f6fb",
                       font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(4, 0))

        env_on = bool(os.environ.get("DEEPSEEK_API_KEY"))
        tk.Label(self, text="检测到环境变量 DEEPSEEK_API_KEY（留空即用它）" if env_on else "",
                 bg="#f4f6fb", fg="#1b8a3d",
                 font=("Microsoft YaHei UI", 8)).pack(anchor="w", pady=(2, 0))

        tk.Label(self, text="余额告警阈值（低于该值气泡变红）", bg="#f4f6fb", fg="#2b3a6b",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        trow = tk.Frame(self, bg="#f4f6fb")
        trow.pack(anchor="w")
        self.var_warn = tk.StringVar(value=str(int(WARN_BELOW)))
        tk.Entry(trow, textvariable=self.var_warn, width=8, font=("Consolas", 9),
                 relief="solid", bd=1).pack(side="left")
        tk.Label(trow, text="（元；默认 10）", bg="#f4f6fb", fg="#7a8095",
                 font=("Microsoft YaHei UI", 8)).pack(side="left", padx=4)

        self.lbl_test = tk.Label(self, text="", bg="#f4f6fb", fg="#7a8095",
                                 font=("Microsoft YaHei UI", 9), wraplength=380,
                                 justify="left")
        self.lbl_test.pack(anchor="w", pady=(10, 0))

        foot = tk.Frame(self, bg="#f4f6fb")
        foot.pack(fill="x", pady=(10, 0))
        tk.Button(foot, text="测试连通性", command=self._test, bg="#e7ecf7", fg="#2b3a6b",
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  font=("Microsoft YaHei UI", 9)).pack(side="left")
        tk.Button(foot, text="保存并生效", command=self._save, bg="#1b6fd8", fg="white",
                  relief="flat", padx=14, pady=3, cursor="hand2",
                  font=("Microsoft YaHei UI", 9, "bold")).pack(side="right")
        tk.Button(foot, text="取消", command=self.destroy, bg="#e7ecf7", fg="#2b3a6b",
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  font=("Microsoft YaHei UI", 9)).pack(side="right", padx=6)

        self.update_idletasks()
        x = max(10, pet.win.winfo_x() - self.winfo_reqwidth() - 16)
        y = max(10, pet.win.winfo_y() - 40)
        self.geometry(f"+{x}+{y}")
        if not self.var_key.get() and not env_on:
            self.lbl_test.config(text="还没填 Key，填好点「测试连通性」验证一下。", fg="#b26a00")

    def _toggle_show(self):
        self.ent.config(show="" if self.var_show.get() else "*")

    def _test(self):
        key = self.var_key.get().strip() or os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            self.lbl_test.config(text="请先填 Key。", fg="#c62828")
            return
        self.lbl_test.config(text="正在查询…", fg="#7a8095")
        self.update_idletasks()

        def work():
            try:
                res = quota.q_deepseek(key)
                val, unit = res.get("value"), res.get("unit", "")
                sub = res.get("sub")
                txt = f"✅ 成功：余额 {fmt(val, unit)}" + (f"（{sub}）" if sub else "")
                self.after(0, lambda: self.lbl_test.config(text=txt, fg="#1b8a3d"))
            except Exception as e:
                msg = str(e)
                if "401" in msg or "Authentication" in msg:
                    msg = "Key 无效或已失效（401）"
                m = msg[:90]
                self.after(0, lambda: self.lbl_test.config(text=f"❌ 失败：{m}", fg="#c62828"))

        threading.Thread(target=work, daemon=True).start()

    def _save(self):
        global WARN_BELOW
        key = self.var_key.get().strip()
        try:
            warn = float(self.var_warn.get().strip() or WARN_BELOW)
        except ValueError:
            self.lbl_test.config(text="告警阈值要填数字。", fg="#c62828")
            return
        WARN_BELOW = warn
        cfg = dict(self.pet.cfg or quota.TEMPLATE)
        cfg["deepseek"] = key
        path = self.pet.cfg_path or os.path.join(HERE, "data", quota.CONFIG_NAME)
        try:
            quota.save_config(cfg, path)          # DPAPI 加密落盘
        except OSError as e:
            self.lbl_test.config(text=f"保存失败：{e}", fg="#c62828")
            return
        for p in Pet.pets:                        # 增殖体共享同一份配置
            p.cfg, p.cfg_path = cfg, path
            p.last_query = 0
        self.pet.refresh(force=True)
        self.pet.bubble.show("配置已保存，正在刷新余额～" if key else "已清空 Key")
        self.destroy()


class Pet:
    """一只鲸鱼娘。支持多实例（增殖）与键盘互动。

    Windows 上多个 tk.Tk() 根窗口会崩，所以本体创建一个隐藏的 Tk root，
    本体与增殖体一律用 tk.Toplevel 承载。
    """

    pets = set()          # 所有存活实例
    _root = None          # 唯一的 Tk root（隐藏）

    @classmethod
    def root(cls):
        if cls._root is None:
            cls._root = tk.Tk()
            cls._root.withdraw()
        return cls._root

    def __init__(self, anchor=None, small=False, spawn_x=None, spawn_y=None):
        self.is_body = anchor is None
        self.win = tk.Toplevel(self.root())   # 本体也走 Toplevel，root 只当事件循环
        Pet.pets.add(self)
        self.cfg, self.cfg_path = quota.load_config()
        self.anchor = anchor                 # 增殖来源（None = 本体）
        self.balance = None
        self.unit = ""
        self.sub = ""
        self.last_query = 0.0
        self._querying = False
        self.auto = anchor is None
        # 自动增殖开关：从 ui.json 读，默认关闭
        # 开关值所有实例共享（菜单显示一致）；但只有本体真正执行自动增殖
        ui = _load_ui()
        self.auto_spawn = bool(ui.get("auto_spawn", AUTO_SPAWN_DEFAULT))
        self.move_style = _normalize_move_style(ui.get("move_style", "walk"))
        self.scale = 2 if small else 1       # 1=原尺寸 2=半尺寸
        self.walking = False
        self.debug_animation_enabled = False
        self.debug_move_style = None
        self.debug_direction = -1
        self.debug_paused = False
        self.debug_frame_index = 0
        self._debug_after_id = None
        self.dragging = False
        self._drag = None
        self._moved = False
        self._last_active = time.time()
        self._was_typing = False
        self._self_after_ids = []
        self._asset_frames = {}
        self._asset_paths = {}
        self._frame_anchors = {}  # key -> foot_y/center_x at current scale
        self._body_glow_cache = {}
        self._walk_frame_tick = 0
        self._blinking = False
        self._sleeping = False
        self._blink_after_id = None
        self._sleep_after_id = None
        self._blink_pose = "front"
        self._blink_index = 0
        self._sleep_index = 0
        self._typing_l = self._typing_r = 0
        self.keys_held = frozenset()
        self._key_glow_until = {}
        self.typing_until = 0.0
        self.typing_lock_until = 0.0
        self._kb_enabled = True

        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=KEY)
        self.win.attributes("-transparentcolor", KEY)

        self.imgs = {}
        self._lit_cache = {}
        self._load_assets()
        # Optional movement sets keep older installs compatible.  If either
        # direction for the requested style is unavailable, use ordinary walk.
        if not all(self._asset_frames.get(role)
                   for role in MOVE_STYLE_ROLES[self.move_style]):
            self.move_style = "walk"
        # 尺寸先算，_build_stage 要用它撑开舞台
        if SELF_CONTAINED:
            self._stage_w = max(im.width() for im in self.scaled.values())
            self._kb_y = 0
            self._stage_h = max(im.height() for im in self.scaled.values())
        else:
            self._stage_w = max(self.scaled["front"].width(),
                                self.scaled["keyboard"].width()) + 10
            self._kb_y = (self.scaled["front"].height()
                          - int(self.scaled["keyboard"].height() * 0.42))
            self._stage_h = self._kb_y + self.scaled["keyboard"].height()
        self._build_stage()
        self._bind_events()

        self.bubble = Bubble(self)
        self.bubble.withdraw()
        self._build_menu()

        if spawn_x is None:
            work_area = _get_primary_work_area(self.win)
            spawn_x, spawn_y = _initial_position(
                work_area, self._stage_w, self._stage_h)
        self.win.geometry(f"{self._stage_w}x{self._stage_h}+{spawn_x}+{spawn_y}")
        self.face("front")
        # spawned pets are created inside a menu callback (mainloop event),
        # so the window is already mapped when -transparentcolor was set;
        # re-apply after mapping to avoid a white box.
        self.win.attributes("-transparentcolor", KEY)

        self.win.after(600, lambda: self.refresh(force=False, quiet=True))
        self._bob_id = self.win.after(900, self._bob)
        self._walk_id = self.win.after(4000, self._maybe_walk)
        if self.auto:
            self._auto_id = self.win.after(AUTO_MS, self._auto_tick)
        self._idle_id = self.win.after(300, self._idle_tick)
        self._key_id = self.win.after(KEY_POLL_MS, self._key_tick)

    # ---------- 素材与舞台 ----------
    def _load_assets(self):
        manifest = _load_asset_manifest()
        required_roles = {"front", "front_typing", "side_l", "side_r", "back"}
        for role in ASSET_DEFAULTS:
            files = _manifest_files(manifest, role)
            if role in required_roles and not files:
                raise SystemExit(f"manifest 缺少必需素材配置: {role}")
            frames = []
            for index, filename in enumerate(files):
                key = _asset_key(role, index)
                p = os.path.join(ASSETS, filename)
                if not os.path.exists(p):
                    # Extra movement styles, later frames, blink and sleep are optional.
                    if role in ("blink", "sleep") or role in OPTIONAL_MOVE_ROLES or (
                            role in ("side_l", "side_r") and index > 0):
                        continue
                    raise SystemExit(f"缺少素材: {p}")
                self.imgs[key] = tk.PhotoImage(file=p)
                self._asset_paths[key] = p
                frames.append(key)
            self._asset_frames[role] = frames

        # SELF_CONTAINED 模式下正面 PNG 已经包含键盘和手，不再强制加载旧分层。
        # 关闭该模式时保留原有分层 Runtime 的加载路径。
        if not SELF_CONTAINED:
            for name in ("keyboard", "arm_l", "arm_r", "hand", "hand_up"):
                p = os.path.join(ASSETS, f"{name}.png")
                if not os.path.exists(p):
                    raise SystemExit(f"缺少素材: {p}\n请先运行 python pet_assets/make_keyboard.py")
                self.imgs[name] = tk.PhotoImage(file=p)

        # 键位表：vK -> 键帽矩形/中心，用于精确点亮与左右手分工
        km = os.path.join(ASSETS, "keys_map.json")
        try:
            if os.path.exists(km):
                with open(km, encoding="utf-8") as f:
                    keys = json.load(f)
            else:
                keys = []
        except (OSError, ValueError, TypeError):
            keys = []
        self._key_rects = keys
        self._keys_by_vk = {k["vk"]: k for k in keys if k.get("vk") is not None}
        self._blink_frames = self._asset_frames.get("blink", [])
        self._sleep_frames = self._asset_frames.get("sleep", [])
        self._apply_scale()

    def _apply_scale(self):
        s = self.scale
        self.scaled = {k: (img.subsample(s) if s > 1 else img)
                       for k, img in self.imgs.items()}
        self._body_glow_cache.clear()
        self._rebuild_frame_anchors()

    def _rebuild_frame_anchors(self):
        """Cache per-frame foot/center anchors, scaled like PhotoImage.subsample."""
        s = max(1, int(self.scale))
        anchors = {}
        for key, path in self._asset_paths.items():
            try:
                native = _frame_anchor_from_png(path)
            except Exception:
                img = self.imgs.get(key)
                if img is None:
                    continue
                native = {
                    "foot_y": img.height() - 1,
                    "center_x": img.width() / 2.0,
                    "left": 0,
                    "right": img.width() - 1,
                    "width": img.width(),
                    "height": img.height(),
                }
            left = native["left"] // s
            right = native["right"] // s
            anchors[key] = {
                "foot_y": native["foot_y"] // s,
                "center_x": (left + right) / 2.0,
                "width": native["width"] // s,
                "height": native["height"] // s,
            }
        self._frame_anchors = anchors

    def _foot_baseline(self):
        """Shared stage Y where content feet sit (walk target: y=261 on h=264)."""
        s = max(1, int(self.scale))
        return (self._stage_h * s - FOOT_PAD_PX) // s

    def _current_body_key(self):
        return (getattr(self, "_shown_walk_frame", None)
                or getattr(self, "_shown_frame", None)
                or "front")

    def _place_body(self, key=None, bob=0):
        """Offset body so feet share a baseline and content center stays mid-stage."""
        if not hasattr(self, "body_lbl"):
            return
        key = key or self._current_body_key()
        img = self.scaled.get(key)
        if img is None:
            return
        anchor = self._frame_anchors.get(key)
        if anchor is None:
            dx, dy = 0, int(bob)
        else:
            dy = self._foot_baseline() - anchor["foot_y"] + int(bob)
            dx = int(round(img.width() / 2.0 - anchor["center_x"]))
        self.body_lbl.place(relx=0.5, rely=0, anchor="n", x=dx, y=dy)

    def _build_stage(self):
        """统一色键底：键盘与手在后景，她压在前景。

        （色键透明是整窗生效的，所以透明处能看到后景——前后关系靠摆放实现。）
        stage 必须撑满窗口，否则 place(relx=.) 会以 1x1 父容器计算而偏出画面。
        """
        self.stage = tk.Frame(self.win, bg=KEY, width=self._stage_w, height=self._stage_h)
        self.stage.pack_propagate(False)
        self.stage.place(x=0, y=0, relwidth=1, relheight=1)
        self.kb_lbl = tk.Label(self.stage, bg=KEY, bd=0)
        self.arm_l_lbl = tk.Label(self.stage, bg=KEY, bd=0)
        self.arm_r_lbl = tk.Label(self.stage, bg=KEY, bd=0)
        self.hand_l = tk.Label(self.stage, bg=KEY, bd=0)
        self.hand_r = tk.Label(self.stage, bg=KEY, bd=0)
        self.body_lbl = tk.Label(self.stage, bg=KEY, bd=0)

    def _pack_stage(self):
        """BongoCat 式前后关系：她在后、键盘压在她身前、双手搭在键盘上。

        色键透明是整窗生效的，z 序只能靠 lift 控制：键盘必须叠在身体之上，
        否则键盘会被她挡住只剩一条边（这正是之前的 bug）。
        """
        if SELF_CONTAINED:
            self._place_body(self._current_body_key())
            for w in (self.kb_lbl, self.arm_l_lbl, self.arm_r_lbl,
                      self.hand_l, self.hand_r):
                w.place_forget()
            self.body_lbl.lift()
            return
        kbw = self.scaled["keyboard"].width()
        self._place_body(self._current_body_key())
        self.kb_lbl.place(relx=0.5, rely=0, anchor="n", y=self._kb_y)
        # 手落在键帽上：左手管键盘左半，右手管右半（对齐真实打字指区）
        paw_y = self._kb_y + int(self.scaled["keyboard"].height() * 0.30)
        self._paw_y = paw_y
        hh = self.scaled["hand"].height()
        self._paw_dx = int(kbw * 0.22)          # 距中心的水平偏移
        for lbl, sgn in ((self.hand_l, -1), (self.hand_r, 1)):
            lbl.place(relx=0.5, rely=0, anchor="center",
                      x=sgn * self._paw_dx, y=paw_y + hh // 2)
        # 手臂从她身侧垂下，末端接到手腕
        for lbl, img, sgn in ((self.arm_l_lbl, "arm_l", -1),
                              (self.arm_r_lbl, "arm_r", 1)):
            aw, ah = self.scaled[img].width(), self.scaled[img].height()
            lbl.place(relx=0.5, rely=0, anchor="center",
                      x=sgn * (self._paw_dx + aw // 3),
                      y=paw_y - ah // 2 + 8)
        self.body_lbl.lower()        # 她在后
        self.kb_lbl.lift()           # 键盘压在她身前
        self.arm_l_lbl.lift()
        self.arm_r_lbl.lift()        # 手臂在键盘上
        self.hand_l.lift()
        self.hand_r.lift()           # 爪子最前

    def _bind_events(self):
        for w in (self.win, self.stage, self.body_lbl, self.kb_lbl,
                  self.arm_l_lbl, self.arm_r_lbl, self.hand_l, self.hand_r):
            w.bind("<Button-1>", self._press)
            w.bind("<B1-Motion>", self._motion)
            w.bind("<ButtonRelease-1>", self._release)
            w.bind("<Button-3>", self._menu)

    def _build_menu(self):
        self.menu = tk.Menu(self.win, tearoff=0)
        self.menu.add_command(label="🔵 看看余额", command=self.speak_balance)
        self.menu.add_command(label="↻ 刷新余额", command=lambda: self.refresh(force=True))
        self.menu.add_command(label="🔑 配置 DeepSeek Key…", command=self.open_settings)
        if self.auto:
            self.menu.add_command(label=f"⏱ 自动刷新：{'开' if self.auto else '关'}",
                                  command=self._toggle_auto)
        self.menu.add_command(label="🔍 尺寸切换(小/中)", command=self._toggle_size)
        self.menu.add_command(label="🐋 增殖一只", command=self.spawn)
        self.menu.add_command(
            label=f"♾ 自动增殖：{'开' if self.auto_spawn else '关'}",
            command=self._toggle_auto_spawn)
        self.menu.add_command(label=f"⌨ 键盘互动：{'开' if self._kb_enabled else '关'}",
                              command=self._toggle_keyboard)
        self.menu.add_command(label="📌 置顶开关", command=self._toggle_top)
        self.menu.add_separator()
        if self.anchor is None:
            self.menu.add_command(label="✕ 退出全部", command=self.quit_all)
        else:
            self.menu.add_command(label="✕ 让她消失", command=self.close_self)

        debug_menu = tk.Menu(self.menu, tearoff=0)
        self._debug_mode_var = tk.StringVar(master=self.win, value="normal")
        self._debug_direction_var = tk.StringVar(master=self.win, value="left")
        debug_menu.add_radiobutton(
            label="Normal", variable=self._debug_mode_var, value="normal",
            command=lambda: self._debug_set_style(None))
        debug_menu.add_separator()
        for style in ("walk", "run", "duo", "ride"):
            debug_menu.add_radiobutton(
                label=style.title(), variable=self._debug_mode_var, value=style,
                command=lambda selected=style: self._debug_set_style(selected))
        debug_menu.add_separator()
        debug_menu.add_radiobutton(
            label="Left", variable=self._debug_direction_var, value="left",
            command=lambda: self._debug_set_direction(-1))
        debug_menu.add_radiobutton(
            label="Right", variable=self._debug_direction_var, value="right",
            command=lambda: self._debug_set_direction(1))
        debug_menu.add_separator()
        debug_menu.add_command(label="Pause", command=self._debug_pause)
        debug_menu.add_command(label="Resume", command=self._debug_resume)
        debug_menu.add_command(label="Previous Frame", command=lambda: self._debug_step(-1))
        debug_menu.add_command(label="Next Frame", command=lambda: self._debug_step(1))
        debug_menu.add_separator()
        debug_menu.add_command(label="Export Animation GIF", command=self._debug_export_gif)
        self.menu.add_cascade(label="Animation Debug", menu=debug_menu)

    def _active_glow_vks(self):
        now = time.time()
        active = {vk for vk, until in self._key_glow_until.items()
                  if until > now or vk in self.keys_held}
        self._key_glow_until = {
            vk: until for vk, until in self._key_glow_until.items()
            if until > now or vk in self.keys_held
        }
        return active

    def _body_image(self, key, pressed_vks=()):
        """返回正面整图或带内嵌键盘高亮的正面整图。"""
        if (not SELF_CONTAINED or key not in ("front", "front_typing")
                or not pressed_vks or not self._key_rects):
            return self.scaled[key]
        cache_key = (key, tuple(sorted(pressed_vks)), self.scale)
        cached = self._body_glow_cache.get(cache_key)
        if cached is not None:
            return cached
        path = self._asset_paths.get(key)
        if not path:
            return self.scaled[key]
        with open(path, "rb") as f:
            width, height, rgba = pngtool.decode(f.read())
        stage_origin_x = (self._stage_w - width) // 2
        rgba = _draw_embedded_key_glow(
            rgba, width, height, stage_origin_x,
            EMBEDDED_KEYBOARD_BBOX, self._key_rects, pressed_vks,
        )
        image = tk.PhotoImage(data=pngtool.encode(width, height, rgba))
        if self.scale > 1:
            image = image.subsample(self.scale)
        if len(self._body_glow_cache) > 40:
            self._body_glow_cache.clear()
        self._body_glow_cache[cache_key] = image
        return image

    def _set_body_image(self, key, pressed_vks=(), bob=0):
        self.body_lbl.config(image=self._body_image(key, pressed_vks))
        self._place_body(key, bob=bob)

    def face(self, key):
        if not _win_alive(self.win):
            return
        self._shown_walk = None
        self._shown_walk_frame = None
        self._shown_frame = key
        self._shown_glow_vks = set()
        self.pose = key
        glow = self._active_glow_vks() if key in ("front", "front_typing") else ()
        self._shown_glow_vks = set(glow)
        self._set_body_image(key, glow)
        front = key == "front"
        self.win.update_idletasks()
        if front:
            self._pack_stage()
            if not SELF_CONTAINED:
                self.kb_lbl.config(image=self.scaled["keyboard"])
                self.arm_l_lbl.config(image=self.scaled["arm_l"])
                self.arm_r_lbl.config(image=self.scaled["arm_r"])
                self.hand_l.config(image=self.scaled["hand"])
                self.hand_r.config(image=self.scaled["hand"])
        else:
            for w in (self.kb_lbl, self.arm_l_lbl, self.arm_r_lbl,
                      self.hand_l, self.hand_r):
                w.place_forget()
        self._resize()

    def _resize(self):
        """按当前素材尺寸重设窗口大小（位置不动）。"""
        if SELF_CONTAINED:
            self._stage_w = max(im.width() for im in self.scaled.values())
            self._kb_y = 0
            self._stage_h = max(im.height() for im in self.scaled.values())
        else:
            self._stage_w = max(self.scaled["front"].width(),
                                self.scaled["keyboard"].width()) + 10
            self._kb_y = (self.scaled["front"].height()
                          - int(self.scaled["keyboard"].height() * 0.42))
            self._stage_h = self._kb_y + self.scaled["keyboard"].height()
        self.win.geometry(f"{self._stage_w}x{self._stage_h}")
        self._place_body(self._current_body_key())

    # ---------- 键盘互动 ----------
    def _key_tick(self):
        if not _win_alive(self.win):
            return
        """轮询全局按键 → 精确点亮对应键帽、对应侧的手抬起。"""
        held = key_state() if self._kb_enabled else frozenset()
        if held is not None and held != self.keys_held:
            new = held - self.keys_held
            self.keys_held = held
            now = time.time()
            if new:
                self._interrupt_walk()   # 打字打断散步，固定在打字姿势
            for vk in new:
                self.mark_active()
                self._key_glow_until[vk] = now + KEY_GLOW_HOLD
                self.typing_until = now + TYPING_HOLD
                self.typing_lock_until = now + TYPING_LOCK
                # 按键盘左右分区决定哪只手敲：以空格键中心为界
                if not SELF_CONTAINED:
                    cx = self._split_x()
                    key = self._keys_by_vk.get(vk)
                    if key:
                        if key["center"][0] < cx:
                            self._typing_l = 1
                        else:
                            self._typing_r = 1
        if self._sleeping or self._blinking:
            self._key_id = self.win.after(KEY_POLL_MS, self._key_tick)
            return
        glow_vks = self._active_glow_vks()
        typing = ((time.time() < self.typing_until and bool(self.keys_held))
                  or bool(glow_vks))
        if self.pose != "front":
            self._was_typing = typing
            self._key_id = self.win.after(KEY_POLL_MS, self._key_tick)
            return
        if not typing and self.typing_now():
            # 打字间隙：保持"手落在键盘上"的待命姿势（SELF_CONTAINED 用 front 帧）
            if SELF_CONTAINED and getattr(self, "_shown_frame", None) != "front":
                self._shown_frame = "front"
                self._set_body_image("front", glow_vks)
            self._was_typing = False
            self._key_id = self.win.after(KEY_POLL_MS, self._key_tick)
            return
        if SELF_CONTAINED:
            # 立绘自带键盘与双手：整图切换，同时叠加内嵌按键高亮。
            want = "front_typing" if typing else "front"
            if (getattr(self, "_shown_frame", None) != want
                    or glow_vks != getattr(self, "_shown_glow_vks", set())):
                self._shown_frame = want
                self._shown_glow_vks = set(glow_vks)
                self._set_body_image(want, glow_vks)
            self._was_typing = typing
            self._key_id = self.win.after(KEY_POLL_MS, self._key_tick)
            return
        if typing:
            pressed = self._pressed_vks()
            self.kb_lbl.config(image=self._kb_image(pressed))
            hh = self.scaled["hand"].height()
            for lbl, up in ((self.hand_l, self._typing_l), (self.hand_r, self._typing_r)):
                lbl.config(image=self.scaled["hand_up" if up else "hand"])
                lbl.place_configure(y=self._paw_y + hh // 2 - (2 if up else 0))
            self._typing_l = self._typing_r = 0
        elif self._was_typing and not self.typing_now():
            self.kb_lbl.config(image=self.scaled["keyboard"])
            hh = self.scaled["hand"].height()
            for lbl in (self.hand_l, self.hand_r):
                lbl.config(image=self.scaled["hand"])
                lbl.place_configure(y=self._paw_y + hh // 2)
        self._was_typing = typing
        self._key_id = self.win.after(KEY_POLL_MS, self._key_tick)

    def _split_x(self):
        """左右手分界：空格键中心（键盘水平中心偏左一点）。"""
        space = self._keys_by_vk.get(0x20)
        return space["center"][0] if space else self.scaled["keyboard"].width() / 2

    def _pressed_vks(self):
        """当前按下的、键盘上画得出的键码集合。"""
        return {vk for vk in self.keys_held if vk in self._keys_by_vk}

    def _kb_image(self, pressed_vks):
        """按需生成"按下这些键"的键盘图（带缓存，避免每次重画）。"""
        key = frozenset(pressed_vks)
        if key not in self._lit_cache:
            from pet_assets.make_keyboard import draw_board, KB_W, KB_H
            img = tk.PhotoImage(data=pngtool.encode(
                KB_W, KB_H, draw_board(lit_vks=key, keys=self._key_rects).raster()))
            if len(self._lit_cache) > 40:      # 简单上限，防无限增长
                self._lit_cache.clear()
            self._lit_cache[key] = img
        img = self._lit_cache[key]
        return img.subsample(self.scale) if self.scale > 1 else img

    def _toggle_keyboard(self):
        self._kb_enabled = not self._kb_enabled
        self.menu.entryconfigure(6, label=f"⌨ 键盘互动：{'开' if self._kb_enabled else '关'}")
        if self.debug_animation_enabled:
            self._debug_render_frame()
        elif not self._kb_enabled:
            self.face(self.pose)

    # ---------- 增殖 ----------
    def typing_now(self):
        """是否处于正在打字状态（打字间隙的短暂停不算中断）。"""
        return time.time() < self.typing_lock_until

    def _interrupt_walk(self):
        """打字打断散步：停下并立刻摆回正面打字姿势。"""
        if self.debug_animation_enabled:
            return
        if self.walking or self.pose != "front":
            self.walking = False
            self.face("front")

    def _cancel_blink(self):
        if self._blink_after_id:
            try:
                self.win.after_cancel(self._blink_after_id)
            except Exception:
                pass
            self._blink_after_id = None
        self._blinking = False

    def _cancel_sleep(self):
        if self._sleep_after_id:
            try:
                self.win.after_cancel(self._sleep_after_id)
            except Exception:
                pass
            self._sleep_after_id = None
        self._sleeping = False

    def _wake(self):
        """交互后退出 blink/sleep，恢复到正面普通姿态。"""
        if self.debug_animation_enabled:
            self._cancel_blink()
            self._cancel_sleep()
            return
        was_special = self._blinking or self._sleeping
        self._cancel_blink()
        self._cancel_sleep()
        if was_special:
            self.face("front")

    def mark_active(self):
        self._last_active = time.time()
        self._wake()

    def _start_blink(self):
        if (self.debug_animation_enabled or not self._blink_frames
                or self._blinking or self._sleeping
                or self.walking or self.dragging or self.typing_now()
                or self.pose != "front"):
            return
        self._blinking = True
        self._blink_pose = self.pose
        self._blink_index = 0
        frame = self._blink_frames[0]
        self._shown_frame = frame
        self.body_lbl.config(image=self.scaled[frame])
        self._place_body(frame)
        self._blink_after_id = self.win.after(BLINK_FRAME_MS, self._blink_tick)

    def _blink_tick(self):
        if not _win_alive(self.win) or not self._blinking:
            return
        next_index = self._blink_index + 1
        if next_index >= len(self._blink_frames):
            self._cancel_blink()
            self.face(self._blink_pose)
            return
        self._blink_index = next_index
        frame = self._blink_frames[next_index]
        self._shown_frame = frame
        self.body_lbl.config(image=self.scaled[frame])
        self._place_body(frame)
        self._blink_after_id = self.win.after(BLINK_FRAME_MS, self._blink_tick)

    def _enter_sleep(self):
        if (self.debug_animation_enabled or not self._sleep_frames
                or self._sleeping or self.dragging
                or self.typing_now()):
            return
        self._cancel_blink()
        self.walking = False
        if self.pose != "front":
            self.face("front")
        self._sleeping = True
        self._sleep_index = 0
        frame = self._sleep_frames[0]
        self._shown_frame = frame
        self.body_lbl.config(image=self.scaled[frame])
        self._place_body(frame)
        self._sleep_after_id = self.win.after(SLEEP_FRAME_MS, self._sleep_tick)

    def _sleep_tick(self):
        if not _win_alive(self.win) or not self._sleeping:
            return
        self._sleep_index = (self._sleep_index + 1) % len(self._sleep_frames)
        frame = self._sleep_frames[self._sleep_index]
        self._shown_frame = frame
        self.body_lbl.config(image=self.scaled[frame])
        self._place_body(frame)
        self._sleep_after_id = self.win.after(SLEEP_FRAME_MS, self._sleep_tick)

    def _idle_tick(self):
        """挂机够久 → 复制一个本体出来（只在还有空间时）。"""
        if not _win_alive(self.win):
            return
        if self.debug_animation_enabled:
            self._idle_id = self.win.after(5000, self._idle_tick)
            return
        idle = time.time() - self._last_active
        if idle > SLEEP_AFTER_MS / 1000:
            self._enter_sleep()
        if idle > IDLE_SPAWN_MS / 1000:
            # 只有本体自动增殖：增殖体即使开关是开也不复制自己
            if self.auto_spawn and self.is_body and len(Pet.pets) < MAX_PETS:
                self.spawn()
            self._last_active = time.time()
            self._idle_id = self.win.after(IDLE_SPAWN_MS, self._idle_tick)
            return
        if (not self._sleeping and self._blink_frames and not self.walking
                and not self.dragging and self.pose == "front"
                and random.random() < 0.35):
            self._start_blink()
        self._idle_id = self.win.after(5000, self._idle_tick)

    def spawn(self):
        if not _win_alive(self.win):
            return None                   # 宿主已销毁，不再增殖
        if len(Pet.pets) >= MAX_PETS:
            self.bubble.show(f"已经 {MAX_PETS} 只啦，屏幕要装不下了…", True)
            return None
        vx0, vy0, vx1, vy1 = self.screen_bounds()
        nx = max(vx0 + 8, min(self.win.winfo_x() - 150, vx1 - 240))
        ny = max(vy0 + 8, min(self.win.winfo_y() + 90, vy1 - 300))
        child = Pet(anchor=self, small=True, spawn_x=nx, spawn_y=ny)
        child.balance, child.unit, child.sub = self.balance, self.unit, self.sub
        child.mark_active()
        self.bubble.show(f"增殖成功～现在有 {len(Pet.pets)} 只鲸鱼娘了 🐋")
        return child

    def open_settings(self):
        """桌宠自带的配置窗口（不必再去开桌面挂件）。"""
        PetSettings(self)

    def close_self(self):
        self.shutdown()

    def shutdown(self):
        """销毁实例：只取消本实例注册的回调，再关窗口。

        注意：after info 返回的是整个 Tcl 解释器的定时器列表（所有实例共享同一个
        Tk root），按它逐个取消会把别的实例和外部定时器一起干掉，导致事件循环
        再也不派发任何定时器。所以这里只清自己持有的那几个 id。
        """
        Pet.pets.discard(self)
        self.walking = False
        for aid_attr in ("_bob_id", "_walk_id", "_idle_id", "_key_id",
                         "_auto_id", "_query_id", "_blink_after_id",
                         "_sleep_after_id", "_debug_after_id"):
            aid = getattr(self, aid_attr, None)
            if aid:
                try:
                    self.win.after_cancel(aid)
                except Exception:
                    pass
                setattr(self, aid_attr, None)
        for obj in (getattr(self, "bubble", None),):
            if obj is None:
                continue
            for aid_attr in ("_hide_id", "_follow_id"):
                aid = getattr(obj, aid_attr, None)
                if aid:
                    try:
                        obj.after_cancel(aid)
                    except Exception:
                        pass
                    setattr(obj, aid_attr, None)
            try:
                obj.destroy()
            except Exception:
                pass
        try:
            self.win.destroy()
        except Exception:
            pass

    def quit_all(self):
        for p in list(Pet.pets):
            p.shutdown()
        Pet.pets.clear()
        if Pet._root is not None:
            try:
                Pet._root.destroy()
            except Exception:
                pass
            Pet._root = None

    # ---------- 多屏几何 ----------
    def screen_bounds(self):
        """虚拟桌面边界（Tk 坐标，覆盖所有显示器）。

        winfo_screenwidth 只有主屏宽度，跨屏定位必须用 vroot。实测 Tk 在
        Windows 上就是"主屏缩放 + 副屏物理"的混合坐标空间，而 vroot 与
        Tk 的窗口坐标同空间（勿再做 DPI 换算，会算错）。
        """
        try:
            vw, vh = self.win.winfo_vrootwidth(), self.win.winfo_vrootheight()
            if vw <= 0 or vh <= 0:                  # 兜底：退回主屏
                return 0, 0, self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            vx, vy = self.win.winfo_vrootx(), self.win.winfo_vrooty()
            return vx, vy, vx + vw, vy + vh
        except tk.TclError:
            return 0, 0, 1920, 1080                 # 窗口已销毁：返回保守值，不抛异常

    # ---------- 动作 ----------
    def _bob(self):
        if not _win_alive(self.win):
            return
        if (not self.walking and not self.dragging and not self._blinking
                and not self._sleeping and self.pose == "front"):
            dy = 1 if (int(time.time() * 2) % 2) else 0
            self._place_body(self._current_body_key(), bob=dy)
        self._bob_id = self.win.after(700, self._bob)

    def _maybe_walk(self):
        if not _win_alive(self.win):
            return
        if (not self.debug_animation_enabled and not self.walking
                and not self.dragging and not self.typing_now()
                and not self._sleeping and not self._blinking
                and random.random() < 0.55):
            self._walk_start()
        self._walk_id = self.win.after(random.randint(6000, 15000), self._maybe_walk)

    def _walk_start(self):
        self.walking = True
        self.dir = random.choice((-1, 1))
        self._walk_frame_tick = 0
        self._last_walk_dir = self.dir
        self.face(self._move_role(self.dir))
        steps = random.randint(30, 110)
        self._walk_step(steps)

    def _move_role(self, direction):
        """Select the configured directional animation, falling back to walk."""
        left_role, right_role = MOVE_STYLE_ROLES.get(
            self.move_style, MOVE_STYLE_ROLES["walk"]
        )
        role = right_role if direction > 0 else left_role
        if self._asset_frames.get(role):
            return role
        return "side_r" if direction > 0 else "side_l"

    def _walk_step(self, left):
        if not _win_alive(self.win):
            return
        if self.debug_animation_enabled:
            self.walking = False
            return
        if (not self.walking or self.dragging or left <= 0 or self.typing_now()
                or self._sleeping or self._blinking):
            self.walking = False
            if self.pose != "front":
                self.face("front")
            return
        x, y, self.dir, _monitor = _next_walk_position(
            _get_monitor_work_areas(self.win),
            self.win.winfo_x(), self.win.winfo_y(),
            self.win.winfo_width(), self.win.winfo_height(), self.dir,
            step=MOVE_STEP_PIXELS.get(self.move_style, MOVE_STEP_PIXELS["walk"]),
        )
        self.win.geometry(f"+{x}+{y}")
        if self.dir != getattr(self, "_last_walk_dir", self.dir):
            self.face(self._move_role(self.dir))
        self._last_walk_dir = self.dir
        base = self._move_role(self.dir)
        frames = self._asset_frames.get(base) or [base]
        hold_ticks = MOVE_FRAME_HOLD_TICKS.get(
            self.move_style, MOVE_FRAME_HOLD_TICKS["walk"]
        )
        frame = frames[(self._walk_frame_tick // hold_ticks) % len(frames)]
        self._walk_frame_tick += 1
        bob = 1 if (left // 4) % 2 == 0 else 0
        if getattr(self, "_shown_walk_frame", None) != frame:
            self._shown_walk_frame = frame
            self.body_lbl.config(image=self.scaled[frame])
        self._place_body(frame, bob=bob)
        self.win.after(MOVE_TICK_MS, lambda: self._walk_step(left - 1))

    def _debug_cancel_timer(self):
        aid = self._debug_after_id
        self._debug_after_id = None
        if aid:
            try:
                self.win.after_cancel(aid)
            except Exception:
                pass

    def _debug_interval_ms(self):
        hold_ticks = MOVE_FRAME_HOLD_TICKS.get(
            self.debug_move_style, MOVE_FRAME_HOLD_TICKS["walk"]
        )
        return MOVE_TICK_MS * hold_ticks

    def _debug_schedule(self):
        if (self.debug_animation_enabled and not self.debug_paused
                and _win_alive(self.win) and self._debug_after_id is None):
            self._debug_after_id = self.win.after(
                self._debug_interval_ms(), self._debug_tick)

    def _debug_set_style(self, style):
        if style not in MOVE_STYLE_ROLES and style is not None:
            raise ValueError(f"unsupported debug animation: {style}")
        if style is None:
            self._debug_cancel_timer()
            self.debug_animation_enabled = False
            self.debug_move_style = None
            self.debug_paused = False
            self.walking = False
            self._debug_mode_var.set("normal")
            self._cancel_blink()
            self._cancel_sleep()
            self._last_active = time.time()
            self.face("front")
            return

        roles = MOVE_STYLE_ROLES[style]
        if not all(self._asset_frames.get(role) for role in roles):
            self._debug_mode_var.set(
                self.debug_move_style if self.debug_animation_enabled else "normal"
            )
            self.bubble.show(f"{style} 缺少完整方向帧，无法预览")
            return
        was_enabled = self.debug_animation_enabled
        self._debug_cancel_timer()
        self.debug_animation_enabled = True
        self.debug_move_style = style
        self.debug_paused = self.debug_paused if was_enabled else False
        self.debug_frame_index = 0
        self.walking = False
        self._debug_mode_var.set(style)
        self._cancel_blink()
        self._cancel_sleep()
        self._last_active = time.time()
        self._debug_render_frame()
        self._debug_schedule()

    def _debug_set_direction(self, direction):
        if direction not in (-1, 1):
            raise ValueError("debug direction must be -1 or 1")
        self._debug_cancel_timer()
        self.debug_direction = direction
        self._debug_direction_var.set("left" if direction < 0 else "right")
        if self.debug_animation_enabled:
            self.debug_frame_index = 0
            self._debug_render_frame()
            self._debug_schedule()

    def _debug_render_frame(self):
        if not self.debug_animation_enabled or not _win_alive(self.win):
            return
        role = MOVE_STYLE_ROLES[self.debug_move_style][
            1 if self.debug_direction > 0 else 0
        ]
        frames = self._asset_frames.get(role) or []
        if not frames:
            return
        self.debug_frame_index %= len(frames)
        frame_key = frames[self.debug_frame_index]
        if self.pose != role:
            self.face(role)
        self._shown_walk = None
        self._shown_walk_frame = frame_key
        self._shown_frame = frame_key
        self.body_lbl.config(image=self.scaled[frame_key])
        self._place_body(frame_key)

    def _debug_tick(self):
        self._debug_after_id = None
        if (not self.debug_animation_enabled or self.debug_paused
                or not _win_alive(self.win)):
            return
        role = MOVE_STYLE_ROLES[self.debug_move_style][
            1 if self.debug_direction > 0 else 0
        ]
        frame_count = len(self._asset_frames.get(role) or ())
        if frame_count:
            self.debug_frame_index = (self.debug_frame_index + 1) % frame_count
            self._debug_render_frame()
        self._debug_schedule()

    def _debug_pause(self):
        if not self.debug_animation_enabled:
            return
        self.debug_paused = True
        self._debug_cancel_timer()

    def _debug_resume(self):
        if not self.debug_animation_enabled:
            return
        self.debug_paused = False
        self._debug_schedule()

    def _debug_step(self, delta):
        if not self.debug_animation_enabled:
            return
        self._debug_pause()
        role = MOVE_STYLE_ROLES[self.debug_move_style][
            1 if self.debug_direction > 0 else 0
        ]
        frame_count = len(self._asset_frames.get(role) or ())
        if frame_count:
            self.debug_frame_index = (self.debug_frame_index + delta) % frame_count
            self._debug_render_frame()

    def _debug_export_gif(self):
        if not self.debug_animation_enabled:
            self.bubble.show("请先选择 Walk、Run、Duo 或 Ride")
            return
        role = MOVE_STYLE_ROLES[self.debug_move_style][
            1 if self.debug_direction > 0 else 0
        ]
        frame_keys = list(self._asset_frames.get(role) or ())
        direction = "right" if self.debug_direction > 0 else "left"
        try:
            path = _export_animation_gif(
                self.debug_move_style, direction, frame_keys, self._asset_paths,
                self._debug_interval_ms(),
            )
        except Exception as exc:
            self.bubble.show(f"GIF 导出失败：{exc}")
            return
        self.bubble.show(f"GIF 已导出：{os.path.relpath(path, HERE)}")

    # ---------- 拖拽 / 点击 ----------
    def _press(self, e):
        self.dragging = True
        self._moved = False
        self.mark_active()
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _motion(self, e):
        if self._drag:
            nx, ny = e.x_root - self._drag[0], e.y_root - self._drag[1]
            if abs(nx - self.win.winfo_x()) + abs(ny - self.win.winfo_y()) > 3:
                self._moved = True
                if not self.debug_animation_enabled:
                    self.face("side_r" if nx > self.win.winfo_x() else "side_l")
            self.win.geometry(f"+{nx}+{ny}")
            if self.bubble.winfo_viewable():
                self.bubble.show(self._bubble_text(), self._warn())

    def _release(self, e):
        self.dragging = False
        if self.debug_animation_enabled:
            self._debug_render_frame()
        else:
            self.face("front")
        if not self._moved:      # 单击 = 摸头 → 报余额
            self.speak_balance()

    def _menu(self, e):
        """弹出右键菜单。应用可能已被销毁（例如 quit_all 后残留的事件），需先判存活。"""
        if not _win_alive(self.win):
            return
        self.mark_active()
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        except tk.TclError:
            pass                      # 菜单弹出期间实例被销毁：忽略
        finally:
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass

    # ---------- 余额 ----------
    def _warn(self):
        return self.balance is not None and self.balance < WARN_BELOW

    def _bubble_text(self):
        """气泡内容：余额 + 今日消耗 + 可用天数（消耗来自本地记账）。"""
        if self.balance is None:
            return "还没拿到余额呢…" + chr(10) + "右键「刷新余额」试试？"
        head = "⚠ 余额快见底啦！" if self._warn() else "主人，DeepSeek 余额还有"
        spent = getattr(self, "_spent_today", 0.0) or 0.0
        delta = getattr(self, "_last_delta", 0.0) or 0.0
        parts = []
        if spent > 0:
            line = f"今日已用 {fmt(spent, self.unit)}"
            if delta > 0:
                line += f"（本次 -{fmt(delta, self.unit)}）"
            parts.append(line)
        left = days_left(self.balance)
        if left is not None:
            parts.append(f"按近期速度约还能用 {left} 天")
        if not parts and self.sub:
            parts.append(self.sub)
        tail = (chr(10) + " · ".join(parts)) if parts else ""
        return head + chr(10) + fmt(self.balance, self.unit) + tail

    def speak_balance(self):
        fresh = (time.time() - self.last_query) < 60
        self.refresh(force=False)          # 数据旧了就顺手刷一次
        if getattr(self, "_querying", False) and not fresh:
            self.bubble.show("正在查询余额…（网络约需几秒）", False)
        else:
            self.bubble.show(self._bubble_text(), self._warn())
        if self._warn():                   # 告警时抖一下
            self._shake(6)

    def _shake(self, n):
        if n <= 0:
            return
        dx = 4 if n % 2 else -4
        self.win.geometry(f"+{self.win.winfo_x() + dx}+{self.win.winfo_y()}")
        self.win.after(40, lambda: self._shake(n - 1))

    def refresh(self, force=False, quiet=False):
        if not force and (time.time() - self.last_query) < 60:
            return
        if not self.cfg:
            self.balance = None
            return
        tasks = quota.collect(self.cfg, ["deepseek"])
        fn = tasks[0][1] if tasks else None
        if fn is None:
            self.balance = None
            if not quiet:
                self.bubble.show("还没配置 DeepSeek key\n（在挂件 ⚙ 里填，或环境变量）", True)
            return

        def work():
            """后台查询：任何 UI 交互前都必须确认实例还活着（可能在等待期间被销毁）。"""
            alive = lambda: _win_alive(self.win)
            try:
                res = fn() or {}
                if alive():
                    self.win.after(0, self._got, res.get("value"), res.get("unit", ""),
                                   res.get("sub") or "", None)
            except Exception as e:
                if alive():
                    self.win.after(0, self._got, None, "", "", str(e)[:60])

        self._quiet = quiet
        self._querying = True
        threading.Thread(target=work, daemon=True).start()

    def _got(self, value, unit, sub, err):
        if not _win_alive(self.win):
            return                        # 实例已销毁，丢弃迟到的查询结果
        self._querying = False
        self.last_query = time.time()
        if err:
            if not self._quiet:
                self.bubble.show(f"查询失败：{err}", True)
            return
        old = self.balance
        self.balance, self.unit, self.sub = value, unit, sub
        if old is not None and value is not None and abs(value - old) > 1e-9:
            self.bubble.show(self._bubble_text(), self._warn())

    def _auto_tick(self):
        if not _win_alive(self.win):
            return
        if self.auto:
            self.refresh(force=True, quiet=False)
            self._auto_id = self.win.after(AUTO_MS, self._auto_tick)

    def _toggle_auto(self):
        self.auto = not self.auto
        self.menu.entryconfigure(2, label=f"⏱ 自动刷新：{'开' if self.auto else '关'}")
        if self.auto:
            self._auto_id = self.win.after(AUTO_MS, self._auto_tick)

    def _toggle_auto_spawn(self):
        """自动增殖开关（持久化到 ui.json）。调试时建议关闭，免得满屏都是她。"""
        self.auto_spawn = not self.auto_spawn
        ui = _load_ui()
        ui["auto_spawn"] = self.auto_spawn
        _save_ui(ui)
        for q in Pet.pets:
            q.auto_spawn = self.auto_spawn
            try:
                q.menu.entryconfigure(
                    7, label=f"♾ 自动增殖：{'开' if q.auto_spawn else '关'}")
            except Exception:
                pass
        if _win_alive(getattr(self, "bubble", None)):
            self.bubble.show("自动增殖已开启（挂机 90 秒会变多）"
                             if self.auto_spawn else "自动增殖已关闭")

    def _toggle_size(self):
        self.scale = 2 if self.scale == 1 else 1
        self._apply_scale()
        if self.debug_animation_enabled:
            self.face(self.pose)
            self._debug_render_frame()
        else:
            self.face(self.pose)

    def _toggle_top(self):
        self._pinned = not getattr(self, "_pinned", True)
        self.win.attributes("-topmost", self._pinned)


def main():
    root = Pet.root()
    Pet()                      # 本体（增殖体在运行时按需创建）
    root.mainloop()


if __name__ == "__main__":
    main()
