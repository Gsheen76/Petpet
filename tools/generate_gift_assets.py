# -*- coding: utf-8 -*-
"""礼物系统占位素材生成器（2026-09-07 礼物系统轮；同日偏好轮扩到 9 礼物）。

生成运行时占位素材（正式素材到位后直接替换同名文件即可）：
- assets/runtime/ui/gifts/sweet_cookie.png    甜心曲奇（档一）
- assets/runtime/ui/gifts/milk_pudding.png    元气布丁（档一）
- assets/runtime/ui/gifts/cheese_cubes.png    香香起司（档一）
- assets/runtime/ui/gifts/meat_can.png        肉肉罐头（档二）
- assets/runtime/ui/gifts/plush_ball.png      毛绒小球（档二）
- assets/runtime/ui/gifts/berry_basket.png    莓莓小篮（档二）
- assets/runtime/ui/gifts/love_box.png        爱心礼盒（档三）
- assets/runtime/ui/gifts/warm_blanket.png    暖暖小毯（档三）
- assets/runtime/ui/gifts/shiny_medal.png     亮晶晶奖牌（档三）
- assets/runtime/ui/shop/gift_tab_icon.png    商店「礼物」页签图标（46x46）
- assets/runtime/ui/pet_profile_new/tab_gift.png   面板第三分栏按钮
    （以 tab_intro.png 为底：逐行插值抹掉原文字，再用幼圆写「礼物」，
     边框/渐变与既有两枚分栏完全一致）
- assets/runtime/ui/pet_profile_new/send_gift_button.png  面板礼物卡「送出」键

礼物名目保持宠物中性（后续加小猫等），不用骨头/毛线球/小鱼干意象。
用法：python tools/generate_gift_assets.py
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(ROOT, "assets", "runtime")
GIFTS_DIR = os.path.join(RUNTIME, "ui", "gifts")
SHOP_DIR = os.path.join(RUNTIME, "ui", "shop")
PROFILE_DIR = os.path.join(RUNTIME, "ui", "pet_profile_new")

# 项目锁定配色（AGENTS.md 视觉风格）。
CREAM = (255, 249, 238, 255)
BISCUIT = (240, 192, 132, 255)
BISCUIT_DARK = (217, 160, 94, 255)
OUTLINE = (192, 122, 74, 255)
CORAL = (242, 143, 118, 255)
CORAL_DEEP = (221, 122, 95, 255)
HEART = (239, 122, 95, 255)
LABEL = (252, 178, 148, 255)
TAB_TEXT = (186, 109, 64, 255)

YOUYUAN_CANDIDATES = (
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "SIMYOU.TTF"),
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in YOUYUAN_CANDIDATES:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    raise SystemExit("找不到可用的中文字体（SIMYOU/msyh/simhei）")


def _heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int,
           fill, outline=None, width=6):
    """两圆+三角拼心形（Pillow 无原生心形图元）。"""
    draw.ellipse((cx - r, cy - r, cx, cy + r * 0.2), fill=fill)
    draw.ellipse((cx, cy - r, cx + r, cy + r * 0.2), fill=fill)
    draw.polygon(
        [(cx - r, cy - r * 0.1), (cx + r, cy - r * 0.1), (cx, cy + r * 1.45)],
        fill=fill,
    )
    if outline:
        _heart_outline(draw, cx, cy, r, outline, width)


def _heart_outline(draw, cx, cy, r, outline, width):
    draw.arc((cx - r, cy - r, cx, cy + r * 0.2), 180, 300,
             fill=outline, width=width)
    draw.arc((cx, cy - r, cx + r, cy + r * 0.2), 240, 360,
             fill=outline, width=width)
    draw.line(
        [(cx - r, cy - r * 0.1), (cx, cy + r * 1.45), (cx + r, cy - r * 0.1)],
        fill=outline, width=width, joint="curve",
    )


def sweet_cookie() -> Image.Image:
    """甜心曲奇：圆饼干 + 烘焙小点 + 中心小爱心。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((60, 60, 280, 280), fill=BISCUIT)
    draw.ellipse((60, 60, 280, 280), outline=OUTLINE, width=9)
    for hx, hy in ((120, 130), (210, 115), (135, 210), (225, 200)):
        draw.ellipse((hx - 9, hy - 9, hx + 9, hy + 9), fill=BISCUIT_DARK)
    _heart(draw, 170, 178, 26, HEART)
    return icon


