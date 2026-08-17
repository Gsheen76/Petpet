import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "petpet"
LEGACY_ROOT_MODULES = {
    "app_paths",
    "buddy_ai",
    "decoration_renderer",
    "game_knowledge",
    "home_pet",
    "home_scene",
    "minigames",
    "progression",
    "progression_ui",
    "scene_system",
}


def _imported_top_levels(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or "").split(".", 1)[0])
    return names


def test_package_modules_do_not_import_legacy_root_facades():
    violations = {}
    for path in PACKAGE_ROOT.rglob("*.py"):
        imported = _imported_top_levels(path) & LEGACY_ROOT_MODULES
        if imported:
            violations[str(path.relative_to(ROOT))] = sorted(imported)

    assert violations == {}
