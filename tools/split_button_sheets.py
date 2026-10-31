# -*- coding: utf-8 -*-
"""2026-10-31 功能专属水彩按钮批产——Meowa 9 宫 sheet 拆版工具。

输入: assets/source/meowa/button-skins-2026-10-31/sheet{A,B,C,D}/.../edited.png
      (asset-clone-run 以 btn_pill_normal.png / home feed.png 为源克隆的 9 格拼版)
输出: 胶囊族 → assets/runtime/ui/panels/ (高 88 等比, QSS 九宫左 96 切片护主题龛)
      家园族 → assets/runtime/scenes/home/buttons/ (宽 500 等比, 覆盖同名旧键)
      原件先归档到 assets/source/references/button_skins_v0/ 便于回退
派生: hover=亮度0.92+饱和1.06; 页签 checked=亮度0.90+饱和1.08 (零积分本地派生)
运行: python tools/split_button_sheets.py [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil

import numpy as np
from PIL import Image, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_GLOB = os.path.join(
    ROOT, "assets", "source", "meowa", "button-skins-2026-10-31",
    "sheet*", "**", "edited.png")
PANELS_DIR = os.path.join(ROOT, "assets", "runtime", "ui", "panels")
HOME_DIR = os.path.join(ROOT, "assets", "runtime", "scenes", "home", "buttons")
ARCHIVE_DIR = os.path.join(
    ROOT, "assets", "source", "references", "button_skins_v0")
REVIEW_DIR = os.path.join(
    ROOT, "assets", "source", "meowa", "button-skins-2026-10-31", "review")

# cell 名单: sheet → [(槽位, 输出名, 族, 派生态)]
# 族 pill=面板胶囊(高88+hover) tab=页签(+checked) home=家园键(宽500)
PLAN = {
    "A": [
        ("A1", "btn_claim", "pill"),        # 金币堆——每日领取
        ("A2", "btn_claim_all", "pill"),    # 福袋——一键领取全部
        ("A3", "btn_checkin", "pill"),      # 日历对勾——签到领取
        ("A4", "btn_tab_paw", "tab"),       # 爪印——记录按宠页签
        ("A5", "btn_tab_medal", "tab"),     # 丝带金牌——成就筛选页签
        ("A6", "btn_replay", "pill"),       # 循环环——再玩一次/聊天↻
        ("A7", "btn_start", "pill"),        # 珊瑚球——开始游戏
        ("A8", "btn_game_coin", "pill"),    # 金币布袋——接金币入口
        ("A9", "btn_game_paw", "pill"),     # 四叶爪垫——幸运爪入口
    ],
    "B": [
        ("B1", "btn_game_card", "pill"),    # 翻牌对——记忆翻牌入口
        ("B2", "btn_send", "pill"),         # 纸飞机——聊天发送/停止
        ("B3", "btn_upload", "pill"),       # 云朵上箭头——聊天上传
        ("B4", "btn_export", "pill"),       # 信封下箭头——导出(设置/聊天)
        ("B5", "btn_clear", "pill"),        # 淡橡皮——聊天 DEL
        ("B6", "btn_save", "pill"),         # 盖章对勾——设置保存
        ("B7", "btn_reset", "pill"),        # 回旋箭头——恢复默认值
        ("B8", "btn_backup", "pill"),       # 小纸箱——一键备份
        ("B9", "btn_restore", "pill"),      # 纸箱上箭头——从备份恢复
    ],
    "C": [
        ("C1", "btn_gift_box", "pill"),     # 礼盒——商店免费领取/送礼
        ("C2", "btn_collar", "pill"),       # 格纹项圈——商店切换宠物
        ("C3", "btn_companion", "pill"),    # 爱心依偎——面板陪我
        ("C4", "btn_gift_basket", "pill"),  # 礼物篮——面板送礼
        # C5-C9 备用格不落 runtime(防孤儿守卫), 拆出仅存 source
    ],
    "D": [
        ("D1", "feed", "home"),             # 食盆骨头——家园喂食
        ("D2", "play", "home"),             # 绒球弧线——家园玩耍
        ("D3", "sleep", "home"),            # 月牙Zzz——家园睡觉
        ("D4", "shop", "home"),             # 店帐篷——家园商店
        ("D5", "pets", "home"),             # 项圈——家园宠物
        ("D6", "decorate", "home"),         # 刷滚彩点——家园装修
        ("D7", "exit", "home"),             # 木门——家园退出
        ("D8", "pet", "home"),              # 爪印小径——家园宠物面板
        # D9 备用格不落 runtime
    ],
}

HOME_KEYS = {"feed", "play", "sleep", "shop", "pets", "decorate", "exit", "pet"}


def bands(mask, axis):
    """沿 axis 的投影分段 (lit→band)。返回 [(start, end), ...]"""
    proj = mask.sum(axis=axis // 2 * 0 + (1 if axis == 0 else 0))
    lit = proj > 0
    out, start = [], None
    for i, v in enumerate(lit):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(lit)))
    return out


def alpha_mask(im, thresh=12):
    return np.array(im)[:, :, 3] > thresh


def split_sheet(path):
    """3×3 拆版: 行带 → 每行在 1/3、2/3 近旁找列投影谷切开(胶囊软边相接无零隙);
    再用实心行列过滤(最大 alpha≥90)剥掉切缝残边。返回 [(rgba, bbox), ...] 行优先。"""
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    mask = arr[:, :, 3] > 12
    rows = bands(mask, axis=0)
    if len(rows) != 3:
        raise RuntimeError(f"{path}: 行带 {len(rows)} != 3: {rows}")
    w = im.size[0]
    cells = []
    for r0, r1 in rows:
        prof = mask[r0:r1].sum(axis=0)
        cuts = [0, w]
        for center in (w // 3, w * 2 // 3):
            lo = max(0, center - 60)
            cuts.append(lo + int(np.argmin(prof[lo:center + 60])))
        cuts.sort()
        for c0, c1 in zip(cuts, cuts[1:]):
            cell = arr[r0:r1, c0:c1]
            solid = cell[:, :, 3] >= 90
            cols = np.where(solid.any(axis=0))[0]
            rws = np.where(solid.any(axis=1))[0]
            if len(cols) == 0 or len(rws) == 0:
                raise RuntimeError(f"{path}: 格({r0},{c0}) 无实心内容")
            y0, y1 = rws[0], rws[-1] + 1
            x0, x1 = cols[0], cols[-1] + 1
            img = Image.fromarray(cell[y0:y1, x0:x1])
            cells.append((img, (c0 + x0, r0 + y0, c0 + x1, r0 + y1)))
    return cells


def derive(im, brightness, color):
    out = ImageEnhance.Color(im).enhance(color)
    return ImageEnhance.Brightness(out).enhance(brightness)


def normalize(im, family):
    w, h = im.size
    if family == "home":
        return im.resize((500, round(h * 500 / w)), Image.LANCZOS)
    return im.resize((round(w * 88 / h), 88), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sheets = {}
    for path in sorted(glob.glob(SRC_GLOB, recursive=True)):
        key = os.path.basename(os.path.dirname(os.path.dirname(path)))[:6]
        sheets[key] = path  # sheetA/B/C/D 目录名前缀
    report = []
    for sheet_id, plan in PLAN.items():
        path = next(
            (p for k, p in sheets.items() if k.startswith("sheet" + sheet_id)),
            None)
        if path is None:
            report.append(f"{sheet_id}: sheet 未找到!")
            continue
        cells = split_sheet(path)
        if len(cells) != 9:
            report.append(f"{sheet_id}: 拆出 {len(cells)} 格 != 9")
            continue
        for slot, name, family in plan:
            idx = int(slot[1]) - 1
            cell, box = cells[idx]
            img = normalize(cell, family)
            if family == "home":
                dest_dir = HOME_DIR
                variants = [("", img)]
                out_base = name + ".png"
            elif family == "tab":
                dest_dir = PANELS_DIR
                variants = [
                    ("", img),
                    ("_hover", derive(img, 0.92, 1.06)),
                    ("_checked", derive(img, 0.90, 1.08)),
                ]
                out_base = name
            else:
                dest_dir = PANELS_DIR
                variants = [
                    ("", img),
                    ("_hover", derive(img, 0.92, 1.06)),
                ]
                out_base = name
            for suffix, image in variants:
                fname = (name + suffix + ".png") if family != "home" \
                    else out_base
                target = os.path.join(dest_dir, fname)
                if os.path.exists(target):
                    arc = os.path.join(ARCHIVE_DIR, fname)
                    if not os.path.exists(arc) and not args.dry_run:
                        os.makedirs(ARCHIVE_DIR, exist_ok=True)
                        shutil.copy2(target, arc)
                report.append(
                    f"{slot} {fname:28s} {image.size[0]}x{image.size[1]} "
                    f"src_bbox={box}")
                if not args.dry_run:
                    image.save(target)
    print("\n".join(report))
    print(f"\n{'[DRY] ' if args.dry_run else ''}共 {len(report)} 格处理完成")


if __name__ == "__main__":
    main()
