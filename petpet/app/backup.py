"""存档一键备份（2026-09-11）：把核心玩家数据打包成 zip。

备份范围 = 进度/设置/聊天记忆/头像/配额状态；**刻意排除
``config.json``**（内含 API Key，导出副本可能被分享）。备份文件名
带时间戳，``backups/`` 目录滚动保留最近 ``KEEP`` 份。
"""

from __future__ import annotations

import glob
import os
import time
import zipfile

from petpet.app.paths import DATA_DIR

# 按需备份的玩家数据（不含 config.json——密钥不进可导出的副本）。
BACKUP_PATTERNS = (
    "pet_state.json",
    "pet_settings.json",
    "memory*.json",
    "player_avatar.png",
    "chat_quota_state.json",
)
KEEP = 5


def backup_dir(data_dir: str | None = None) -> str:
    """本地备份目录（在数据目录下，自动创建）。"""
    path = os.path.join(data_dir or DATA_DIR, "backups")
    os.makedirs(path, exist_ok=True)
    return path


def create_backup_zip(dest_path: str, data_dir: str | None = None) -> int:
    """把核心存档打包进 dest_path，返回实际写入的文件数。"""
    root = data_dir or DATA_DIR
    names: list[str] = []
    for pattern in BACKUP_PATTERNS:
        for path in sorted(glob.glob(os.path.join(root, pattern))):
            names.append(os.path.basename(path))
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(os.path.join(root, name), arcname=name)
    return len(names)


def rotate_backups(keep: int = KEEP, data_dir: str | None = None) -> list[str]:
    """只保留最近 keep 份备份，返回被删除的文件路径列表。"""
    folder = backup_dir(data_dir)
    zips = sorted(glob.glob(os.path.join(folder, "petpet-backup-*.zip")))
    doomed = zips[:-keep] if keep > 0 else zips
    removed = []
    for path in doomed:
        try:
            os.remove(path)
            removed.append(path)
        except OSError:
            pass
    return removed


def backup_now(data_dir: str | None = None) -> tuple[str, int]:
    """一键备份：写入滚动目录并轮转，返回 (路径, 文件数)。"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(backup_dir(data_dir), f"petpet-backup-{stamp}.zip")
    count = create_backup_zip(path, data_dir)
    rotate_backups(data_dir=data_dir)
    return path, count
