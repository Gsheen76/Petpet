# -*- coding: utf-8 -*-
"""素材年龄普查:按功能组统计 runtime 素材的 git 最后改动时间。"""
import os
import subprocess
from collections import defaultdict

ROOT = 'assets/runtime'
SEP = chr(92)
groups = defaultdict(list)
for dirpath, _, files in os.walk(ROOT):
    for f in files:
        rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(SEP, '/')
        parts = rel.split('/')
        if parts[0] == 'ui':
            key = 'ui/' + parts[1]
        elif parts[0] == 'pets':
            key = 'pets/' + parts[1] + ('/desktop_new' if 'desktop_new' in rel else '')
        else:
            key = parts[0]
        groups[key].append(rel)


def last_date(rel):
    r = subprocess.run(
        ['git', 'log', '-1', '--format=%ad', '--date=format:%Y-%m-%d',
         '--', 'assets/runtime/' + rel],
        capture_output=True, text=True)
    return r.stdout.strip() or '?'


rows = []
for key in sorted(groups):
    files = groups[key]
    dates = [last_date(f) for f in files]
    old = sum(1 for d in dates if d < '2026-09-28')
    rows.append((key, len(files), min(dates), max(dates), old))

print('%-32s %5s %11s %11s %9s' % ('功能组', '件数', '最早', '最近', '09-28前'))
for key, n, mn, mx, old in sorted(rows, key=lambda x: x[2]):
    print('%-32s %5d %11s %11s %9d' % (key, n, mn, mx, old))
