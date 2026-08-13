# Home Pet Commands and Affection Growth Design

Date: 2026-08-13
Status: approved

## Goal

Move the home pet's commands into the home window header, separate desktop and
home autonomy, add passive affection growth and zero-stat warnings, and improve
treasure and speech-bubble presentation without changing existing save data.

## Home header and interaction menu

The home header is ordered as `属性 | 商店 | 互动 | 装修 | 退出`.

- `属性` opens the existing property panel.
- `商店` opens the existing shop.
- `互动` toggles a warm rounded dropdown containing `抚摸`, `喂食`, `玩耍`,
  and `睡觉`.
- Clicking elsewhere, entering decoration mode, or closing the home closes the
  dropdown.
- Right-clicking inside the home no longer opens the desktop shortcut menu.
- Left-click movement remains unchanged.

When any of hunger, mood, or energy is exactly zero, a red notification dot is
drawn on the home pet, the header interaction button, and every dropdown action
that can restore the zero stat. Hunger maps to feeding; mood maps to petting,
feeding, and playing; energy maps to sleeping. Dots disappear as soon as the
relevant stat becomes greater than zero.

## Desktop and home autonomy

The desktop pet no longer selects random walking behavior. Dragging, direct
interactions, state-driven sleep, speech, and treasure behavior remain.

The home pet chooses a random walkable floor destination every 12–25 seconds
only while idle, visible, not decorating, not sleeping, and without a user
movement command. Direct movement, interaction, decoration, or sleep cancels
the current autonomous-walk deadline and schedules a fresh one afterward.

## Affection balance

Passive affection accrues only while the application is actively running. Its
base rate is 0.01 affection per second, displayed as 0.60 per minute. For each
stat at zero the current rate is multiplied by 0.5, producing 0.30, 0.15, and
0.075 per minute for one, two, and three zero stats. A persisted fractional
buffer prevents sub-point growth from being lost. Affection may exceed the
ordinary pet level.

Affection required for the next level is:

`min(200, 30 + 10 * (affection_level - 1))`

Interaction gains and independent cooldowns are:

| Interaction | Affection | Cooldown |
|---|---:|---:|
| Petting | 1 | 60 seconds |
| Feeding | 4 | 8 minutes |
| Playing | 5 | 6 minutes |
| Manual sleep | 3 | 15 minutes |
| Fetch catch | 2 | 5 minutes |
| Successful chat | 1 | 3 minutes |
| Wake shake | 1 | 5 minutes |

The property panel shows both passive EXP per minute and the current passive
affection per minute, including zero-stat penalties.

## Desktop reminders

The clickable hunger and play request bubbles are removed. Hunger, mood, and
energy use spoken reminders below 20, each with an independent ten-minute
cooldown. If several stats need attention, priority is energy, then hunger,
then mood. Energy may still initiate automatic sleep.

## Treasure and mini-game rewards

New treasure rewards double to 10–20, 24–40, 50–80, and 120–200 Pet coins.
Existing pending rewards are not retroactively doubled. Coin Catch values
double from 1/2 to 2/4, and Lucky Paws round rewards double from 5/10/15 to
10/20/30.

The pending treasure control becomes a small warm circular bubble directly
above the desktop pet. While visible, it suppresses ordinary reminders,
proactive speech, and other speech bubbles. Opening the desktop right-click
menu temporarily hides it; closing the menu restores it if the reward remains
pending. The treasure bubble is desktop-only.

## Speech bubble anchor

Speech bubbles retain the pet's head-center as a target anchor. The bubble body
may clamp to the screen edge, but its lower triangle moves within the rounded
card's safe horizontal range and always points at the current pet position.
Position and triangle geometry refresh while the pet moves or is dragged.

## Architecture

- `progression.py`: affection rates and thresholds, zero-stat mappings,
  interaction gains, and doubled reward rules.
- `home_pet.py`: deterministic autonomous-walk scheduling primitives.
- `home_scene.py`: header buttons, interaction dropdown, red dots, and removal
  of the home right-click menu.
- `pet.py`: desktop autonomy split, reminder cooldowns, passive affection tick,
  circular treasure bubble, menu mutual exclusion, dynamic speech pointer, and
  property-panel rates.
- `minigames.py`: visible doubled reward values.

## Persistence and compatibility

Existing state remains valid. Migration adds only a passive affection buffer
and per-stat reminder timestamps with safe defaults. An already pending
treasure retains its stored amount. No user name, level, currency, furniture,
avatar, settings, or chat memory is reset.

## Verification

Implementation follows test-first development. Focused coverage includes
affection formulas and migration, zero-stat action mapping, interaction gains,
reward values, home dropdown behavior, autonomous-walk exclusions, reminder
cooldowns, treasure/speech mutual exclusion, and triangle anchoring. Completion
requires focused tests and a fresh `pytest -q` run.
