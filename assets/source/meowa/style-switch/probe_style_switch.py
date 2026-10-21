"""风格切换真平台探针:经典/新装两态真实渲染对照 + 解析链核验。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage

from petpet.app import pets
from petpet.app.state import ensure_state_schema, set_pet_style


def main():
    app = QApplication([])
    state = ensure_state_schema({}, "Probe", str)

    # 解析链核验(真实清单)
    classic_idle = pets.pet_asset_path("lunch_meat", "desktop", "idle")
    new_idle = pets.pet_asset_path(
        "lunch_meat", "desktop", "idle", style="new")
    classic_avatar = pets.pet_avatar_path("lunch_meat", style="classic")
    new_avatar = pets.pet_avatar_path("lunch_meat", style="new")
    print("[resolve] classic idle:", classic_idle)
    print("[resolve] new idle:", new_idle)
    print("[resolve] classic avatar:", classic_avatar)
    print("[resolve] new avatar:", new_avatar)
    assert "desktop_new" in new_idle and "desktop_new" not in classic_idle
    assert new_idle and os.path.isfile(new_idle)
    assert "avatar_classic" in classic_avatar and classic_avatar != new_avatar

    import pet  # noqa: F401 -- PetWindow 依赖 pet.py 注入
    from petpet.app.pet_window import PetWindow
    window = PetWindow(state)
    window.refresh_pet_assets("lunch_meat")
    print("[classic] manifest:", window._desktop_animation_manifest_path())
    assert "desktop_new" not in window._desktop_animation_manifest_path()
    img_classic = QImage(window.grab())

    set_pet_style(state, "lunch_meat", "new")
    window.refresh_pet_assets("lunch_meat")
    print("[new] manifest:", window._desktop_animation_manifest_path())
    assert "desktop_new" in window._desktop_animation_manifest_path()
    img_new = QImage(window.grab())

    # 两态渲染必须互异
    w, h = img_classic.width(), img_classic.height()
    diff = sum(
        1 for y in range(0, h, 4) for x in range(0, w, 4)
        if img_classic.pixel(x, y) != img_new.pixel(x, y)
    )
    total = (w // 4) * (h // 4)
    print(f"[render] sampled diff {diff}/{total} = {diff/total:.1%}")
    assert diff / total > 0.02, "两风格渲染应明显互异"

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_compare.png")
    canvas = QImage(w * 2 + 12, h, QImage.Format_ARGB32)
    canvas.fill(0xFFFDF3E8)
    from PyQt5.QtGui import QPainter
    painter = QPainter(canvas)
    painter.drawImage(0, 0, img_classic)
    painter.drawImage(w + 12, 0, img_new)
    painter.end()
    canvas.save(out)
    print("[saved]", out)

    window.close()
    print("PROBE PASS")


if __name__ == "__main__":
    main()
