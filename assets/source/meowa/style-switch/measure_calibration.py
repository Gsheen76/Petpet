"""风格切换导入标定:量经典/新装 idle 的画布与体高占比,算 manifest scale。"""
from PIL import Image
import numpy as np
import glob
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
RUNTIME = os.path.join(ROOT, 'assets', 'runtime', 'pets')
SOURCE = os.path.join(ROOT, 'assets', 'source', 'meowa', 'style-switch')


def body(p):
    im = Image.open(p).convert('RGBA')
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 50)
    if len(ys) == 0:
        return im.size, 0, 0
    return im.size, ys.max() - ys.min() + 1, xs.max() - xs.min() + 1


for pet in ('lunch_meat', 'ice_cream'):
    frames = sorted(glob.glob(os.path.join(RUNTIME, pet, 'desktop', 'animations', 'idle', '*.png')))
    classic = frames[0]
    size, h, w = body(classic)
    frac = h / size[1]
    print(pet, 'classic idle frame0', size, 'body h/w', h, w, 'h/canvas', round(frac, 3))

    src_frames = sorted(glob.glob(os.path.join(SOURCE, pet, 'idle_v1', 'frames', '*.png')))
    size2, h2, w2 = body(src_frames[0])
    frac2 = h2 / size2[1]
    scale = frac / frac2
    print('  new frame0', size2, 'body h/w', h2, w2, 'h/canvas', round(frac2, 3), '-> manifest scale', round(scale, 4))

    # 导入 runtime:desktop_new/animations/idle/ + poses/idle.png(帧0)
    dst_anim = os.path.join(RUNTIME, pet, 'desktop_new', 'animations', 'idle')
    os.makedirs(dst_anim, exist_ok=True)
    poses_dir = os.path.join(RUNTIME, pet, 'desktop_new', 'poses')
    os.makedirs(poses_dir, exist_ok=True)
    for i, src in enumerate(src_frames):
        shutil.copyfile(src, os.path.join(dst_anim, f'{i:03d}.png'))
    shutil.copyfile(src_frames[0], os.path.join(poses_dir, 'idle.png'))
    print('  imported', len(src_frames), 'frames + pose ->', os.path.join(pet, 'desktop_new'))
