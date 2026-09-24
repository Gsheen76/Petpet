"""存档一键备份（2026-09-11）：把核心玩家数据打包成 zip。

备份范围 = 进度/设置/聊天记忆/头像/配额状态；**刻意排除
``config.json``**（内含 API Key，导出副本可能被分享）。备份文件名
带时间戳，``backups/`` 目录滚动保留最近 ``KEEP`` 份。
"""

from __future__ import annotations

import glob
import os
import time
import shutil
import tempfile
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


def _is_restorable(name: str) -> bool:
    """文件名是否命中备份模式（memory*.json 等通配也接受）。"""
    import fnmatch

    return any(fnmatch.fnmatch(name, pat) for pat in BACKUP_PATTERNS)


def inspect_backup_zip(zip_path: str) -> list[str]:
    """列出备份包内可还原的文件；白名单外/带路径条目一律拒绝。

    校验先于任何写入：fnmatch 的 ``*`` 可跨分隔符，目录穿越条目
    （如 ``memory-../../evil.json``）在这里拦下，restore 只处理已
    验证的平铺文件名。
    """
    with zipfile.ZipFile(zip_path) as bundle:
        names = [n for n in bundle.namelist() if not n.endswith("/")]
    unknown = sorted(n for n in names if not _is_restorable(n))
    if unknown:
        raise ValueError(f"备份包含未知文件，拒绝还原：{unknown[:3]}")
    bad_paths = sorted(
        n for n in names
        if "/" in n or n.replace("\\", "/") != n or n.startswith("..")
    )
    if bad_paths:
        raise ValueError(f"备份包含异常路径条目，拒绝还原：{bad_paths[:3]}")
    return names


def restore_backup_zip(zip_path: str, data_dir: str | None = None) -> list[str]:
    """把备份包内容还原到数据目录（覆盖同名文件），返回还原清单。

    仅接受备份模式内的文件名（防伪造包写入任意路径）；调用方应先
    做一次安全快照（backup_now）再调用。

    原子化（2026-09-23 低⑭）：先整体解包进 staging 临时目录，再逐
    文件「写临时+os.replace」替换；替换阶段任何失败按回滚副本恢复
    全部已动文件——中途失败不再留下新旧混合态。
    """
    root = data_dir or DATA_DIR
    names = inspect_backup_zip(zip_path)
    root_abs = os.path.abspath(root)
    staging = None
    rollback = None
    try:
        staging = tempfile.mkdtemp(prefix="petpet_restore_stage_")
        rollback = tempfile.mkdtemp(prefix="petpet_restore_prev_")
        staged = []
        with zipfile.ZipFile(zip_path) as bundle:
            for name in names:
                staged_path = os.path.abspath(os.path.join(staging, name))
                if os.path.dirname(staged_path) != os.path.abspath(staging):
                    raise ValueError(f"异常路径条目：{name}")
                with bundle.open(name) as src, open(staged_path, "wb") as dst:
                    dst.write(src.read())
                staged.append((name, staged_path))
        # 换入阶段：先存回滚副本，再逐文件原子替换；还原前不存在的
        # 文件记入 created_new，回滚时删除（不留新增残留）
        created_new = []
        tmp_current = None
        try:
            for name, staged_path in staged:
                target = os.path.abspath(os.path.join(root, name))
                if os.path.dirname(target) != root_abs:
                    raise ValueError(f"异常路径条目：{name}")
                if os.path.exists(target):
                    prev = os.path.join(rollback, name)
                    shutil.copyfile(target, prev)
                else:
                    created_new.append(target)
                tmp_target = target + ".petpet_restore.tmp"
                tmp_current = tmp_target
                shutil.copyfile(staged_path, tmp_target)
                os.replace(tmp_target, target)
                tmp_current = None
        except BaseException:
            if tmp_current is not None:
                try: os.unlink(tmp_current)
                except OSError: pass
            for target in created_new:
                try: os.unlink(target)
                except OSError: pass
            if rollback is not None:
                for name in os.listdir(rollback):
                    try:
                        os.replace(
                            os.path.join(rollback, name),
                            os.path.abspath(os.path.join(root, name)),
                        )
                    except OSError:
                        pass  # 回滚尽力而为；调用方仍有事前安全快照兜底
            raise
        return names
    finally:
        for folder in (staging, rollback):
            if folder and os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
