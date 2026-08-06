import re
from pathlib import Path

import pet
from version import VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_public_version_has_one_source_of_truth():
    assert VERSION == "1.3.2"
    assert pet.VERSION == VERSION


def test_readme_and_release_notes_match_public_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release_notes = (
        ROOT / "docs" / f"RELEASE_NOTES_v{VERSION}.md"
    ).read_text(encoding="utf-8")
    assert f"当前版本：`v{VERSION}`" in readme
    assert release_notes.startswith(f"# Pet陪它 v{VERSION}")


def test_macos_build_uses_lightweight_version_module():
    workflow = (
        ROOT / ".github" / "workflows" / "build-macos.yml"
    ).read_text(encoding="utf-8")
    mac_spec = (
        ROOT / "packaging" / "Petpet-mac.spec"
    ).read_text(encoding="utf-8")
    assert "from version import VERSION" in workflow
    assert 'project_root / "version.py"' in mac_spec
    assert re.search(r'^VERSION = "1\.3\.2"$', (
        ROOT / "version.py"
    ).read_text(encoding="utf-8"), re.MULTILINE)


def test_runtime_props_are_packaged_on_both_platforms():
    for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
        spec = (
            ROOT / "packaging" / filename
        ).read_text(encoding="utf-8")
        assert '(str(assets_root / "props"), "assets/props")' in spec
    assert (ROOT / "assets" / "props" / "fetch_ball.png").is_file()


def test_packaging_uses_independent_decorations_not_outfit_combinations():
    for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
        spec = (
            ROOT / "packaging" / filename
        ).read_text(encoding="utf-8")
        assert '(str(assets_root / "decorations"), "assets/decorations")' in spec
        assert '(assets_root / "poses").glob("*.png")' in spec
        assert "poses/outfits" not in spec
