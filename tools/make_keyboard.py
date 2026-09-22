#!/usr/bin/env python3
"""make_keyboard.py — 键盘与手臂素材生成（纯标准库，风格对齐鲸鱼娘立绘）

输出到 pet_assets/：
  keyboard.png        深蓝键盘（4 排键帽 + 空格）
  keys_map.json       每个键帽的矩形/中心坐标 + 虚拟键码（供精确点亮与手位分组）
  arm_l.png/arm_r.png 手臂（从裙侧伸向键盘，带袖口）

色键透明下不能出现近白像素（会被 #00fe 色键吞掉），因此一律用深蓝/亮蓝系。
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mascot   # noqa: E402
import pngtool  # noqa: E402

SHELL = (34, 45, 84)
EDGE = (92, 112, 176)
CAP = (62, 82, 144)
CAP_TOP = (86, 108, 176)
LIT = (150, 200, 255)
SLEEVE = (40, 54, 102)
SLEEVE_EDGE = (86, 108, 172)
CUFF = (222, 222, 220)

KB_W, KB_H = 150, 58
ROWS = [
    (2.0, [1] * 13 + [1.8]),
    (2.6, [1.5] + [1] * 11 + [1.7]),
    (3.4, [1.8] + [1] * 10 + [2.0]),
    (4.6, [1.3, 1.3] + [6.6] + [1.3, 1.3]),
]
VK_ROWS = [
    [0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0xBD, 0xBB, 0xDC, 0x08],
    [0x09, 0x51, 0x57, 0x45, 0x52, 0x54, 0x59, 0x55, 0x49, 0x4F, 0x50, 0xDB, 0xDD, 0x0D],
    [0x14, 0x41, 0x53, 0x44, 0x46, 0x47, 0x48, 0x4A, 0x4B, 0x4C, 0xBA, 0xDE, 0x10],
    [0x11, 0x12, 0x20, 0x11, 0x12],
]
UNIT, GAP, KEY_H, PAD_X, PAD_Y, ROW_GAP = 9.6, 1.8, 9.0, 8.0, 7.0, 2.0


def key_rects():
    out = []
    for r, (indent, widths) in enumerate(ROWS):
        x = PAD_X + indent
        y = PAD_Y + r * (KEY_H + ROW_GAP)
        vks = VK_ROWS[r] if r < len(VK_ROWS) else []
        for i, wu in enumerate(widths):
            w = wu * UNIT - GAP
            x0, x1 = x, x + w
            out.append({"rect": [round(x0, 2), round(y, 2), round(x1, 2), round(y + KEY_H, 2)],
                        "center": [round((x0 + x1) / 2, 1), round(y + KEY_H / 2, 1)],
                        "vk": vks[i] if i < len(vks) else None})
            x += wu * UNIT
    return out


def draw_board(lit_vks=None, keys=None):
    keys = keys if keys is not None else key_rects()
    c = mascot.Canvas(KB_W, KB_H)
    c.rrect(1, 1, KB_W - 1, KB_H - 1, 8, EDGE)
    c.rrect(3, 3, KB_W - 3, KB_H - 3, 7, SHELL)
    lit = set(lit_vks or ())
    for k in keys:
        x0, y0, x1, y1 = k["rect"]
        on = k["vk"] in lit
        c.rrect(x0, y0, x1, y1, 2.0, LIT if on else CAP)
        if not on:
            c.rrect(x0, y0, x1, y0 + 2.0, 1.0, CAP_TOP)
    return c


def draw_arm(side):
    """手臂：从身体一侧斜伸到键盘，末端带袖口。"""
    w, h = 44, 28
    c = mascot.Canvas(w, h)
    if side == "l":   # 左臂：从左上伸向右下
        body = [(1, 3), (14, 2), (31, 11), (42, 18), (31, 26), (14, 23), (1, 19)]
        cuff = (28, 9, 41, 25)
    else:             # 右臂：镜像
        body = [(43, 3), (30, 2), (13, 11), (2, 18), (13, 26), (30, 23), (43, 19)]
        cuff = (3, 9, 16, 25)
    c.poly(body, SLEEVE)
    c.poly([(p[0], p[1] + 0.001) for p in body], SLEEVE_EDGE, 0.06)
    c.rrect(*cuff, 4, CUFF)
    return c.raster()


if __name__ == "__main__":
    keys = key_rects()
    open(os.path.join(HERE, "keyboard.png"), "wb").write(
        pngtool.encode(KB_W, KB_H, draw_board(keys=keys).raster()))
    json.dump(keys, open(os.path.join(HERE, "keys_map.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for side in ("l", "r"):
        open(os.path.join(HERE, f"arm_{side}.png"), "wb").write(
            pngtool.encode(44, 28, draw_arm(side)))
    for old in ("keys_l.png", "keys_r.png"):
        p = os.path.join(HERE, old)
        if os.path.exists(p):
            os.remove(p)
    print(f"keyboard.png {KB_W}x{KB_H}")
    print(f"keys_map.json: {len(keys)} 键帽，{sum(1 for k in keys if k['vk'])} 个已映射键码")
    print("arm_l.png / arm_r.png 44x28；已移除旧 keys_l/keys_r")
