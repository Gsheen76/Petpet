import re
import json
from pathlib import Path

import pet
from version import VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_public_version_has_one_source_of_truth():
    assert VERSION == "1.6.0"
    assert pet.VERSION == VERSION


def test_readme_and_release_notes_match_public_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release_notes = (
        ROOT / "docs" / f"RELEASE_NOTES_v{VERSION}.md"
    ).read_text(encoding="utf-8")
    assert f"当前版本：`v{VERSION}`" in readme
    assert f"## v{VERSION} 更新亮点" in readme
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
    assert re.search(r'^VERSION = "1\.6\.0"$', (
        ROOT / "version.py"
    ).read_text(encoding="utf-8"), re.MULTILINE)


def test_game_knowledge_matches_public_version():
    knowledge = json.loads(
        (ROOT / "assets/runtime/knowledge/game_knowledge.json").read_text(
            encoding="utf-8"
        )
    )
    assert knowledge["version"] == VERSION


def test_release_ignores_local_debug_and_wrangler_cache():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored_paths = {
        line.strip()
        for line in gitignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "debug-chat-window.png" in ignored_paths
    assert "debug-pet-menu.png" in ignored_paths
    assert "cloudflare-worker/.wrangler/" in ignored_paths
    assert ".tools/" in ignored_paths


def test_readme_documents_one_click_release_and_v160_assets():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".\\scripts\\release.ps1 -Version 1.6.0" in readme
    for asset in (
        "Petpet.exe",
        "Petpet-v1.6.0-windows.zip",
        "Petpet-v1.6.0-macOS-arm64.zip",
        "Petpet-v1.6.0-macOS-intel.zip",
    ):
        assert asset in readme
    assert "默认免费文字聊天" in readme
    assert "个人 GLM-4.6V-Flash" in readme


def test_readme_documents_multi_pet_behavior():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "宠物" in readme
    assert "午餐肉" in readme
    assert "冰淇淋" in readme
    assert "active_pet_id" not in readme


def test_runtime_props_are_packaged_on_both_platforms():
    for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
        spec = (
            ROOT / "packaging" / filename
        ).read_text(encoding="utf-8")
        assert '(str(runtime_assets_root), "assets/runtime")' in spec
    assert (
        ROOT / "assets" / "runtime" / "props" / "fetch_ball.png"
    ).is_file()


def test_packaging_uses_independent_decorations_not_outfit_combinations():
    for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
        spec = (
            ROOT / "packaging" / filename
        ).read_text(encoding="utf-8")
        assert '(str(runtime_assets_root), "assets/runtime")' in spec
        assert "source_assets_root" not in spec
        assert "poses/outfits" not in spec
