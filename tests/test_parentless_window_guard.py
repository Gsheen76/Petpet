# -*- coding: utf-8 -*-
"""无父顶层原生窗保活守卫（2026-09-24 崩溃家族根治配套）。

规则（绝对、零豁免）：petpet 里任何设 Qt.Tool 窗口标志的顶层
QWidget 子类必须继承 petpet.ui.common.KeepAliveTopLevelWindow——
构造即入类级保活表、closeEvent 出表，杜绝「弃引用→GC 连 C++ 一起
销毁→在途窗口事件投递到已释放接收者」的 AV 崩溃家族
（pythonw.exe 20876/49612.dmp 等，2026-09-13 起多案）。

本测试静态扫描源码：新增无父浮窗类忘记继承基类 → CI 直接失败，
规矩不再依赖人工记忆。
"""
import importlib
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[1]


def _qt_tool_classes():
    """扫描 petpet/**.py：返回 (module_name, class_name) 列表。"""
    hits = []
    for path in sorted((REPO / "petpet").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        module = ".".join(path.with_suffix("").parts[len(REPO.parts):])
        for match in re.finditer(r"class (\w+)\(([^)]+)\):", text):
            name, bases = match.groups()
            if "QWidget" not in bases:
                continue  # 基类自身/非窗体类不扫
            body = text[match.end():match.end() + 2500].split("\nclass ")[0]
            if "Qt.Tool" in body:
                hits.append((module, name))
    return hits


class ParentlessWindowGuardTests(unittest.TestCase):
    def test_every_qt_tool_window_inherits_keepalive_base(self):
        from petpet.ui.common import KeepAliveTopLevelWindow

        classes = _qt_tool_classes()
        self.assertTrue(classes, "扫描器失效：至少应发现桌面气泡类")
        offenders = []
        for module_name, class_name in classes:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            if not issubclass(cls, KeepAliveTopLevelWindow):
                offenders.append(f"{module_name}.{class_name}")
        self.assertEqual(
            offenders, [],
            "Qt.Tool 顶层窗必须继承 KeepAliveTopLevelWindow（保活基类）："
            + ", ".join(offenders),
        )

    def test_base_registers_and_discards(self):
        import gc
        import weakref

        from PyQt5 import sip
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QApplication

        from petpet.ui.common import KeepAliveTopLevelWindow

        app = QApplication.instance() or QApplication([])

        class _Probe(KeepAliveTopLevelWindow):
            pass

        _Probe.CLOSE_GRACE_MS = 20  # 测试用短缓冲（生产 2500ms）

        probe = _Probe()
        ref = weakref.ref(probe)
        self.assertIn(probe, _Probe._keep_alive)
        del probe
        gc.collect()
        QApplication.processEvents()
        self.assertIsNotNone(ref(), "基类必须保活无引用实例")
        self.assertFalse(sip.isdeleted(ref()))
        ref().close()
        QApplication.processEvents()
        # 延迟出表（2026-09-28 15:56 第六案加固）：close 后仍在表内
        # （缓冲在途窗口事件），缓冲期过后才出表。
        self.assertIn(
            ref(), _Probe._keep_alive, "close 当场出表会同步析构——必须缓冲"
        )
        deadline = QTimer()
        deadline.setSingleShot(True)
        fired = []
        deadline.timeout.connect(lambda: fired.append(1))
        deadline.start(60)
        while not fired:
            QApplication.processEvents()
        self.assertNotIn(ref(), _Probe._keep_alive, "缓冲期后必须出表")


if __name__ == "__main__":
    unittest.main()


class QMenuAdoptionGuardTests(unittest.TestCase):
    """裸 QMenu 守卫（2026-09-25 家族第 6 例后）：无父 QMenu 必须收养
    （adopt_window）或持父/持久引用——否则关闭即弃引用重现闪退族。"""

    def test_bare_qmenu_is_adopted_parented_or_persistent(self):
        offenders = []
        files = [REPO / "pet.py"] + sorted((REPO / "petpet").rglob("*.py"))
        for path in files:
            if path.name == "common.py":
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if "QMenu(" not in line:
                    continue
                if "parent" in line:
                    continue  # 带父
                if "=" in line and "self." in line.split("=")[0]:
                    continue  # 持久引用（self.menu 等复用）
                window = chr(10).join(lines[index:index + 8])
                if "adopt_window" in window:
                    continue
                offenders.append(f"{path.name}:{index + 1}")
        self.assertEqual(offenders, [], "未收养的裸 QMenu：" + ", ".join(offenders))
