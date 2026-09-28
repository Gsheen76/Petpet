# -*- coding: utf-8 -*-
"""纯缩放反馈守卫（2026-09-28 用户定稿：全应用统一悬浮放大+点击缩小
再还原，撤一切描边/白洗叠层）。

四角锁定特效真正根因：FeedbackButton 悬浮帧曾把珊瑚描边画在
rect±2 的圆角矩形上，控件边界裁掉描边直线段、只剩四角的弧段——
正是用户拍到的「取景框角标」。本测试把修后行为钉死：

1. hover 帧 == 素颜帧整体放大 2px/边（无任何叠层像素）
2. _AvatarButton 悬浮外扩、按压内缩（bbox 对比）
3. 家园场景键悬浮整键外扩（bbox 对比）
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap, QRegion
from PyQt5.QtWidgets import QApplication, QWidget


def _array(image):
    """QImage(ARGB32) → (h, w, 4) uint8。"""
    ptr = image.constBits()
    bpl = image.bytesPerLine()
    ptr.setsize(bpl * image.height())
    arr = np.frombuffer(bytes(ptr), dtype=np.uint8)
    return arr.reshape(image.height(), bpl)[:, : image.width() * 4].reshape(
        image.height(), image.width(), 4
    )


def _opaque_bbox(image):
    """非透明像素的包围盒（QImage ARGB32）。"""
    alpha = _array(image)[:, :, 3]
    ys, xs = np.nonzero(alpha > 24)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _images_close(a, b, tol=10, max_bad_frac=0.002):
    """逐像素比较，允许抗锯齿容差；坏点比例须小于 max_bad_frac。"""
    if a.size() != b.size():
        return False, -1, -1
    aa, bb = _array(a).astype(int), _array(b).astype(int)
    bad = int((np.abs(aa - bb).max(axis=2) > tol).sum())
    total = a.width() * a.height()
    return bad <= total * max_bad_frac, bad, total


class FeedbackButtonPureScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hover_frame_is_pure_scaled_skin(self):
        """悬浮帧必须只含放大后的素颜帧——描边/白洗一律不得回归。

        旧根因：描边画在 rect±2 圆角矩形，被控件边界裁成四角括号。
        """
        from petpet.progression.ui import FeedbackButton

        btn = FeedbackButton("购买")
        btn.resize(110, 48)
        btn.show()
        self.addCleanup(btn.close)
        btn._capture_skin()
        self.assertIsNotNone(btn._skin_cache)
        # 强制进入 hover 相位（offscreen 无真鼠标，顶替判定）。
        btn.underMouse = lambda: True
        hover = btn.grab().toImage().convertToFormat(QImage.Format_ARGB32)
        # 期望帧：素颜帧按 hover 目标矩形（±2px）整体绘制。
        expected = QPixmap(btn.size())
        expected.fill(Qt.transparent)
        p = QPainter(expected)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(QRect(-2, -2, btn.width() + 4, btn.height() + 4),
                     btn._skin_cache)
        p.end()
        exp = expected.toImage().convertToFormat(QImage.Format_ARGB32)
        ok, bad, total = _images_close(hover, exp)
        self.assertTrue(
            ok,
            f"悬浮帧不得含放大素材以外的叠层（描边/白洗回归？坏点 {bad}/{total}）",
        )

    def test_recover_frame_equals_plain_skin(self):
        """回弹相位于原大小直绘素颜帧（无叠层）。"""
        from petpet.progression.ui import FeedbackButton

        btn = FeedbackButton("确定")
        btn.resize(96, 44)
        btn.show()
        self.addCleanup(btn.close)
        btn._capture_skin()
        btn._pending_fire = True  # recover 相位
        recover = btn.grab().toImage().convertToFormat(QImage.Format_ARGB32)
        expected = QPixmap(btn.size())
        expected.fill(Qt.transparent)
        p = QPainter(expected)
        p.drawPixmap(QRect(0, 0, btn.width(), btn.height()),
                     btn._skin_cache)
        p.end()
        exp = expected.toImage().convertToFormat(QImage.Format_ARGB32)
        ok, bad, total = _images_close(recover, exp)
        self.assertTrue(
            ok, f"回弹帧应为原大小素颜帧（坏点 {bad}/{total}）"
        )


class AvatarButtonPureScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _button(self):
        from petpet.ui.pet_profile import _AvatarButton

        btn = _AvatarButton()
        art = QPixmap(80, 80)
        art.fill(QColor("#e8a37c"))
        btn.set_pixmap(art)
        btn.resize(80, 80)
        btn.show()
        self.addCleanup(btn.close)
        return btn

    def _grab(self, btn):
        # render 时不画窗口底色（否则 offscreen 调色板灰底盖满全幅）。
        pm = QPixmap(btn.size())
        pm.fill(Qt.transparent)
        btn.render(pm, QPoint(), QRegion(), QWidget.DrawChildren)
        return pm.toImage().convertToFormat(QImage.Format_ARGB32)

    def test_hover_grows_press_shrinks_no_overlay(self):
        btn = self._button()
        normal = _opaque_bbox(self._grab(btn))
        btn._hovered = True
        hovered = _opaque_bbox(self._grab(btn))
        btn._hovered = False
        btn._pressed = True
        pressed = _opaque_bbox(self._grab(btn))
        btn._pressed = False
        self.assertIsNotNone(normal)
        # 常态内缩 2px、悬浮回全幅、按压内缩 5px（含压暗盖）。
        self.assertEqual(normal[0], 2, "常态头像应四周留 2px 余量")
        self.assertEqual(hovered[0], 0, "悬浮应放大到全幅（无余量）")
        self.assertEqual(pressed[0], 5, "按压应内缩 5px（2026-09-28 三轮：4→6→5px）")
        # 悬浮帧不得引入白色洗盖（顶部不得出现近白不透明像素）。
        btn._hovered = True
        arr = _array(self._grab(btn))
        top = arr[0:4]
        wash_like = int(
            ((top[:, :, 3] > 40)
             & (top[:, :, 0] > 246)
             & (top[:, :, 1] > 246)
             & (top[:, :, 2] > 236)).sum()
        )
        self.assertEqual(
            wash_like, 0, "悬浮帧顶部不得出现白洗盖（纯缩放反馈）"
        )


class HomeSceneButtonPureScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _paint(self, state):
        from petpet.home.window import HomeSceneWindow

        img = QImage(140, 64, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        HomeSceneWindow._draw_scene_button(
            None, p, QRect(20, 10, 100, 40), "测试",
            variant="primary", state=state,
        )
        p.end()
        return img

    def test_hover_enlarges_whole_button(self):
        normal = _opaque_bbox(self._paint(None))
        hovered = _opaque_bbox(self._paint("hover"))
        pressed = _opaque_bbox(self._paint("pressed"))
        self.assertIsNotNone(normal)
        self.assertEqual(
            (hovered[2] - hovered[0]) - (normal[2] - normal[0]), 6,
            "悬浮整键应外扩 3px/边",
        )
        self.assertEqual(
            (pressed[2] - pressed[0]) - (normal[2] - normal[0]), -8,
            "按压整键应内缩 4px/边（2026-09-28 三轮：3→5→4px 折中）",
        )

    def test_pressed_keeps_label_visible(self):
        """按压压暗盖后必须复回文字色 pen——NoPen 下 drawText 不绘制
        （五轮评审抓出的按住文字消失回归）。offscreen 无字体库，文字
        渲染 0 像素，像素对照测不出——改钉源码时序。"""
        import re

        src = (Path(__file__).resolve().parents[1]
               / "petpet" / "home" / "window.py").read_text(encoding="utf-8")
        block = re.search(
            r"def _draw_scene_button\(.*?(?=\n    def )", src, re.S
        )
        self.assertIsNotNone(block, "找不到 _draw_scene_button")
        text = block.group(0)
        self.assertIn(
            "painter.setPen(text)\n        painter.drawText",
            text,
            "按压压暗盖（NoPen）后必须复回文字色再 drawText",
        )


class PureScaleStaticGuards(unittest.TestCase):
    """静态守卫：叠层撤除断言（halo 色号/recover 放大模式禁止回库）。"""

    ROOT = Path(__file__).resolve().parents[1]

    def test_bubble_menu_hover_halo_present(self):
        """气泡菜单 hover 光环（2026-09-28 晚用户定稿恢复：「我喜欢
        之前那样的交互方式」）——光环画在整格内，无越界裁角问题；
        纯缩放规范不适用于气泡菜单，防再被统一轮误删。"""
        src = (self.ROOT / "petpet" / "ui" / "desktop.py").read_text(
            encoding="utf-8")
        self.assertIn(
            "242, 143, 118, 34", src, "气泡菜单悬浮白洗光环是用户定稿")
        self.assertIn(
            'QPen(QColor("#f28f76"), 2.2)', src,
            "气泡菜单悬浮珊瑚描边是用户定稿")

    def test_recover_state_never_enlarges(self):
        """recover（回弹）相位=原大小，不得与 hover 同享放大几何。"""
        src = (self.ROOT / "petpet" / "home" / "window.py").read_text(
            encoding="utf-8")
        self.assertNotIn(
            '== "hover" or state == "recover"', src,
            "recover 相位不得沿用悬浮放大（点击缩小再还原）")


if __name__ == "__main__":
    unittest.main()