def milk_pudding() -> Image.Image:
    """元气布丁：焦糖顶的奶布丁 + 小碟子。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    # 碟子。
    draw.ellipse((60, 232, 280, 296), fill=(250, 236, 205, 255),
                 outline=OUTLINE, width=8)
    # 布丁身（梯形近似 + 圆底）。
    draw.polygon(
        [(100, 118), (240, 118), (258, 250), (82, 250)],
        fill=(255, 243, 216, 255),
    )
    draw.line([(100, 122), (84, 246)], fill=OUTLINE, width=9)
    draw.line([(240, 122), (256, 246)], fill=OUTLINE, width=9)
    draw.arc((82, 218, 258, 282), 20, 160, fill=OUTLINE, width=9)
    # 焦糖顶。
    draw.ellipse((94, 84, 246, 152), fill=(214, 148, 88, 255),
                 outline=OUTLINE, width=9)
    return icon


def cheese_cubes() -> Image.Image:
    """香香起司：两块起司方砖 + 气孔。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    cheese = (245, 214, 132, 255)
    # 后块。
    draw.polygon([(150, 96), (262, 96), (262, 208), (150, 208)], fill=cheese)
    draw.line([(150, 96), (262, 96)], fill=OUTLINE, width=9)
    draw.line([(262, 100), (262, 204)], fill=OUTLINE, width=9)
    draw.line([(150, 100), (150, 204)], fill=OUTLINE, width=9)
    draw.line([(150, 208), (262, 208)], fill=OUTLINE, width=9)
    # 前块（错位叠放）。
    draw.polygon([(78, 150), (190, 150), (190, 262), (78, 262)], fill=cheese)
    draw.line([(78, 150), (190, 150)], fill=OUTLINE, width=9)
    draw.line([(190, 154), (190, 258)], fill=OUTLINE, width=9)
    draw.line([(78, 154), (78, 258)], fill=OUTLINE, width=9)
    draw.line([(78, 262), (190, 262)], fill=OUTLINE, width=9)
    for cx, cy, r in ((115, 190, 11), (155, 228, 13), (215, 135, 12),
                      (232, 176, 9)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r),
                     fill=(214, 176, 96, 255))
    return icon


def plush_ball() -> Image.Image:
    """毛绒小球：软球 + 十字缝线 + 高光。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((58, 58, 282, 282), fill=(250, 214, 182, 255))
    draw.ellipse((58, 58, 282, 282), outline=OUTLINE, width=9)
    # 十字缝线（毛绒玩具经典元素，中性）。
    draw.arc((96, 96, 244, 244), 200, 340, fill=OUTLINE, width=8)
    draw.arc((96, 96, 244, 244), 20, 160, fill=OUTLINE, width=8)
    draw.line([(170, 110), (170, 230)], fill=OUTLINE, width=8)
    # 高光。
    draw.ellipse((104, 96, 152, 124), fill=(255, 246, 226, 255))
    return icon


def berry_basket() -> Image.Image:
    """莓莓小篮：编织小篮 + 三颗莓果 + 叶片。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    # 篮身（梯形）+ 编织横纹。
    draw.polygon([(88, 150), (252, 150), (232, 274), (108, 274)],
                 fill=(233, 190, 134, 255))
    draw.line([(88, 154), (110, 270)], fill=OUTLINE, width=9)
    draw.line([(252, 154), (230, 270)], fill=OUTLINE, width=9)
    draw.line([(88, 150), (252, 150)], fill=OUTLINE, width=9)
    draw.line([(106, 274), (234, 274)], fill=OUTLINE, width=9)
    for y in (186, 222):
        draw.line([(98 - (0 if y == 186 else 4), y),
                   (242 + (0 if y == 186 else 4), y)],
                  fill=OUTLINE, width=6)
    # 莓果。
    for cx, cy in ((120, 122), (170, 104), (222, 124)):
        draw.ellipse((cx - 30, cy - 26, cx + 30, cy + 30),
                     fill=(238, 116, 106, 255), outline=OUTLINE, width=8)
        draw.ellipse((cx - 6, cy - 20, cx + 6, cy - 8),
                     fill=(126, 168, 96, 255))
    return icon


