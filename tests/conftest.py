"""Keep tests isolated from the player's real local Petpet profile."""

import atexit
import os
import shutil
import sys
import tempfile


_TEST_LOCAL_APP_DATA = tempfile.mkdtemp(prefix="petpet-tests-")
os.environ["LOCALAPPDATA"] = _TEST_LOCAL_APP_DATA
atexit.register(shutil.rmtree, _TEST_LOCAL_APP_DATA, ignore_errors=True)


def pytest_sessionfinish(session, exitstatus):
    """收尾清理（2026-09-29）：显式关停/销毁模块级常开音频通道——
    若活到解释器退出阶段会在 QApplication 已析构后再被 GC 析构
    C++ 对象（全量收尾段错误实证）。"""
    try:
        import petpet.app.sounds as sounds

        sounds._shutdown_push_channel()
    except Exception:
        pass
    # 跳过解释器退出清理（PyQt 测试套件惯例）：跨文件组合的退出序
    # 段错误（1018 全绿后 C 对象在 QApplication 析构后又被 GC——
    # 2026-09-29 实证单文件/半集均绿、全集组合崩；根因排查立项）。
    # 所有测试已完成，硬退出不影响判定。
    # 2026-10-03 假阴性教训：os._exit 抢在 terminalreporter 打印
    # 汇总之前，失败列表被吞（grep FAILED 找不到行）——三天里
    # 3 个真失败一直被当「全量零失败」。这里自己打一行判定摘要。
    try:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        stats = getattr(reporter, "stats", {}) if reporter else {}
        passed = len(stats.get("passed", []))
        failed = len(stats.get("failed", []))
        errors = len(stats.get("error", []))
        print(
            f"\nPYTEST VERDICT: {passed} passed"
            f"{f', {failed} FAILED' if failed else ''}"
            f"{f', {errors} ERROR' if errors else ''}",
            flush=True,
        )
    except Exception:
        pass
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    # os._exit 跳过 atexit——顶部注册的临时目录清理手动补上
    try:
        shutil.rmtree(_TEST_LOCAL_APP_DATA, ignore_errors=True)
    except Exception:
        pass
    os._exit(exitstatus)
