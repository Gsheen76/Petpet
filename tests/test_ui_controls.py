import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import pet


ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


def test_root_reexports_package_control_classes():
    from petpet.ui.controls import (
        StepperControl,
        ThreeLevelSlider,
        ToggleSwitch,
    )

    assert pet.ToggleSwitch is ToggleSwitch
    assert pet.StepperControl is StepperControl
    assert pet.ThreeLevelSlider is ThreeLevelSlider


def test_control_implementations_are_owned_by_package_module():
    root_source = (ROOT / "pet.py").read_text(encoding="utf-8")
    package_source = (
        ROOT / "petpet" / "ui" / "controls.py"
    ).read_text(encoding="utf-8")
    for name in ("ToggleSwitch", "StepperControl", "ThreeLevelSlider"):
        assert f"class {name}" not in root_source
        assert f"class {name}" in package_source


def test_three_level_slider_still_clamps_to_named_positions():
    from petpet.ui.controls import ThreeLevelSlider

    control = ThreeLevelSlider(("文静", "适中", "活泼"))
    try:
        control.setValue(99)
        assert control.value() == 2
        assert [button.isChecked() for button in control.level_buttons] == [
            False,
            False,
            True,
        ]
    finally:
        control.close()
