# Task 3 Report: 卡片布局与强化文本

## Scope

- Implemented the Task 3 brief in `petpet/progression/core.py` and
  `petpet/progression/ui.py`.
- Added/updated behavioral coverage in the three specified progression/UI
  test modules.
- Did not modify the Task 1 formula values, purchase eligibility, upgrade
  prices, save data, or image asset files.

## RED evidence

Test-first changes covered: pet descriptions do not wrap; the petting effect
is exactly `每次抚摸：心情+10点` without `当前加成`; sleep text uses signed
values; free pet/home prices use the gift role and `免费赠送`; furniture and
upgrade cards have a uniform fixed height; and upgrade effects are rendered
directly from `progression.upgrade_description()`.

Command run before implementation:

```text
python -m pytest -q tests/test_progression.py tests/test_progression_ui.py tests/test_progression_ui_boundary.py
```

Result: `7 failed, 74 passed in 1.86s`.

The failures were the expected missing behavior: old restore/consume wording,
the `当前加成：` prefix, non-fixed card heights, and old free-price labels.

## GREEN evidence

Minimal implementation:

- `upgrade_description()` now owns the requested signed-text format for
  petting, feeding, playing, and sleeping; it does not alter any effect values.
- Pet descriptions explicitly disable word wrapping.
- Pet, outfit, and home-furniture price labels use `_price_tag`; zero-price
  labels display `免费赠送` with the `gift` role. Existing pet discount
  original/current/badge components remain supplied by `_price_labels`.
- Furniture cards are two-column fixed-height cards (310 px) retaining title,
  description, price, status, action, and the existing 170x112 keep-aspect
  preview. Upgrade cards are fixed at 230 px and retain title, level, summary,
  effect, and action.

Focused command:

```text
python -m pytest -q tests/test_progression.py tests/test_progression_ui.py tests/test_progression_ui_boundary.py
81 passed in 1.69s
```

Full-suite command:

```text
python -m pytest -q
609 passed in 77.30s (0:01:17)
```

## Files changed

- `petpet/progression/core.py`
- `petpet/progression/ui.py`
- `tests/test_progression.py`
- `tests/test_progression_ui.py`
- `tests/test_progression_ui_boundary.py`
- `.superpowers/sdd/2026-08-20-shop-price-assets-and-upgrade-balance/task-3-report.md`

## Commit

`feat: unify shop card presentation`

## Concerns

None. The full suite passed. Git emitted normal Windows LF-to-CRLF working-tree
warnings during diff inspection; no whitespace errors were reported by
`git diff --check`.
