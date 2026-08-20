# Task 7: Active Pet Switching Design

## Scope

Continue the multi-pet implementation from Tasks 1-6 in the existing
`home-scene-system` worktree. Do not redo or reorganize prior task changes.
Task 7 coordinates active-pet switching across the tray application, desktop
pet window, home scene, chat, and shop surfaces.

## Transaction Boundary

`TrayApp.set_active_pet(pet_id: str) -> dict` is the only application-level
transaction that may change `state["active_pet_id"]`.

The transaction performs these steps in order:

1. Validate that the pet ID exists in the registry and is present in
   `owned_pet_ids`. On failure, return `ok=False` without changing state,
   saving, or refreshing surfaces.
2. Capture the current active pet profile.
3. Bind the requested pet profile while preserving shared player progress.
4. Call `save_state(state)` exactly once.
5. Refresh desktop assets, the home controller and assets, chat memory/name,
   and any open shop, records, or achievements surfaces.
6. Update the AI pet name, tray tooltip, and desktop repaint.
7. If a Qt surface has already been deleted, clear its reference after the
   state has been saved. The next open operation recreates it lazily.

`PetWindow.set_active_pet` remains a compatibility forwarder to the tray
callback. It must not independently mutate the active profile or duplicate
the transaction. The shop's post-purchase auto-switch uses the same callback.

## Component Contracts

### PetWindow

`PetWindow.set_pet_name(value)` normalizes the name, writes it to the active
pet profile, updates that pet's chat memory, persists the state, and refreshes
the visible chat name. It does not switch pets.

Desktop positions are captured under the current pet profile's
`desktop_position` during close/restore paths.

### HomeSceneWindow

`HomeSceneWindow.refresh_active_pet()` reads the active pet ID from shared
state, resets the controller, restores that pet's exact `home_position` when
present, and reloads home assets. It must not replace an explicitly saved
position with the default entry position.

Home controller movement and exit paths save `home_position` under the active
pet profile.

### ChatWindow

`ChatWindow.set_pet_id(pet_id)` switches the memory file and visible name for
the selected pet. While a message is streaming, it returns `False` and leaves
the current conversation unchanged.

### Live surfaces

The tray transaction refreshes live surfaces through one safe helper. A
`RuntimeError` from a deleted Qt object clears only that surface reference;
the already-saved state remains valid and the transaction still succeeds.

## Return Values

Successful switching returns a dictionary containing `ok=True`, the selected
`pet_id`, and a user-facing message. Invalid or unowned IDs return
`ok=False`, the requested `pet_id`, and an explanatory message.

## Testing and Verification

The red phase runs the Task 7 boundary tests before production changes. The
focused suite covers:

- exact home-position restoration;
- desktop/home/chat/shop/records synchronization;
- preservation of shared pet coins;
- rejection of unowned pets without saving;
- cleanup of already-closed surfaces;
- independent names and chat memories;
- shop purchase auto-switching through the tray callback;
- per-pet desktop and home position persistence.

Verification runs the focused boundary suite, the related live-window tests,
then the full `python -m pytest -q` suite. The final diff is checked to ensure
that Task 1-6 changes are preserved and unrelated main-worktree changes are
not included.
