#!/usr/bin/env python3
"""build_sprites.py — 从原始立绘生成桌宠运行时素材（纯标准库）

输入（需自行从上游下载，见 README「素材与授权」）：
  _assets/sprites/{正面,侧面,背面}_187.png     鲸鱼娘·大肥鱼 三视图（1190fasheqi/dafeiyu-pet, MIT）
输出（桌宠运行时读取）：
  pet_assets/front.png    正面
  pet_assets/side_r.png   侧面（朝右）
  pet_assets/side_l.png   侧面镜像（朝左）
  pet_assets/back.png     背面

为什么要处理：Windows 的 tkinter 只能用色键（-transparentcolor）做透明，
软边 alpha 会在色键边缘渗出粉边，所以必须把 alpha 二值化成硬边。

用法：python pet_assets/build_sprites.py
键盘和手不在这里生成，见 pet_assets/make_keyboard.py（程序自绘，无外部依赖）。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import pngtool  # noqa: E402

SRC = os.path.join(ROOT, "_assets", "sprites")
# (源文件名, 输出名, 是否需要水平镜像)
JOBS = [("正面_187.png", "front", False),
        ("侧面_187.png", "side_r", False),
        ("侧面_187.png", "side_l", True),
        ("背面_187.png", "back", False)]
ALPHA_THRESHOLD = 128


def build():
    missing = [j for j in JOBS if not os.path.exists(os.path.join(SRC, j[0]))]
    if missing:
        print("缺少原始素材，请先下载到 _assets/sprites/：")
        for name, _, _ in missing:
            print(f"  {name}")
        print("来源见 README 的「素材与授权」一节。")
        return 1
    for src_name, out_name, mirror in JOBS:
        w, h, rgba = pngtool.decode(open(os.path.join(SRC, src_name), "rb").read())
        if mirror:
            rgba = pngtool.flip_h(w, h, rgba)
        soft = 0
        for i in range(3, len(rgba), 4):
            a = rgba[i]
            if a not in (0, 255):
                soft += 1
            rgba[i] = 255 if a >= ALPHA_THRESHOLD else 0
        out = os.path.join(HERE, f"{out_name}.png")
        open(out, "wb").write(pngtool.encode(w, h, rgba))
        print(f"{out_name}.png  {w}x{h}  二值化 {soft} 个软边像素 -> {os.path.getsize(out)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
