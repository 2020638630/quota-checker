#!/usr/bin/env python3
"""source/walk_right_f*.png -> pet_assets/side_{r,l}*.png

Pipeline (HANDOFF, adapted for already-sized magenta walk frames):
  - no scale (already 215x264)
  - flood-fill from corners: manhattan dist to #FF00FE < 160 -> KEY
  - force opaque alpha
  - KEEP enclosed KEY gaps (leg/apron) as KEY for colorkey transparency
    (do NOT skin-fill internal holes — that would paint flesh into gait gaps)
  - write side_r*; horizontal flip -> side_l*
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

ROOT = Path(r"D:\quota-checker")
sys.path.insert(0, str(ROOT))
import pngtool  # noqa: E402

SRC = ROOT / "source"
OUT = ROOT / "pet_assets"
KEY = (255, 0, 254)
FLOOD_THRESH = 160
RUNTIME = (215, 264)

SOURCES = [
    ("walk_right_f0.png", "side_r.png", "side_l.png"),
    ("walk_right_f1.png", "side_r_1.png", "side_l_1.png"),
    ("walk_right_f2.png", "side_r_2.png", "side_l_2.png"),
    ("walk_right_f3.png", "side_r_3.png", "side_l_3.png"),
]


def key_dist(r, g, b):
    return abs(r - KEY[0]) + abs(g - KEY[1]) + abs(b - KEY[2])


def flood_fill_key(w, h, rgba, thresh=FLOOD_THRESH):
    visited = bytearray(w * h)
    q = deque()
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        idx = y * w + x
        q.append(idx)
        visited[idx] = 1
    flooded = 0
    while q:
        idx = q.popleft()
        i = idx * 4
        r, g, b = rgba[i], rgba[i + 1], rgba[i + 2]
        if key_dist(r, g, b) >= thresh:
            continue
        if (r, g, b) != KEY:
            rgba[i : i + 3] = bytes(KEY)
            flooded += 1
        rgba[i + 3] = 255
        x, y = idx % w, idx // w
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                nidx = ny * w + nx
                if not visited[nidx]:
                    visited[nidx] = 1
                    q.append(nidx)
    return flooded


def force_opaque(rgba):
    soft = 0
    for i in range(3, len(rgba), 4):
        if rgba[i] != 255:
            soft += 1
            rgba[i] = 255
    return soft


def content_stats(w, h, rgba):
    minx, miny, maxx, maxy = w, h, -1, -1
    exact = 0
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            r, g, b = rgba[i], rgba[i + 1], rgba[i + 2]
            if (r, g, b) == KEY:
                exact += 1
                continue
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y
    cx = (minx + maxx) / 2.0 if maxx >= 0 else None
    return {
        "bbox": (minx, miny, maxx, maxy),
        "foot_y": maxy,
        "center_x": cx,
        "exact_key": exact,
    }


def main():
    reports = []
    for src_name, right_name, left_name in SOURCES:
        src = SRC / src_name
        if not src.is_file():
            raise SystemExit(f"missing source: {src}")
        w, h, rgba = pngtool.decode(src.read_bytes())
        if (w, h) != RUNTIME:
            raise SystemExit(f"{src_name}: expected {RUNTIME}, got {w}x{h}")
        flooded = flood_fill_key(w, h, rgba)
        soft = force_opaque(rgba)
        for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            i = (y * w + x) * 4
            rgba[i : i + 4] = bytes((*KEY, 255))
        stats = content_stats(w, h, rgba)
        right_path = OUT / right_name
        right_path.write_bytes(pngtool.encode(w, h, rgba))
        left_rgba = pngtool.flip_h(w, h, rgba)
        left_path = OUT / left_name
        left_path.write_bytes(pngtool.encode(w, h, left_rgba))
        left_stats = content_stats(w, h, left_rgba)
        rep = {
            "source": src_name,
            "side_r": right_name,
            "side_l": left_name,
            "size": [w, h],
            "flooded": flooded,
            "soft_alpha_forced": soft,
            "side_r_stats": stats,
            "side_l_center_x": left_stats["center_x"],
            "side_r_bytes": right_path.stat().st_size,
            "side_l_bytes": left_path.stat().st_size,
        }
        reports.append(rep)
        print(rep)
    cxs = [r["side_r_stats"]["center_x"] for r in reports]
    foots = [r["side_r_stats"]["foot_y"] for r in reports]
    print("center_x range", max(cxs) - min(cxs), "values", cxs)
    print("foot_y", foots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
