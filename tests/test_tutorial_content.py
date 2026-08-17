import pet
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tutorial_window_reexports_package_content():
    from petpet.ui.tutorial import TUTORIAL_PAGES

    assert pet.TutorialWindow.PAGES is TUTORIAL_PAGES
    assert len(TUTORIAL_PAGES) == 6
    assert all(len(page) == 3 for page in TUTORIAL_PAGES)


def test_tutorial_content_keeps_current_user_guidance():
    from petpet.ui.tutorial import TUTORIAL_PAGES

    combined = "\n".join(text for page in TUTORIAL_PAGES for text in page)
    assert "双击进入小屋" in combined
    assert "免费或自定义模式" in combined
    assert "最多 6 个字符" in combined


def test_tutorial_window_is_owned_by_package_module():
    from petpet.ui.tutorial import TutorialWindow

    assert pet.TutorialWindow is TutorialWindow
    root_source = (ROOT / "pet.py").read_text(encoding="utf-8")
    package_source = (
        ROOT / "petpet" / "ui" / "tutorial.py"
    ).read_text(encoding="utf-8")
    assert "class TutorialWindow" not in root_source
    assert "class TutorialWindow" in package_source
