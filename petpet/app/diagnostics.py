# -*- coding: utf-8 -*-
"""后台诊断日志（2026-09-25 用户要求：总是事后修补，先把记录做好）。

三层记录：
1. **轮转事件日志** ``diag.log``（JSONL，本地时间戳）：菜单/面板开关等
   关键动作埋点——崩溃发生时能看到「崩前在干什么」。
2. **异常拦截**：替换 ``sys.excepthook`` / ``threading.excepthook``——
   PyQt5 的规则是槽/paintEvent 内未捕获异常默认 qFatal 杀进程；一旦
   excepthook 被替换，PyQt5 改为调它后**继续运行**。曾经的
   「paintEvent 里 UnboundLocalError = exit 127 无声死」从此变成
   日志里一条带完整栈的 error 事件。
3. 原生 AV 仍由 faulthandler 记 ``crash_dump.log``（既有机制不动）。

日志上限 256KB×2 份轮转，写失败静默（诊断绝不拖垮主程序）。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback

LOG_MAX_BYTES = 256 * 1024
_ENABLED = {"on": True}


def _log_path():
    from petpet.app.paths import DATA_DIR

    return os.path.join(DATA_DIR, "diag.log")


def _rotate_if_needed(path: str) -> None:
    try:
        if os.path.getsize(path) < LOG_MAX_BYTES:
            return
        prev = path + ".1"
        if os.path.exists(prev):
            os.remove(prev)
        os.replace(path, prev)
    except OSError:
        pass


def log_event(name: str, **fields) -> None:
    """追加一条 JSONL 事件（本地时间戳）。诊断入口，永不抛异常。"""
    if not _ENABLED["on"]:
        return
    try:
        entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": str(name)}
        entry.update(fields)
        path = _log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _rotate_if_needed(path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _log_exception(kind: str, exc_type, exc, tb) -> None:
    log_event(
        "unhandled_exception",
        where=kind,
        exc=f"{exc_type.__name__}: {exc}",
        stack="".join(traceback.format_exception(exc_type, exc, tb)).strip(),
    )


def install_excepthooks() -> None:
    """装全局异常拦截：记录且不杀进程（PyQt5 见模块 docstring）。"""
    prev_sys = sys.excepthook
    prev_thread = threading.excepthook

    def _sys_hook(exc_type, exc, tb):
        _log_exception("main", exc_type, exc, tb)
        try:
            prev_sys(exc_type, exc, tb)
        except Exception:
            pass

    def _thread_hook(args):
        _log_exception(
            f"thread:{getattr(args.thread, 'name', '?')}",
            args.exc_type, args.exc_value, args.exc_traceback,
        )
        try:
            prev_thread(args)
        except Exception:
            pass

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
    log_event("diagnostics_installed", python=sys.version.split()[0])
