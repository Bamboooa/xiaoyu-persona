#!/usr/bin/env python3
"""小鱼房间 · 第二版

严格一点透视：消失点固定，所有面从门框连到后墙，家具按 z 顺序摆放。
明暗按她的要求：室内一半是暗的，只有窗光（冷）和台灯（暖）。

色号：#46565B 青灰 / #E9A63F 暖黄 / #A9825A 木头 / #E6E4DF 灰白墙
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1600, 1000
VP = (828, 462)                      # 消失点（偏右，因为门从左开）

# 后墙矩形（房间最里面那面，正对门）
BW = (436, 196, 1206, 700)           # x0, y0, x1, y1

TEAL = (70, 86, 91)
WARM = (233, 166, 63)
WOOD = (169, 130, 90)
WALL = (230, 228, 223)

random.seed(7)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def to_black(c, t):
    return mix(c, (9, 14, 16), t)


def vgrad(size, c1, c2, horiz=False):
    w, h = size
    n = w if horiz else h
    strip = Image.new("RGB", (n, 1) if horiz else (1, n))
    d = ImageDraw.Draw(strip)
    for i in range(n):
        d.point((i, 0) if horiz else (0, i), mix(c1, c2, i / max(1, n - 1)))
    return strip.resize((w, h), Image.BILINEAR)


def tgrad(size, colors):
    """多段渐变（上到下）。colors = [(pos, rgb), ...]"""
    w, h = size
    strip = Image.new("RGB", (1, h))
    d = ImageDraw.Draw(strip)
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(colors) - 1):
            p0, c0 = colors[i]
            p1, c1 = colors[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / max(1e-6, p1 - p0)
                d.point((0, y), mix(c0, c1, k))
                break
        else:
            d.point((0, y), colors[-1][1])
    return strip.resize((w, h), Image.BILINEAR)


def glow(W_, H_, color, cx, cy, r, strength=1.0, pw=2):
    img = Image.new("RGB", (W_, H_), (0, 0, 0))
    px = img.load()
    for y in range(0, H_, pw):
        for x in range(0, W_, pw):
            dd = math.hypot(x - cx, y - cy) / r
            if dd >= 1:
                continue
            v = (1 - dd) ** 2.4 * strength
            c = tuple(int(color[i] * v) for i in range(3))
            for dy in range(pw):
                for dx in range(pw):
                    if x + dx < W_ and y + dy < H_:
                        px[x + dx, y + dy] = c
    return img.filter(ImageFilter.GaussianBlur(10))


def render() -> Image.Image:
    img = Image.new("RGB", (W, H), (7, 11, 13))
    d = ImageDraw.Draw(img)

    bx0, by0, bx1, by1 = BW

    # ================= 房间六个面 =================
    # 后墙：窗附近亮，四角暗（窗光衰减很快）
    back = tgrad((bx1 - bx0, by1 - by0), [
        (0.00, to_black(WALL, 0.42)),
        (0.35, to_black(WALL, 0.24)),
        (0.62, to_black(WALL, 0.34)),
        (1.00, to_black(WALL, 0.56)),
    ])
    img.paste(back, (bx0, by0))

    # 左墙：暗，但看得出是墙
    d.polygon([(0, 0), (bx0, by0), (bx0, by1), (0, H)], fill=to_black(TEAL, 0.56))
    # 右墙：更暗
    d.polygon([(W, 0), (bx1, by0), (bx1, by1), (W, H)], fill=to_black(TEAL, 0.66))
    # 天花板
    d.polygon([(0, 0), (W, 0), (bx1, by0), (bx0, by0)], fill=to_black(WALL, 0.7))
    # 地板（木色，靠门更暗）
    fl = tgrad((W, H - by1), [
        (0.00, to_black(WOOD, 0.4)),
        (0.45, to_black(WOOD, 0.54)),
        (1.00, to_black(WOOD, 0.74)),
    ])
    img.paste(fl, (0, by1))
    # 地板只保留梯形区域（两侧墙外的部分要盖掉）
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([(bx0, by1), (bx1, by1), (W, H), (0, H)], fill=255)
    img.paste(to_black(TEAL, 0.82), (0, 0), m.point(lambda v: 255 - v))

    # 墙面交界线（极淡，别像 CAD）
    for a, b in [((bx0, by0), (bx0, by1)), ((bx1, by0), (bx1, by1)),
                 ((bx0, by1), (bx1, by1)), ((bx0, by0), (bx1, by0))]:
        d.line([a, b], fill=to_black(WALL, 0.86), width=1)

    # ================= 大窗 =================
    wx0, wy0, wx1, wy1 = 512, 264, 1136, 610
    # 窗外：阴天，柔、无方向
    sky = tgrad((wx1 - wx0, wy1 - wy0), [
        (0.00, (168, 178, 180)),
        (0.55, (196, 202, 200)),
        (1.00, (176, 184, 183)),
    ])
    img.paste(sky, (wx0, wy0))

    # 窗外远景（糊掉，只留一点形状）
    far = Image.new("RGB", (wx1 - wx0, wy1 - wy0), (150, 160, 160))
    fd = ImageDraw.Draw(far)
    hy = int((wy1 - wy0) * 0.66)
    fd.rectangle([0, hy, wx1 - wx0, wy1 - wy0], fill=(122, 132, 132))
    for _ in range(34):
        xx = random.randint(-30, wx1 - wx0)
        rr = random.randint(10, 40)
        fd.ellipse([xx, hy - rr, xx + rr * 2, hy + rr // 2], fill=(108, 120, 120))
    far = far.filter(ImageFilter.GaussianBlur(9))
    img.paste(Image.blend(img.crop((wx0, wy0, wx1, wy1)), far, 0.6), (wx0, wy0))

    # 玻璃水汽：整体薄雾 + 细流痕（不要做成云）
    fog = Image.new("L", (wx1 - wx0, wy1 - wy0), 0)
    fdr = ImageDraw.Draw(fog)
    fdr.rectangle([0, 0, wx1 - wx0, wy1 - wy0], fill=18)          # 均匀薄雾
    for _ in range(140):                                          # 局部凝结
        xx = random.randint(0, wx1 - wx0)
        yy = random.randint(0, wy1 - wy0)
        rr = random.randint(6, 26)
        fdr.ellipse([xx - rr, yy - rr, xx + rr, yy + rr],
                    fill=random.randint(10, 40))
    fog = fog.filter(ImageFilter.GaussianBlur(7))
    glass = Image.new("RGB", (wx1 - wx0, wy1 - wy0), (214, 218, 216))
    img.paste(Image.composite(glass, img.crop((wx0, wy0, wx1, wy1)), fog), (wx0, wy0))

    # 水珠往下流的痕（细、短、不多）
    d = ImageDraw.Draw(img)
    for _ in range(26):
        xx = random.randint(wx0 + 8, wx1 - 8)
        yy = random.randint(wy0 + 10, wy1 - 80)
        ln = random.randint(18, 90)
        d.line([(xx, yy), (xx + random.randint(-3, 3), yy + ln)],
               fill=mix((214, 218, 216), (168, 176, 176), 0.4), width=1)

    # 窗框（细，白的，不是木的）
    fr = (176, 176, 172)
    d.rectangle([wx0 - 10, wy0 - 10, wx1 + 10, wy1 + 10], outline=fr, width=10)
    d.line([((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1)], fill=fr, width=8)
    d.line([(wx0, wy0 + 172), (wx1, wy0 + 172)], fill=fr, width=6)
    # 窗台（一道厚边，落在后墙上）
    d.rectangle([wx0 - 26, wy1 + 10, wx1 + 26, wy1 + 34], fill=(146, 146, 142))

    # ================= 家具（远 → 近）=================
    # --- 木桌（右侧，靠墙）---
    # 桌面上表面（平行四边形，四点透视）
    t_nl = (1128, 636)   # 后左
    t_nr = (1198, 624)   # 后右
    t_fl = (1016, 706)   # 前左
    t_fr = (1420, 668)   # 前右
    d.polygon([t_nl, t_nr, t_fr, t_fl], fill=to_black(WOOD, 0.44))
    # 桌面厚度（前缘）
    d.polygon([t_fl, t_fr, (t_fr[0], t_fr[1] + 20), (t_fl[0], t_fl[1] + 20)],
              fill=to_black(WOOD, 0.64))
    # 桌腿：只留近处两条（远处被桌面挡住）
    d.line([(1032, 724), (1032, 946)], fill=to_black(WOOD, 0.76), width=15)
    d.line([(1396, 690), (1396, 926)], fill=to_black(WOOD, 0.76), width=16)
    # 划痕（细、乱、不新）
    for _ in range(42):
        x0 = random.randint(1030, 1400)
        y0 = random.randint(650, 690)
        d.line([(x0, y0), (x0 + random.randint(-70, 70), y0 + random.randint(-8, 8))],
               fill=to_black(WOOD, 0.6), width=1)

    # --- 台灯（桌面上，唯一暖光）---
    lx, ly = 1176, 566
    d.line([(lx, ly + 20), (lx, 640)], fill=to_black(WOOD, 0.74), width=5)
    d.ellipse([lx - 30, 628, lx + 30, 648], fill=to_black(WOOD, 0.6))
    d.polygon([(lx - 46, ly + 20), (lx + 46, ly + 20),
               (lx + 30, ly - 18), (lx - 30, ly - 18)],
              fill=to_black((206, 200, 188), 0.34))
    d.ellipse([lx - 26, ly + 12, lx + 26, ly + 26], fill=(248, 232, 196))

    # --- 空杯子（桌角）---
    cxp, cyp = 1318, 686
    d.polygon([(cxp - 15, cyp - 26), (cxp + 15, cyp - 26),
               (cxp + 11, cyp), (cxp - 11, cyp)], fill=to_black((216, 212, 202), 0.36))
    d.ellipse([cxp - 15, cyp - 32, cxp + 15, cyp - 22], fill=to_black((204, 200, 190), 0.3))
    d.arc([cxp + 11, cyp - 24, cxp + 29, cyp - 6], -80, 80,
          fill=to_black((216, 212, 202), 0.42), width=3)

    # --- 大床（左前方，被子没叠）---
    # 床板（长方体）
    b_nl = (452, 612); b_nr = (742, 604)      # 后
    b_fl = (168, 736); b_fr = (716, 700)      # 前
    # 侧面（靠左墙的暗面）
    d.polygon([b_nl, b_fl, (b_fl[0], b_fl[1] + 96), (b_nl[0], b_nl[1] + 74)],
              fill=to_black((176, 170, 158), 0.72))
    # 床垫顶面（被子盖着）
    d.polygon([b_nl, b_nr, b_fr, b_fl], fill=to_black((196, 192, 180), 0.56))
    # 床前脸
    d.polygon([b_fl, b_fr, (b_fr[0], b_fr[1] + 92), (b_fl[0], b_fl[1] + 96)],
              fill=to_black((178, 173, 162), 0.78))

    # 被子：一大块不规则的，堆着、掀开一角
    quilt = [(468, 620), (744, 611), (712, 690),
             (410, 716), (236, 748), (176, 742), (452, 636)]
    d.polygon(quilt, fill=to_black((190, 186, 174), 0.5))
    # 褶皱：少而柔，别像条纹布
    for i in range(4):
        t = (i + 0.5) / 4
        x0 = 470 + (744 - 470) * t
        x1 = 190 + (712 - 190) * t
        wv = math.sin(i * 2.6) * 16
        d.line([(x0 + wv, 626 + 10 * i), (x1 + wv * 1.5, 740)],
               fill=to_black((190, 186, 174), 0.7), width=random.randint(6, 11))
    # 两条亮脊（被子堆起来的地方）
    for i in range(2):
        t = (i + 0.6) / 2
        x0 = 470 + (744 - 470) * t
        x1 = 200 + (712 - 200) * t
        d.line([(x0, 630 + 12 * i), (x1, 738)],
               fill=mix((190, 186, 174), (228, 224, 212), 0.5), width=7)
    # 掀开的一角：露出下面的床单
    d.polygon([(744, 611), (782, 640), (738, 700), (712, 690)],
              fill=to_black((216, 212, 200), 0.4))
    d.line([(744, 611), (738, 700)], fill=to_black((216, 212, 200), 0.62), width=2)

    # 枕头两个，歪着
    for (px, py, pw, ph) in [(456, 600, 150, 42), (612, 596, 142, 40)]:
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=18,
                            fill=to_black((218, 214, 204), 0.44))
        d.line([(px + 10, py + ph - 12), (px + pw - 10, py + ph - 14)],
               fill=to_black((218, 214, 204), 0.66), width=2)

    # ================= 光：只两处 =================
    # 窗光（冷，衰减快）
    img = ImageChops.screen(img, glow(W, H, (108, 126, 128),
                                      (wx0 + wx1) // 2, (wy0 + wy1) // 2, 620, 0.58))
    img = ImageChops.screen(img, glow(W, H, (126, 146, 148),
                                      (wx0 + wx1) // 2, wy1 - 20, 340, 0.4))
    # 台灯（暖，小范围）
    img = ImageChops.screen(img, glow(W, H, WARM, lx, ly + 18, 230, 1.0))
    img = ImageChops.screen(img, glow(W, H, (255, 226, 176), lx, ly + 14, 80, 1.0))

    # ================= 门框（前景，像刚被推开）=================
    d = ImageDraw.Draw(img)
    # 门洞右上角那一条斜的光边（从门框漏进来的天光）
    # 左门框立柱
    d.rectangle([0, 0, 104, H], fill=to_black(TEAL, 0.92))
    # 顶部横框
    d.rectangle([0, 0, W, 74], fill=to_black(TEAL, 0.94))
    # 半开的门板：斜切进画面（左侧）
    d.polygon([(0, 0), (150, 118), (150, 940), (0, H)], fill=to_black(TEAL, 0.97))
    # 门板边缘被窗光照到的一线
    d.line([(150, 118), (150, 940)], fill=mix(TEAL, (188, 196, 194), 0.5), width=3)
    d.line([(150, 118), (W, 74)], fill=mix(TEAL, (188, 196, 194), 0.28), width=2)
    # 右上角也压一点（门框厚度）
    d.polygon([(W, 0), (W, 74), (1502, 74), (1502, 0)], fill=to_black(TEAL, 0.9))

    # ================= 暗角 =================
    vig = Image.new("L", (W, H), 255)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-460, -320, W + 460, H + 420], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(190))
    img = Image.composite(Image.new("RGB", (W, H), (8, 12, 15)), img,
                          vig.point(lambda v: int(v * 0.36)))
    # 近处稍暗（站在门口）
    near_mask = Image.new("L", (W, H), 0)
    nm = ImageDraw.Draw(near_mask)
    nm.rectangle([0, H - 150, W, H], fill=52)
    near_mask = near_mask.filter(ImageFilter.GaussianBlur(80))
    img = Image.composite(Image.new("RGB", (W, H), (10, 14, 17)), img, near_mask)

    return img


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "xiaoyu_room2.png")
    img = render()
    noise = Image.effect_noise((W, H), 6).convert("RGB")
    img = ImageChops.blend(img, ImageChops.add(img, noise, scale=8, offset=-60), 0.22)
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    img.save(out, quality=95)
    print("saved", out, img.size)


if __name__ == "__main__":
    main()
