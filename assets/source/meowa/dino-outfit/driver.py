# -*- coding: utf-8 -*-
"""恐龙套装动画批量管线：gen / extract / import / verify / all
用法：python driver.py <stage> <action>
action ∈ pet|eat|play|dig|happy|sleep
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent
REF = Path(r'assets/source/meowa/dino-idle-v2/user_reference.png')
SKILL = r'C:\Users\sheen\.agents\skills\game-assets\meowart_api.py'
RUNTIME = Path(r'assets/runtime/pets/lunch_meat/desktop/animations')
MANIFEST = RUNTIME / 'manifest.json'
CANVAS = 640
BOTTOM_ROW = 596
PAW_CX = 315.0
CONTENT_H = 585.0

PROMPTS = {
    "pet": "The sitting puppy in the green dinosaur costume happily enjoys being petted on the head: eyes close into a content squinting smile, the ears relax and twitch gently with delight, the fluffy tail wags slowly, and the body leans forward very slightly into the affection. The head stays mostly straight and upright. It starts and ends in the exact reference pose. Same costume, same face, same colors, side view facing right, same size and position in every frame.",
    "eat": "The sitting puppy in the green dinosaur costume eats contentedly: it lowers its head only slightly and nibbles and chews at chest height with a happy relaxed chewing motion, small joyful tail sways, eyes squinting with enjoyment. The head movement is small and gentle, never buried to the ground. It starts and ends in the exact reference pose. Same costume, same face, same colors, side view facing right, same size and position in every frame.",
    "play": "The sitting puppy in the green dinosaur costume plays joyfully in place: it makes small energetic happy bounces with its whole body (feet barely leaving the ground), the fluffy tail wags super fast, the ears flop up and down, bright playful expression. The head stays up and straight. It starts and ends in the exact reference pose. Same costume, same face, same colors, side view facing right, same size and position in every frame.",
    "dig": "The sitting puppy in the green dinosaur costume just discovered a buried treasure and celebrates with pure joy: eyes sparkle wide, it sits up tall and bounces excitedly twice, the fluffy tail whirls around fast, ears fly up happily. The head stays up and straight. It starts and ends in the exact reference pose. Same costume, same face, same colors, side view facing right, same size and position in every frame.",
    "happy": "The sitting puppy in the green dinosaur costume tilts its head to one side in curious delight, one ear flopping down with a sweet squinting smile, then straightens back up with the ear springing back, then tilts its head to the other side with the other ear flopping, fluffy curled tail wagging happily, and finally returns exactly to the starting pose. The face stays mostly looking forward, head movement is gentle and small. Same costume, same face, same colors, side view facing right, same size and position in every frame.",
    "sleep": "The sitting puppy in the green dinosaur costume gets sleepy, curls up and lies down on its side, closes its eyes and sleeps peacefully with deep slow breathing (the body gently rising and falling), then after a while it wakes up, stretches slightly and returns to the sitting reference pose. Most of the animation is the peaceful lying-down sleep breathing. Same costume, same face, same colors, side view facing right, same size and position in every frame.",
}

KEY = {"pet": "pet_dinosaur", "eat": "eat_dinosaur", "play": "play_dinosaur",
       "dig": "dig_dinosaur", "happy": "happy_dinosaur", "sleep": "sleep_dinosaur"}
DUR = {"pet": ([110.0]*24, False), "eat": ([125.0]*24, True),
       "play": ([100.0]*24, False), "dig": ([110.0]*24, False),
       "happy": ([135.0]*4+[118.0]*5+[145.0, 118.0]+[118.0]*5+[135.0, 135.0]+[118.0]*2+[145.0, 118.0]+[135.0]*4, False)[:2],
       "sleep": ([300.0]*16, True)}


def sh(cmd, timeout=1500):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')


def gen(action):
    out = ROOT / action
    out.mkdir(exist_ok=True)
    (out / 'prompt.txt').write_text(PROMPTS[action], encoding='utf-8')
    r = sh(['python', SKILL, 'meowa-animation-run',
            '--output-dir', str(out),
            '--image-file', str(REF), '--last-image-file', str(REF),
            '--prompt', PROMPTS[action],
            '--style-mode', 'hd', '--resolution', '720p', '--quality-mode', 'medium',
            '--alpha-mode', 'soft', '--remove-bg-method', 'standard'])
    log = (r.stdout or '') + (r.stderr or '')
    (out / 'gen.log').write_text(log, encoding='utf-8')
    if 'no final media could be downloaded' in log:
        rescue(out, log)
    webp = newest_webp(out)
    print(f'[{action}] gen done -> {webp}')
    return webp


def rescue(out, log):
    import re
    urls = re.findall(r'https://media\.meowa\.ai/[^\s:\]]+\.webp', log)
    d = newest_task_dir(out)
    d.mkdir(parents=True, exist_ok=True)
    for u in urls:
        name = u.split('/')[-1]
        for i in range(4):
            r = sh(['curl', '-sS', '-x', 'http://127.0.0.1:7897', '-C', '-',
                    '--max-time', '240', '-o', str(d / name), u])
            if r.returncode == 0:
                break
            time.sleep(3)


def newest_task_dir(out):
    ds = [p for p in out.iterdir() if p.is_dir() and p.name != 'frames']
    return max(ds, key=lambda p: p.stat().st_mtime) if ds else out / 'task'


def newest_webp(out):
    cands = [p for p in out.rglob('meowa_animation.webp')] + \
            [p for p in out.rglob('meowa_animation_2.webp')]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def extract(action):
    out = ROOT / action
    src = newest_webp(out)
    im = Image.open(src)
    n = getattr(im, 'n_frames', 1)
    fr = out / 'frames'
    fr.mkdir(exist_ok=True)
    for p in fr.glob('*.png'):
        p.unlink()
    heads, paws, ious = [], [], []
    prev = None
    for i in range(n):
        im.seek(i)
        a = np.asarray(im.convert('RGBA'))
        Image.fromarray(a).save(fr / f'{i:03d}.png')
        solid = a[..., 3] > 128
        ys, xs = np.where(solid)
        top, bot = ys.min(), ys.max()
        h = bot - top
        head = solid[:top + int(h * 0.30)]
        hys, hxs = np.where(head)
        heads.append(hxs.max() - hxs.min() + 1 if hxs.size else 0)
        paw = solid[top + int(h * 0.85):]
        pys, pxs = np.where(paw)
        paws.append(pxs.mean())
        if prev is not None:
            ious.append((prev & solid).sum() / (prev | solid).sum())
        prev = solid
    hsw = (max(heads) - min(heads)) / max(heads)
    report = {'frames': n, 'head_swing': round(hsw, 3), 'paw': round(max(paws) - min(paws), 1),
              'iou_min': round(min(ious), 3), 'iou_max': round(max(ious), 3)}
    (out / 'audit.json').write_text(json.dumps(report), encoding='utf-8')
    print(f'[{action}]', report)
    return report


def import_(action):
    import cv2
    fr = ROOT / action / 'frames'
    files = sorted(fr.glob('*.png'))
    if action == 'sleep':
        files = pick_sleep_segment(files)
    dst = RUNTIME / 'outfits' / 'dinosaur' / action_dir(action)
    dst.mkdir(parents=True, exist_ok=True)
    for p in dst.glob('*.png'):
        p.unlink()

    import scipy.ndimage as ndimage
    frames = []
    for f in files:
        a = np.asarray(Image.open(f).convert('RGBA')).astype(np.float32)
        s = a[..., 3] > 128
        ys, xs = np.where(s)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        h = y1 - y0 + 1
        sc = CONTENT_H / h
        p = a[y0:y1+1, x0:x1+1].copy()
        p[..., :3] *= (p[..., 3:4] / 255.0)
        hh = int(round(p.shape[0] * sc))
        ww = int(round(p.shape[1] * sc))
        m = cv2.resize(p, (ww, hh), interpolation=cv2.INTER_LANCZOS4)
        out = np.zeros((CANVAS, CANVAS, 4), np.float32)
        ox = (CANVAS - ww) // 2
        oy = (CANVAS - hh) // 2
        out[max(0,oy):max(0,oy)+min(hh,CANVAS), max(0,ox):max(0,ox)+min(ww,CANVAS)] = m[max(0,-oy):, max(0,-ox):]
        out = register(out)
        frames.append(out)

    idle_pool = []
    for j in range(24):
        oa = np.asarray(Image.open(RUNTIME / 'outfits/dinosaur/idle' / f'{j:03d}.png').convert('RGBA')).astype(np.float32)
        idle_pool.append(oa[oa[..., 3] > 200][:, :3])
    idle_pool = np.concatenate(idle_pool)
    pool = np.concatenate([k[(k[..., 3] > 200)][..., :3] for k in frames])
    luts = []
    for c in range(3):
        srcq = np.quantile(np.sort(pool[:, c]), np.linspace(0, 1, 2048))
        tgtq = np.quantile(np.sort(idle_pool[:, c]), np.linspace(0, 1, 2048))
        luts.append(np.interp(np.arange(256, dtype=np.float32), srcq, tgtq).astype(np.float32))
    for i, k in enumerate(frames):
        al = k[..., 3:4] / 255.0
        o = k.copy()
        o[..., :3] = np.clip(k[..., :3] / np.maximum(al, 1e-6), 0, 255)
        o[..., 3] = np.clip(k[..., 3], 0, 255)
        for c in range(3):
            o[..., c] = luts[c][np.clip(o[..., c], 0, 255).astype(np.int32)]
        Image.fromarray(np.clip(o, 0, 255).round().astype(np.uint8), 'RGBA').save(dst / f'{i:03d}.png')

    durs, loop = DUR[action]
    if action == 'sleep':
        durs = [300.0] * len(files)
    m = json.loads(MANIFEST.read_text(encoding='utf-8'))
    m[KEY[action]] = {"folder": f"outfits/dinosaur/{action_dir(action)}", "fps": 8, "loop": loop,
                      "fallback": action_base_fallback(action),
                      "frame_durations_ms": list(durs)[:len(files)]}
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'[{action}] imported {len(files)} frames -> {dst}')


def action_dir(action):
    return {'dig': 'dig_reward'}.get(action, action)


def action_base_fallback(action):
    return {'dig': 'dig_reward'}.get(action, action)


def pick_sleep_segment(files):
    """取完全躺平的连续中段做睡眠循环。"""
    segs = []
    for f in files:
        a = np.asarray(Image.open(f).convert('RGBA'))
        s = a[..., 3] > 128
        ys, _ = np.where(s)
        segs.append(ys.max() - ys.min() + 1)
    arr = np.array(segs)
    sitting = np.median(arr[:3] + arr[-3:])
    lying = arr < sitting * 0.75
    idx = [i for i, v in enumerate(lying) if v]
    if len(idx) >= 8:
        lo, hi = idx[0], idx[-1]
        chosen = files[lo:hi+1]
        print(f'[sleep] 躺平段 帧{lo}~{hi} 共{len(chosen)}帧')
        return chosen
    print('[sleep] 未检出足够躺平帧，回退全段')
    return files


def register(out):
    import cv2
    for _ in range(2):
        s = out[..., 3] > 128
        ys, xs = np.where(s)
        top, bot = ys.min(), ys.max()
        band = s[top + int((bot - top) * 0.85):]
        bys, bxs = np.where(band)
        dx = PAW_CX - bxs.mean()
        dy = BOTTOM_ROW - bot
        if abs(dx) < 0.3 and abs(dy) < 0.3:
            break
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        out = cv2.warpAffine(out, M, (CANVAS, CANVAS), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out


def verify(action):
    import cv2
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    code = f'''
import os, copy, json, time as _t
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import numpy as np, cv2
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage
from PIL import Image
import pet
import petpet.app.pet_window as pw
from scipy import ndimage

app = QApplication([])
state = copy.deepcopy(pet.DEFAULT_STATE)
state.update({{"pet_id": "lunch_meat", "x": 100, "y": 100}})
state["owned_outfits"] = ["dinosaur_suit"]
state["equipped_outfit"] = "dinosaur_suit"
w = pet.PetWindow(state)
w.resize(190, 160)
real = pw.time.monotonic
t = [50.0]
pw.time.monotonic = lambda: t[0]
for _ in range(50):
    app.processEvents()

def to_arr(img):
    buf = img.constBits(); buf.setsize(img.sizeInBytes())
    return np.frombuffer(buf, np.uint8).reshape(img.height(), img.width(), 4)
def blob(arr):
    mm = arr[..., 3] > 60
    if not mm.any(): return None
    lab, n = ndimage.label(mm)
    k = int(np.argmax(ndimage.sum(mm, lab, range(1, n+1))))
    sl = ndimage.find_objects(lab == k+1)[0]
    sub = mm[sl[0].start:sl[0].stop, sl[1].start:sl[1].stop]
    ys, xs = np.where(sub)
    return xs.mean()+sl[1].start, ys.max()+sl[0].start, int(sub.sum())
def grab():
    for _ in range(20):
        app.processEvents()
        b = blob(to_arr(w.grab().toImage().convertToFormat(QImage.Format_ARGB32)).copy())
        if b is not None: return b
        _t.sleep(0.05)
    return None

idle = grab()
w.trigger_animation("TRIGGERNAME")
pw.time.monotonic = lambda: 50.001
f0 = grab()
print("IDLE|%.2f|%d|%d" % idle)
print("F0|%.2f|%d|%d|%.4f" % (f0[0], f0[1], f0[2], f0[2]/idle[2]))
pw.time.monotonic = real
'''
    code = code.replace('TRIGGERNAME', action_base_fallback(action))
    r = sh(['python', '-c', code], timeout=300)
    print(f'[{action}] verify:', (r.stdout or '').strip().replace('\n', '  '), (r.stderr or '')[:200])


if __name__ == '__main__':
    stage, action = sys.argv[1], sys.argv[2]
    if stage == 'gen':
        gen(action)
    elif stage == 'extract':
        extract(action)
    elif stage == 'import':
        import_(action)
    elif stage == 'verify':
        verify(action)
    elif stage == 'all':
        rep = None
        try:
            gen(action)
            rep = extract(action)
            if rep['head_swing'] < 0.20 and rep['iou_min'] > 0.55:
                import_(action)
                verify(action)
                print(f'[{action}] ✓ 完成')
            else:
                print(f'[{action}] ✗ 审计未过，跳过导入', rep)
        except Exception as e:
            print(f'[{action}] ✗ 异常: {e}')
