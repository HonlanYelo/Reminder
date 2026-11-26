# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico（纯标准库，4x 超采样抗锯齿）"""
import os
import struct
import zlib
import math


def dist_seg(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / L2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def in_rounded(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return math.hypot(x - cx, y - cy) <= r


def lerp(a, b, t):
    return a + (b - a) * t


def render(size, ss=4):
    W = size
    px = []
    n = W * W
    for j in range(W):
        for i in range(W):
            acc_r = acc_g = acc_b = acc_a = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    x = i + (sx + 0.5) / ss
                    y = j + (sy + 0.5) / ss
                    u = x / W
                    v = y / W
                    # 背景圆角矩形
                    if in_rounded(x, y, 0.5, 0.5, W - 0.5, W - 0.5, 0.235 * W):
                        # 渐变
                        t = (u * 0.45 + v * 0.55)
                        r0, g0, b0 = 0x5E, 0x8DFF >> 8, 0xFF
                        r0, g0, b0 = 0x62, 0x8f, 0xff
                        r1, g1, b1 = 0x35, 0x5c, 0xd6
                        cr = lerp(r0, r1, t)
                        cg = lerp(g0, g1, t)
                        cb = lerp(b0, b1, t)
                        # 勾
                        d1 = dist_seg(u, v, 0.285, 0.520, 0.435, 0.675)
                        d2 = dist_seg(u, v, 0.435, 0.675, 0.735, 0.345)
                        d = min(d1, d2)
                        w = 0.052
                        if d <= w:
                            cr = cg = cb = 0xFF
                        elif d <= w + 0.012:
                            k = (d - w) / 0.012
                            cr = lerp(255, cr, k)
                            cg = lerp(255, cg, k)
                            cb = lerp(255, cb, k)
                        acc_r += cr
                        acc_g += cg
                        acc_b += cb
                        acc_a += 255
            cnt = float(ss * ss)
            a = acc_a / cnt
            if a > 0:
                px.append((int(acc_r / cnt), int(acc_g / cnt), int(acc_b / cnt), int(a)))
            else:
                px.append((0, 0, 0, 0))
    return px


def png_bytes(w, h, pixels):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b, a = pixels[y * w + x]
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def build(path):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = []
    for s in sizes:
        ss = 4 if s <= 64 else 2
        imgs.append((s, png_bytes(s, s, render(s, ss))))
        print("  rendered %d" % s)
    n = len(imgs)
    out = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    entries = b""
    datas = b""
    for s, png in imgs:
        w = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        datas += png
    with open(path, "wb") as f:
        f.write(out + entries + datas)
    print("saved", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    build(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"))