def warm_blanket() -> Image.Image:
    """暖暖小毯：折起的绒毯三叠 + 流苏。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    body = (250, 214, 182, 255)
    fold = (240, 196, 158, 255)
    # 三段折叠（上窄下宽的圆角矩形堆叠）。
    draw.rounded_rectangle((84, 74, 256, 150), radius=16, fill=fold)
    draw.rounded_rectangle((84, 74, 256, 150), radius=16,
                           outline=OUTLINE, width=8)
    draw.rounded_rectangle((76, 142, 264, 218), radius=16, fill=body)
    draw.rounded_rectangle((76, 142, 264, 218), radius=16,
                           outline=OUTLINE, width=8)
    draw.rounded_rectangle((68, 210, 272, 268), radius=16, fill=fold)
    draw.rounded_rectangle((68, 210, 272, 268), radius=16,
                           outline=OUTLINE, width=8)
    # 底缘流苏。
    for x in range(92, 272, 36):
        draw.line([(x, 272), (x, 296)], fill=OUTLINE, width=7)
    # 小爱心点缀。
    _heart(draw, 118, 116, 12, HEART)
    _heart(draw, 224, 186, 12, HEART)
    return icon


def shiny_medal() -> Image.Image:
    """亮晶晶奖牌：缎带 + 金牌 + 星星。"""
    size = 340
    icon = new = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(new)
    # 缎带两尾。
    draw.polygon([(120, 58), (170, 58), (152, 160), (110, 150)],
                 fill=CORAL, outline=OUTLINE)
    draw.polygon([(220, 58), (170, 58), (188, 160), (230, 150)],
                 fill=CORAL_DEEP, outline=OUTLINE)
    # 金牌。
    draw.ellipse((86, 138, 254, 306), fill=(244, 197, 92, 255))
    draw.ellipse((86, 138, 254, 306), outline=OUTLINE, width=9)
    draw.ellipse((108, 160, 232, 284), outline=(214, 166, 74, 255), width=7)
    # 星星（五角）。
    import math
    cx, cy, r1, r2 = 170, 222, 42, 17
    pts = []
    for i in range(10):
        r = r1 if i % 2 == 0 else r2
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, fill=(255, 246, 214, 255), outline=OUTLINE)
    # 闪光。
    draw.line([(96, 92), (96, 118)], fill=(244, 214, 138, 255), width=7)
    draw.line([(82, 105), (110, 105)], fill=(244, 214, 138, 255), width=7)
    return icon


def meat_can() -> Image.Image:
    """肉肉罐头：圆柱罐 + 珊瑚标签 + 罐面小爱心。"""
    size = 340
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    # 罐身（圆柱侧壁）。
    draw.rectangle((86, 118, 254, 252), fill=(250, 236, 205, 255))
    draw.ellipse((86, 232, 254, 292), fill=(240, 218, 178, 255))
    # 标签带。
    draw.rectangle((86, 150, 254, 224), fill=LABEL)
    # 罐口（顶面椭圆）。
    draw.ellipse((86, 74, 254, 142), fill=(255, 247, 228, 255))
    _heart(draw, 170, 186, 30, HEART)
    # 轮廓（最后画，覆盖接缝）。
    draw.ellipse((86, 74, 254, 142), outline=OUTLINE, width=9)
    draw.line([(86, 108), (86, 262)], fill=OUTLINE, width=9)
    draw.line([(254, 108), (254, 262)], fill=OUTLINE, width=9)
    draw.arc((86, 232, 254, 292), 0, 180, fill=OUTLINE, width=9)
    draw.line([(86, 150), (254, 150)], fill=OUTLINE, width=7)
    draw.line([(86, 224), (254, 224)], fill=OUTLINE, width=7)
    return icon


def love_box(scale: float = 1.0) -> Image.Image:
    """爱心礼盒：奶油盒 + 珊瑚缎带 + 顶部蝴蝶结与爱心。"""
    size = round(340 * scale)
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    s = scale

    def box_rect(x0, y0, x1, y1):
        return tuple(round(v * s) for v in (x0, y0, x1, y1))

    # 盒身。
    draw.rounded_rectangle(box_rect(70, 128, 270, 282), radius=22 * s,
                           fill=(247, 201, 164, 255))
    # 竖缎带。
    draw.rectangle(box_rect(152, 128, 188, 282), fill=CORAL)
    # 盒盖（略宽的扁盖）。
    draw.rounded_rectangle(box_rect(56, 96, 284, 152), radius=20 * s,
                           fill=(252, 216, 180, 255))
    draw.rectangle(box_rect(152, 96, 188, 152), fill=CORAL)
    # 蝴蝶结（左右两瓣 + 中央结）。
    draw.polygon(box_rect(100, 66, 162, 104), fill=CORAL_DEEP)
    draw.polygon(box_rect(178, 66, 240, 104), fill=CORAL_DEEP)
    draw.rounded_rectangle(box_rect(152, 66, 188, 104), radius=10 * s,
                           fill=CORAL)
    _heart(draw, round(170 * s), round(210 * s), round(26 * s), HEART)
    # 轮廓。
    draw.rounded_rectangle(box_rect(70, 128, 270, 282), radius=22 * s,
                           outline=OUTLINE, width=round(9 * s))
    draw.rounded_rectangle(box_rect(56, 96, 284, 152), radius=20 * s,
                           outline=OUTLINE, width=round(9 * s))
    draw.line(box_rect(152, 104, 152, 282), fill=OUTLINE,
              width=round(9 * s))
    draw.line(box_rect(188, 104, 188, 282), fill=OUTLINE,
              width=round(9 * s))
    draw.rounded_rectangle(box_rect(152, 66, 188, 104), radius=10 * s,
                           outline=OUTLINE, width=round(7 * s))
    draw.polygon(box_rect(100, 66, 162, 104), outline=OUTLINE)
    draw.polygon(box_rect(178, 66, 240, 104), outline=OUTLINE)
    return icon


def tab_gift() -> Image.Image:
    """面板第三分栏：tab_intro.png 逐行修复文字区后写「礼物」。"""
    base = Image.open(
        os.path.join(PROFILE_DIR, "tab_intro.png")
    ).convert("RGBA")
    width, height = base.size
    pixels = base.load()
    # 原「简介」文字包围盒（实测 dark bbox 外扩 20px），左右取净区端点。
    left, right = 295, 1291
    top, bottom = 77, 426
    for y in range(top, min(bottom + 1, height)):
        c0 = pixels[left, y]
        c1 = pixels[right, y]
        span = right - left
        for x in range(left + 1, right):
            t = (x - left) / span
            pixels[x, y] = tuple(
                round(c0[i] + (c1[i] - c0[i]) * t) for i in range(4)
            )
    draw = ImageDraw.Draw(base)
    font = _font(round(height * 0.64))
    text = "礼物"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - text_w) / 2 - bbox[0], (height - text_h) / 2 - bbox[1]),
        text, font=font, fill=TAB_TEXT,
    )
    return base


def send_gift_button() -> Image.Image:
    """面板礼物卡「送出」胶囊键（珊瑚底白字，_ArtButton 素材）。"""
    width, height = 240, 84
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, width - 4, height - 4), radius=38,
                           fill=CORAL)
    draw.rounded_rectangle((4, 4, width - 4, height - 4), radius=38,
                           outline=CORAL_DEEP, width=4)
    font = _font(44)
    bbox = draw.textbbox((0, 0), "送出", font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - text_w) / 2 - bbox[0], (height - text_h) / 2 - bbox[1]),
        "送出", font=font, fill=(255, 255, 255, 255),
    )
    return image


def gift_tab_icon() -> Image.Image:
    """商店「礼物」页签图标：46x46 迷你礼盒。"""
    box = love_box(scale=1.0)
    icon = box.resize((46, 46), Image.LANCZOS)
    return icon


def main() -> int:
    os.makedirs(GIFTS_DIR, exist_ok=True)
    outputs = (
        (os.path.join(GIFTS_DIR, "sweet_cookie.png"), sweet_cookie()),
        (os.path.join(GIFTS_DIR, "milk_pudding.png"), milk_pudding()),
        (os.path.join(GIFTS_DIR, "cheese_cubes.png"), cheese_cubes()),
        (os.path.join(GIFTS_DIR, "meat_can.png"), meat_can()),
        (os.path.join(GIFTS_DIR, "plush_ball.png"), plush_ball()),
        (os.path.join(GIFTS_DIR, "berry_basket.png"), berry_basket()),
        (os.path.join(GIFTS_DIR, "love_box.png"), love_box()),
        (os.path.join(GIFTS_DIR, "warm_blanket.png"), warm_blanket()),
        (os.path.join(GIFTS_DIR, "shiny_medal.png"), shiny_medal()),
        (os.path.join(SHOP_DIR, "gift_tab_icon.png"), gift_tab_icon()),
        (os.path.join(PROFILE_DIR, "tab_gift.png"), tab_gift()),
        (os.path.join(PROFILE_DIR, "send_gift_button.png"), send_gift_button()),
    )
    legacy = os.path.join(GIFTS_DIR, "bone_cookie.png")
    if os.path.exists(legacy):
        os.remove(legacy)
        print(f"removed legacy {os.path.relpath(legacy, ROOT)}")
    for path, image in outputs:
        image.save(path)
        print(f"wrote {os.path.relpath(path, ROOT)} {image.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
