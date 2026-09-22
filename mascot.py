#!/usr/bin/env python3
"""mascot.py — 纯标准库自绘的 BongoCat 风格猫咪动画帧（零依赖、无外部素材）

用 3x 超采样光栅化 + 手写 PNG 编码，输出带 alpha 的白猫动画帧，
供挂件做会动的小吉祥物：
  idle / blink / tap_l / tap_r / worried / panic / happy
每个状态是一组 PNG 帧（base64），tkinter 用 PhotoImage(data=...) 直接加载。

预览：python mascot.py   → 生成 mascot_preview.png（深色+透明两种底）
"""

import base64
import struct
import sys
import zlib

SS = 3  # 超采样倍数（抗锯齿）

WHITE = (255, 255, 255)
INK = (58, 58, 60)
PINK = (255, 170, 190)
BLUSH = (255, 150, 175, 140)
SWEAT = (126, 200, 255)
RED = (255, 69, 58)


# ---------------------------------------------------------------- PNG 编码
def png_bytes(w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


class Canvas:
    """预乘 alpha 的浮点画布，超采样后降采样输出。"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.W, self.H = w * SS, h * SS
        self.buf = [0.0] * (self.W * self.H * 4)

    def _blend(self, x, y, color, alpha=1.0):
        if not (0 <= x < self.W and 0 <= y < self.H):
            return
        r, g, b = color[:3]
        a = (color[3] / 255.0 if len(color) > 3 else 1.0) * alpha
        if a <= 0:
            return
        i = (y * self.W + x) * 4
        buf = self.buf
        na = a + buf[i + 3] * (1 - a)
        if na <= 0:
            return
        buf[i] = (r * a + buf[i] * buf[i + 3] * (1 - a)) / na
        buf[i + 1] = (g * a + buf[i + 1] * buf[i + 3] * (1 - a)) / na
        buf[i + 2] = (b * a + buf[i + 2] * buf[i + 3] * (1 - a)) / na
        buf[i + 3] = na

    # ---- 图元（坐标单位：目标像素） ----
    def ellipse(self, cx, cy, rx, ry, color, alpha=1.0):
        x0, x1 = int((cx - rx) * SS) - 1, int((cx + rx) * SS) + 1
        y0, y1 = int((cy - ry) * SS) - 1, int((cy + ry) * SS) + 1
        cx, cy, rx, ry = cx * SS, cy * SS, max(rx * SS, 0.01), max(ry * SS, 0.01)
        for y in range(max(y0, 0), min(y1, self.H - 1) + 1):
            dy = (y + 0.5 - cy) / ry
            if abs(dy) > 1:
                continue
            half = rx * (1 - dy * dy) ** 0.5
            for x in range(max(int(cx - half), 0), min(int(cx + half) + 1, self.W)):
                if abs(x + 0.5 - cx) <= half:
                    self._blend(x, y, color, alpha)

    def rrect(self, x0, y0, x1, y1, r, color, alpha=1.0):
        self.ellipse(x0 + r, y0 + r, r, r, color, alpha)
        self.ellipse(x1 - r, y0 + r, r, r, color, alpha)
        self.ellipse(x0 + r, y1 - r, r, r, color, alpha)
        self.ellipse(x1 - r, y1 - r, r, r, color, alpha)
        for y in range(int(y0 * SS), int(y1 * SS)):
            self._hline(y, x0 + r, x1 - r, color, alpha)
        for x in range(int(x0 * SS), int(x1 * SS)):
            self._vline(x, y0 + r, y1 - r, color, alpha)

    def _hline(self, y, xa, xb, color, alpha):
        if not (0 <= y < self.H):
            return
        for x in range(max(int(xa * SS), 0), min(int(xb * SS), self.W - 1) + 1):
            self._blend(x, y, color, alpha)

    def _vline(self, x, ya, yb, color, alpha):
        if not (0 <= x < self.W):
            return
        for y in range(max(int(ya * SS), 0), min(int(yb * SS), self.H - 1) + 1):
            self._blend(x, y, color, alpha)

    def poly(self, pts, color, alpha=1.0):
        """扫描线填充（偶奇规则），pts 为目标像素坐标。"""
        p = [(x * SS, y * SS) for x, y in pts]
        ys = [int(y) for _, y in p]
        for y in range(max(min(ys), 0), min(max(ys), self.H - 1) + 1):
            xs = []
            n = len(p)
            for i in range(n):
                x1, y1 = p[i]
                x2, y2 = p[(i + 1) % n]
                if (y1 <= y < y2) or (y2 <= y < y1):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(int(xs[i]), min(int(xs[i + 1]) + 1, self.W)):
                    if x >= 0:
                        self._blend(x, y, color, alpha)

    # ---- 输出：降采样到目标尺寸的 RGBA 字节 ----
    def raster(self):
        out = bytearray(self.w * self.h * 4)
        n = SS * SS
        for y in range(self.h):
            for x in range(self.w):
                r = g = b = a = 0.0
                for sy in range(SS):
                    base = ((y * SS + sy) * self.W + x * SS) * 4
                    for sx in range(SS):
                        i = base + sx * 4
                        pa = self.buf[i + 3]
                        r += self.buf[i] * pa
                        g += self.buf[i + 1] * pa
                        b += self.buf[i + 2] * pa
                        a += pa
                i = (y * self.w + x) * 4
                if a > 0:
                    out[i] = min(255, int(r / a + 0.5))
                    out[i + 1] = min(255, int(g / a + 0.5))
                    out[i + 2] = min(255, int(b / a + 0.5))
                    out[i + 3] = min(255, int(a / n * 255 + 0.5))
        return out


# ---------------------------------------------------------------- 画猫
def draw_cat(w=44, h=40, ear=0.0, eye="open", paw_l=0.0, paw_r=0.0,
             mouth="smile", blush=1.0, extra=None, tilt=0.0):
    """ear: 0=竖起 1=耷拉；paw_*: 0=放下 1=抬起；extra: None/'sweat'/'alert'/'star'"""
    c = Canvas(w, h)
    cx = w / 2
    hy = h * 0.42
    rxy = (14.0, 12.0)

    # 耳朵（三角形，ear 越大越向外下耷拉）
    for sgn in (-1, 1):
        bx = cx + sgn * 8.5
        tipx = cx + sgn * (11.5 + 5.5 * ear)
        tipy = hy - rxy[1] * (1.02 - 0.75 * ear)
        c.poly([(bx - sgn * 4.2, hy - rxy[1] * 0.55), (tipx, tipy),
                (bx + sgn * 4.0, hy - rxy[1] * 0.15)], WHITE)
        c.poly([(bx - sgn * 1.6, hy - rxy[1] * 0.5), (tipx - sgn * 1.2, tipy + 2.2),
                (bx + sgn * 2.0, hy - rxy[1] * 0.2)], PINK)

    # 头
    c.ellipse(cx, hy, rxy[0], rxy[1], WHITE)
    # 腮红
    if blush > 0:
        c.ellipse(cx - 8.6, hy + 3.4, 2.4, 1.7, BLUSH, blush)
        c.ellipse(cx + 8.6, hy + 3.4, 2.4, 1.7, BLUSH, blush)

    # 眼睛
    ey = hy - 1.0
    for sgn in (-1, 1):
        ex = cx + sgn * 5.4
        if eye == "open":
            c.ellipse(ex, ey, 1.7, 2.0, INK)
            c.ellipse(ex - sgn * 0.5, ey - 0.7, 0.5, 0.6, WHITE)
        elif eye == "blink":
            c.rrect(ex - 1.8, ey - 0.35, ex + 1.8, ey + 0.35, 0.35, INK)
        elif eye == "half":
            c.rrect(ex - 1.8, ey - 0.8, ex + 1.8, ey + 0.1, 0.45, INK)
        elif eye == "wide":
            c.ellipse(ex, ey, 2.6, 2.9, WHITE)
            c.ellipse(ex, ey + 0.4, 1.5, 1.7, INK)
            c.ellipse(ex - sgn * 0.5, ey - 0.4, 0.5, 0.6, WHITE)
        elif eye == "sad":
            c.ellipse(ex, ey + 0.3, 1.5, 1.7, INK)
            c.rrect(ex - 2.0, ey - 2.0, ex + 2.0, ey - 1.2, 0.4, INK)  # 眉毛压眼
        elif eye == "x":
            c.rrect(ex - 1.8, ey - 0.4, ex + 1.8, ey + 0.4, 0.4, INK)
            c.poly([(ex - 1.8, ey - 1.6), (ex - 0.6, ey - 1.6),
                    (ex + 1.8, ey + 1.6), (ex + 0.6, ey + 1.6)], INK)
            c.poly([(ex - 1.8, ey + 1.6), (ex - 0.6, ey + 1.6),
                    (ex + 1.8, ey - 1.6), (ex + 0.6, ey - 1.6)], INK)

    # 嘴（ω / 波浪）
    my = hy + 3.6
    if mouth == "smile":
        for sgn in (-1, 1):
            c.rrect(cx + sgn * 0.2, my - 0.35, cx + sgn * 2.4, my + 0.35, 0.3, INK)
    elif mouth == "flat":
        c.rrect(cx - 2.2, my - 0.3, cx + 2.2, my + 0.3, 0.3, INK)
    elif mouth == "frown":
        c.rrect(cx - 2.2, my + 0.4, cx + 2.2, my + 1.0, 0.3, INK)
        c.rrect(cx - 2.6, my + 0.4, cx - 1.8, my + 1.4, 0.35, INK)

    # 爪子（敲桌子）
    py = h * 0.80
    c.ellipse(cx - 6.0, py - 4.2 * paw_l, 4.6, 3.4, WHITE)
    c.ellipse(cx + 6.0, py - 4.2 * paw_r, 4.6, 3.4, WHITE)
    c.ellipse(cx - 6.0, py - 3.0 - 4.2 * paw_l, 1.1, 0.8, PINK)
    c.ellipse(cx + 6.0, py - 3.0 - 4.2 * paw_r, 1.1, 0.8, PINK)

    # 附加表情符号
    if extra == "sweat":
        c.ellipse(cx + 12.5, hy - 6.0, 1.9, 2.6, SWEAT)
        c.poly([(cx + 11.2, hy - 5.4), (cx + 13.8, hy - 5.4), (cx + 12.5, hy - 8.6)], SWEAT)
    elif extra == "alert":
        c.rrect(cx + 13.0, hy - 8.5, cx + 14.8, hy - 3.0, 0.7, RED)
        c.ellipse(cx + 13.9, hy - 1.4, 1.0, 1.0, RED)
    elif extra == "star":
        for ex, ey2, r in ((cx - 13.5, hy - 8.5, 1.7), (cx + 13.5, hy - 8.5, 1.7)):
            c.poly([(ex, ey2 - r), (ex + r * 0.35, ey2 - r * 0.35), (ex + r, ey2),
                    (ex + r * 0.35, ey2 + r * 0.35), (ex, ey2 + r),
                    (ex - r * 0.35, ey2 + r * 0.35), (ex - r, ey2),
                    (ex - r * 0.35, ey2 - r * 0.35)], (255, 214, 102))
    return c.raster()


# ---------------------------------------------------------------- 状态帧表
def build_frames(w=44, h=40):
    """返回 {state: [png_bytes, ...]}"""
    seq = {
        "idle": [dict(), dict(), dict(eye="blink"), dict()],
        "tap": [dict(paw_l=1.0, paw_r=0.15, mouth="flat"),
                dict(paw_l=0.15, paw_r=1.0, mouth="flat")],
        "happy": [dict(extra="star"), dict(extra="star", eye="blink")],
        "worried": [dict(ear=0.85, eye="half", mouth="frown", extra="sweat", blush=0.7),
                    dict(ear=0.85, eye="sad", mouth="frown", extra="sweat", blush=0.7)],
        "panic": [dict(ear=1.0, eye="wide", mouth="frown", extra="alert"),
                  dict(ear=1.0, eye="x", mouth="frown", extra="alert")],
    }
    return {k: [png_bytes(w, h, draw_cat(w, h, **kw)) for kw in v] for k, v in seq.items()}


_B64_CACHE = {}


def frames_b64(w=44, h=40):
    """供 tkinter PhotoImage(data=...) 使用的 base64 帧表（带缓存）。"""
    key = (w, h)
    if key not in _B64_CACHE:
        _B64_CACHE[key] = {k: [base64.b64encode(f).decode("ascii") for f in v]
                           for k, v in build_frames(w, h).items()}
    return _B64_CACHE[key]


# ---------------------------------------------------------------- 预览
def render_preview(path="mascot_preview.png", zoom=4, w=44, h=40):
    """把各状态帧平铺成一张预览图（深色底），便于人工检查造型。"""
    states = build_frames(w, h)
    order = ["idle", "tap", "happy", "worried", "panic"]
    cols = max(len(v) for v in states.values()) + 1
    rows = len(order)
    cw, chh = w + 6, h + 6
    W, H = cols * cw, rows * chh
    # 像素层面拼接：先铺深色卡片底，再贴帧
    px = bytearray()
    for y in range(H):
        px += bytes((27, 28, 31, 255)) * W
    for r, name in enumerate(order):
        for cidx, fr in enumerate(states[name]):
            raw = _decode_png(fr, w, h)
            ox, oy = cidx * cw + 3, r * chh + 3
            for y in range(h):
                for x in range(w):
                    i = (y * w + x) * 4
                    a = raw[i + 3] / 255.0
                    if a <= 0:
                        continue
                    j = ((oy + y) * W + ox + x) * 4
                    for k in range(3):
                        px[j + k] = int(raw[i + k] * a + px[j + k] * (1 - a))
    # 放大 zoom 倍输出
    out = bytearray()
    for y in range(H):
        row = b""
        for x in range(W):
            row += bytes(px[(y * W + x) * 4:(y * W + x) * 4 + 4]) * zoom
        out += row * zoom
    with open(path, "wb") as f:
        f.write(png_bytes(W * zoom, H * zoom, out))
    return path


def _decode_png(data, w, h):
    """解析我们自己生成的 PNG（无滤波器、RGBA8888）。"""
    pos, out = 8, bytearray()
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if tag == b"IDAT":
            out += zlib.decompress(body)
        pos += 12 + ln
    # 去掉每行滤波器字节
    px = bytearray()
    stride = w * 4
    for y in range(h):
        px += out[y * (stride + 1) + 1: y * (stride + 1) + 1 + stride]
    return px


if __name__ == "__main__":
    p = render_preview()
    print("preview written:", p)