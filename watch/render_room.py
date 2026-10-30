#!/usr/bin/env python3
"""按小鱼的交底单渲染她的房间。

视角：从门里往里看，门框在画面边上，像刚被推开。
光：只有两处 —— 窗外阴天天光（冷、无方向），桌上一盏台灯（暖、不亮）。
室内一半是暗的。

色号（她自己定的）：
  青灰 #46565B / 暖黄 #E9A63F / 木头 #A9825A / 灰白墙 #E6E4DF
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 1000

# —— 她定的四种色 ——
TEAL = (70, 86, 91)        # #46565B 青灰
WARM = (233, 166, 63)      # #E9A63F 暖黄
WOOD = (169, 130, 90)      # #A9825A 木头
WALL = (230, 228, 223)     # #E6E4DF 灰白墙

random.seed(20261030)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def darker(c, t):
    """往青灰的暗里压。t=0 原色，t=1 全暗。"""
    return mix(c, (18, 26, 29), t)


def lin_grad(size, c1, c2, horizontal=False):
    """线性渐变图层。"""
    w, h = size
    img = Image.new("RGB", (1, h) if not horizontal else (w, 1))
    d = ImageDraw.Draw(img)
    n = h if not horizontal else w
    for i in range(n):
        d.point((0, i) if not horizontal else (i, 0), mix(c1, c2, i / max(1, n - 1)))
    return img.resize((w, h), Image.BILINEAR)


def radial(size, color, cx, cy, r, strength=1.0):
    """径向光晕（黑底，用于 screen 叠加）。"""
    w, h = size
    img = Image.new("RGB", (w, h), (0, 0, 0))
    px = img.load()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            dd = math.hypot(x - cx, y - cy) / r
            if dd >= 1:
                continue
            v = (1 - dd) ** 2.2 * strength
            c = tuple(int(color[i] * v) for i in range(3))
            px[x, y] = c
            if x + 1 < w:
                px[x + 1, y] = c
            if y + 1 < h:
                px[x, y + 1] = c
                if x + 1 < w:
                    px[x + 1, y + 1] = c
    return img.filter(ImageFilter.GaussianBlur(9))


def screen(base: Image.Image, add: Image.Image) -> Image.Image:
    """滤色叠加（光）。"""
    from PIL import ImageChops
    return ImageChops.screen(base, add)


def draw_room() -> Image.Image:
    img = Image.new("RGB", (W, H), (12, 18, 20))
    d = ImageDraw.Draw(img)

    # ---------- 透视骨架 ----------
    # 后墙（正对门）
    bx0, by0, bx1, by1 = 405, 168, 1258, 812          # 后墙矩形
    # 地板前沿（画面底部略内收）
    fx0, fy0, fx1, fy1 = 96, 1000, 1560, 1000
    # 天花板前沿
    cx0, cy0, cx1, cy1 = 150, 0, 1502, 0

    # 后墙：灰白墙，但一半在暗里
    wall = lin_grad((bx1 - bx0, by1 - by0), mix(WALL, TEAL, 0.25), darker(WALL, 0.72))
    img.paste(wall, (bx0, by0))

    # 天花板（越靠门越暗）
    d.polygon([(cx0, cy0), (cx1, cy1), (bx1, by0), (bx0, by0)],
              fill=darker(mix(WALL, TEAL, 0.4), 0.78))
    # 地板（木色，靠门更暗）
    floor = lin_grad((W, H - by1 + 40), darker(WOOD, 0.55), darker(WOOD, 0.86))
    img.paste(floor.crop((0, 0, W, H - by1)), (0, by1))
    d.polygon([(bx0, by1), (bx1, by1), (fx1, fy1), (fx0, fy0)],
              fill=None, outline=None)

    # 左右墙（暗，几乎只剩剪影）
    d.polygon([(0, 0), (bx0, by0), (bx0, by1), (0, H)], fill=darker(TEAL, 0.62))
    d.polygon([(W, 0), (bx1, by0), (bx1, by1), (W, H)], fill=darker(TEAL, 0.7))

    # ---------- 大窗（不要窗帘，玻璃有水汽）----------
    wx0, wy0, wx1, wy1 = 505, 246, 1158, 638
    # 窗外的天：阴天，灰白偏冷，柔和不带方向
    sky = lin_grad((wx1 - wx0, wy1 - wy0), (176, 186, 188), (206, 210, 208))
    img.paste(sky, (wx0, wy0))
    # 远处一点模糊的地平线/树影，别太清楚
    hor = Image.new("RGB", (wx1 - wx0, wy1 - wy0), (0, 0, 0))
    hd = ImageDraw.Draw(hor)
    hy = int((wy1 - wy0) * 0.72)
    hd.rectangle([0, hy, wx1 - wx0, wy1 - wy0], fill=(126, 138, 138))
    for i in range(26):
        xx = random.randint(-20, wx1 - wx0)
        rr = random.randint(14, 46)
        hd.ellipse([xx, hy - rr, xx + rr * 2, hy + rr], fill=(104, 118, 118))
    hor = hor.filter(ImageFilter.GaussianBlur(7))
    img.paste(Image.blend(img.crop((wx0, wy0, wx1, wy1)), hor, 0.55), (wx0, wy0))

    # 玻璃水汽：一层很淡的雾 + 几道流痕
    fog = Image.new("L", (wx1 - wx0, wy1 - wy0), 0)
    fd = ImageDraw.Draw(fog)
    for i in range(70):
        xx = random.randint(0, wx1 - wx0)
        yy = random.randint(0, wy1 - wy0)
        rr = random.randint(22, 90)
        fd.ellipse([xx - rr, yy - rr, xx + rr, yy + rr], fill=random.randint(8, 26))
    for i in range(9):
        xx = random.randint(10, wx1 - wx0 - 10)
        fd.line([(xx, random.randint(0, 40)), (xx + random.randint(-8, 8), wy1 - wy0)],
                fill=random.randint(14, 30), width=random.randint(2, 5))
    fog = fog.filter(ImageFilter.GaussianBlur(11))
    glass = Image.new("RGB", (wx1 - wx0, wy1 - wy0), (222, 226, 224))
    img.paste(Image.composite(glass, img.crop((wx0, wy0, wx1, wy1)), fog), (wx0, wy0))

    # 窗框：细，窗台一道厚
    d.rectangle([wx0 - 9, wy0 - 9, wx1 + 9, wy1 + 9], outline=darker(WALL, 0.35), width=9)
    d.line([((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1)],
           fill=darker(WALL, 0.3), width=7)                       # 中竖梃
    d.line([(wx0, wy0 + 168), (wx1, wy0 + 168)], fill=darker(WALL, 0.3), width=6)
    d.rectangle([wx0 - 22, wy1 + 8, wx1 + 22, wy1 + 30], fill=darker(WALL, 0.5))

    # ---------- 窗光：把后墙和地板打亮一点（冷、无方向）----------
    glow = radial((W, H), (150, 170, 172), (wx0 + wx1) // 2, wy1 - 40, 620, 0.55)
    img = screen(img, glow)
    d = ImageDraw.Draw(img)

    # ---------- 大床（前景左，被子没叠）----------
    bed_pts = [(78, 618), (742, 596), (860, 1000), (18, 1000)]
    d.polygon(bed_pts, fill=darker((196, 190, 178), 0.5))
    # 床垫厚度
    d.polygon([(78, 618), (742, 596), (742, 646), (78, 672)], fill=darker((170, 165, 154), 0.62))
    # 被子：一大块，皱的
    quilt = [(60, 660), (738, 636), (838, 1000), (30, 1000)]
    d.polygon(quilt, fill=darker((188, 184, 172), 0.62))
    # 被子的褶皱：几条顺势的暗线 + 亮面
    for i in range(9):
        t = i / 8
        x0 = 60 + (738 - 60) * t
        x1 = 30 + (838 - 30) * t
        wav = math.sin(i * 1.7) * 26
        d.line([(x0 + wav, 660 + 6 * i), (x1 + wav * 1.6, 1000)],
               fill=darker((188, 184, 172), 0.78), width=random.randint(3, 7))
    # 掀开的一角：露出的床单
    d.polygon([(560, 648), (742, 636), (700, 760), (556, 742)],
              fill=darker((214, 209, 198), 0.45))
    d.line([(560, 648), (700, 760)], fill=darker((214, 209, 198), 0.7), width=3)
    # 枕头（两个，歪的）
    for (px, py, pw, ph, ang) in [(150, 606, 210, 66, 0), (386, 600, 200, 62, 0)]:
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=26,
                            fill=darker((216, 212, 202), 0.52 - ang))
        d.line([(px + 14, py + ph - 16), (px + pw - 14, py + ph - 20)],
               fill=darker((216, 212, 202), 0.72), width=2)

    # ---------- 木桌（右侧，桌面有划痕，不新）----------
    tx0, ty0, tx1, ty1 = 962, 700, 1432, 792                 # 桌面前沿
    d.polygon([(1004, 660), (1398, 626), (tx1, ty1), (tx0, ty0)],
              fill=darker(WOOD, 0.34))                        # 桌面
    d.polygon([(1004, 660), (1398, 626), (1398, 648), (1004, 682)],
              fill=darker(WOOD, 0.5))                         # 桌面厚度
    # 桌腿
    for lx in (1010, 1372):
        d.rectangle([lx, 760, lx + 26, 1000], fill=darker(WOOD, 0.68))
    # 划痕：细、乱、不显眼
    for i in range(30):
        x0 = random.randint(1020, 1380)
        y0 = random.randint(668, 780)
        d.line([(x0, y0), (x0 + random.randint(-90, 90), y0 + random.randint(-14, 14))],
               fill=darker(WOOD, 0.62), width=1)
    for i in range(6):
        x0 = random.randint(1040, 1350)
        y0 = random.randint(672, 776)
        d.line([(x0, y0), (x0 + random.randint(-160, 160), y0 + random.randint(-20, 20))],
               fill=darker(WOOD, 0.58), width=2)

    # ---------- 台灯（唯一暖光，别太亮）----------
    lx, ly = 1112, 606                                       # 灯头位置
    d.line([(lx, ly + 26), (lx, 700)], fill=darker(WOOD, 0.72), width=5)   # 灯杆
    d.ellipse([lx - 34, 690, lx + 34, 714], fill=darker(WOOD, 0.6))        # 底座
    d.polygon([(lx - 54, ly + 26), (lx + 54, ly + 26), (lx + 34, ly - 22), (lx - 34, ly - 22)],
              fill=darker((212, 206, 194), 0.42))                          # 灯罩
    d.ellipse([lx - 30, ly + 16, lx + 30, ly + 34], fill=(245, 226, 186))  # 灯泡面

    # ---------- 空杯子（桌角，位置留着）----------
    cupx, cupy = 1288, 726
    d.polygon([(cupx - 17, cupy - 30), (cupx + 17, cupy - 30),
               (cupx + 13, cupy), (cupx - 13, cupy)],
              fill=darker((222, 218, 208), 0.3))
    d.ellipse([cupx - 17, cupy - 36, cupx + 17, cupy - 24], fill=darker((210, 206, 196), 0.24))
    d.arc([cupx + 13, cupy - 26, cupx + 33, cupy - 8], -80, 80,
          fill=darker((222, 218, 208), 0.34), width=4)         # 杯柄

    # ---------- 门框（前景，像刚被推开）----------
    # 左侧门框立柱
    d.rectangle([0, 0, 96, H], fill=darker(TEAL, 0.9))
    # 上沿
    d.rectangle([0, 0, W, 66], fill=darker(TEAL, 0.92))
    # 门板（半开，只露一条边，在左边缘）
    d.polygon([(0, 0), (118, 92), (118, 966), (0, H)], fill=darker(TEAL, 0.95))
    # 门框内侧的一线亮边（被窗光照到）
    d.line([(118, 92), (118, 966)], fill=mix(TEAL, (200, 205, 202), 0.45), width=3)
    d.line([(118, 92), (W, 66)], fill=mix(TEAL, (200, 205, 202), 0.3), width=2)

    # ---------- 光照：两处，且只两处 ----------
    # 窗光（冷）
    g1 = radial((W, H), (128, 148, 150), (wx0 + wx1) // 2, 470, 700, 0.5)
    img = screen(img, g1)
    # 台灯（暖，一圈就够）
    g2 = radial((W, H), WARM, lx, ly + 26, 250, 0.85)
    img = screen(img, g2)
    d = ImageDraw.Draw(img)

    # 灯罩下方最亮的一点
    core = radial((W, H), (255, 214, 150), lx, ly + 24, 90, 1.0)
    img = screen(img, core)

    # ---------- 暗角：室内要有一半是暗的 ----------
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.rectangle([0, 0, W, H], fill=255)
    vd.ellipse([-460, -320, W + 460, H + 420], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(180))
    shade = Image.new("RGB", (W, H), (8, 13, 15))
    img = Image.composite(shade, img, vig.point(lambda v: int(v * 0.62)))

    # 门槛附近再压一点（门里看进去，近处更暗）
    near = lin_grad((W, 300), (10, 15, 17), (60, 70, 72))
    near_layer = Image.new("RGB", (W, H), (10, 15, 17))
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for i in range(300):
        md.rectangle([0, H - 300 + i, W, H - 300 + i + 1], fill=int(150 * (1 - i / 300) ** 1.6))
    img = Image.composite(near_layer, img, mask)

    return img


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "xiaoyu_room.png")
    img = draw_room()
    # 轻微颗粒，去掉数字感
    from PIL import ImageChops
    noise = Image.effect_noise((W, H), 9).convert("RGB")
    img = ImageChops.blend(img, ImageChops.add(img, noise, scale=6, offset=-40), 0.28)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(out, quality=95)
    print("saved", out, img.size)


if __name__ == "__main__":
    main()
