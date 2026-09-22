#!/usr/bin/env python3
"""pngtool.py — 极简 PNG 解码/编码/水平翻转（纯标准库）

用于处理桌宠素材：读取 RGBA、统计 alpha 分布（判断色键透明的可行性）、
生成左右镜像版本（tkinter 没有翻转能力，只能预处理）。
支持非交错 8bit 的灰度/RGB/调色板/灰度+alpha/RGBA。
"""

import struct
import zlib

_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def decode(data):
    """返回 (w, h, rgba_bytearray)。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos = 8
    w = h = bitdepth = colortype = None
    idat = b""
    palette = b""
    trns = b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            w, h, bitdepth, colortype, comp, filt, inter = struct.unpack(">IIBBBBB", body)
            if inter:
                raise ValueError("interlaced png not supported")
            if bitdepth != 8:
                raise ValueError(f"bitdepth {bitdepth} not supported")
        elif tag == b"PLTE":
            palette = body
        elif tag == b"tRNS":
            trns = body
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    raw = zlib.decompress(idat)
    ch = _CHANNELS[colortype]
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line

    rgba = bytearray(w * h * 4)
    if colortype == 6:
        rgba[:] = out
    elif colortype == 2:
        for i in range(w * h):
            rgba[i * 4:i * 4 + 3] = out[i * 3:i * 3 + 3]
            rgba[i * 4 + 3] = 255
    elif colortype == 0:
        for i in range(w * h):
            v = out[i]
            rgba[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
    elif colortype == 4:
        for i in range(w * h):
            v, a = out[i * 2], out[i * 2 + 1]
            rgba[i * 4:i * 4 + 4] = bytes((v, v, v, a))
    elif colortype == 3:
        for i in range(w * h):
            idx = out[i]
            r, g, b = palette[idx * 3:idx * 3 + 3]
            a = trns[idx] if idx < len(trns) else 255
            rgba[i * 4:i * 4 + 4] = bytes((r, g, b, a))
    else:
        raise ValueError(f"colortype {colortype} not supported")
    return w, h, rgba


def encode(w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def flip_h(w, h, rgba):
    out = bytearray(len(rgba))
    for y in range(h):
        row = rgba[y * w * 4:(y + 1) * w * 4]
        for x in range(w):
            sx = (w - 1 - x) * 4
            out[(y * w + x) * 4:(y * w + x) * 4 + 4] = row[sx:sx + 4]
    return out


def alpha_stats(rgba):
    n = len(rgba) // 4
    hard0 = hard255 = soft = 0
    for i in range(3, len(rgba), 4):
        a = rgba[i]
        if a == 0:
            hard0 += 1
        elif a == 255:
            hard255 += 1
        else:
            soft += 1
    return {"total": n, "fully_transparent": hard0, "opaque": hard255,
            "semi": soft, "semi_pct": round(soft * 100.0 / max(n, 1), 2)}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "_assets/sprites/正面.png"
    w, h, rgba = decode(open(path, "rb").read())
    print(f"{path}: {w}x{h}", alpha_stats(rgba))