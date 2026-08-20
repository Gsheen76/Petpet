# 图文陪伴聊天 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy text model with GLM-4.7-Flash and GLM-4.6V-Flash, and let the visual model accept one local picture per conversation turn.

**Architecture:** `buddy_ai.py` owns model normalization, image validation/thumbnail persistence and API message construction. `ChatWindow` owns the selection, preview and history presentation; it passes an image payload only for the current request. Memory stores compact metadata that points at a local thumbnail rather than image bytes.

**Tech Stack:** Python standard library (`base64`, `imghdr`, `pathlib`), PyQt5 (`QFileDialog`, `QPixmap`, `QImageReader`), unittest, pytest.

## Global Constraints

- Preserve existing user changes; never use git reset or checkout.
- Use the current worktree's `pet.py` when manually launching the source app.
- Accepted API model identifiers are exactly `glm-4.7-flash` and `glm-4.6v-flash`.
- Image upload is visible and usable only with `glm-4.6v-flash`.
- Accept one PNG, JPG/JPEG or WEBP image of at most `10 * 1024 * 1024` bytes.
- Do not store Base64, absolute paths or original-image copies in `memory.json`.
- Persist a 320 px maximum-dimension thumbnail under the user data directory and delete those thumbnails when clearing memory.
- Manual source edits use `apply_patch`; all Markdown records are mirrored in the Obsidian Petpet vault.

---

### Task 1: Model migration and multimodal request construction

**Files:**
- Modify: `buddy_ai.py:1-25, load_config(), _build_messages(), chat_stream(), _stream_once()`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Produces: `DEFAULT_MODEL == "glm-4.7-flash"`, `SUPPORTED_MODELS`, `VISION_MODEL`, `is_vision_model(model=None)`.
- Produces: `prepare_image_attachment(path) -> dict` with `base64_data`, `filename`, and thumbnail metadata; raises `ValueError` for invalid input.
- Consumes: `chat_stream(user_text, ..., image_attachment=None)` and `_stream_once(..., image_attachment=None)`.

- [x] **Step 1: Write the failing model and request tests**

```python
def test_legacy_model_is_migrated_to_glm_47_flash(self):
    self._write_config({"model": "glm-4-flash"})
    self.assertEqual(ai.get_model(), "glm-4.7-flash")

def test_visual_request_contains_one_image_and_text_block(self):
    attachment = {"base64_data": "aGk=", "filename": "dog.png"}
    body = self._stream_body(model="glm-4.6v-flash", attachment=attachment)
    self.assertEqual(body["messages"][-1]["content"][0]["type"], "image_url")
    self.assertEqual(body["messages"][-1]["content"][1]["text"], "look")

def test_text_model_request_does_not_contain_an_image_block(self):
    body = self._stream_body(model="glm-4.7-flash")
    self.assertIsInstance(body["messages"][-1]["content"], str)
```

- [x] **Step 2: Run the focused RED test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: FAIL because the legacy value is still supported and image attachments are not accepted.

- [x] **Step 3: Implement model migration and API message construction**

```python
DEFAULT_MODEL = "glm-4.7-flash"
VISION_MODEL = "glm-4.6v-flash"
SUPPORTED_MODELS = {
    "glm-4.7-flash": "GLM-4.7-Flash",
    VISION_MODEL: "GLM-4.6V-Flash",
}

def _user_content(text, attachment=None):
    if not attachment:
        return text
    return [
        {"type": "image_url", "image_url": {"url": attachment["base64_data"]}},
        {"type": "text", "text": text or "请看看这张图片，和我聊聊吧"},
    ]
```

Pass `image_attachment` through `chat_stream` and `_stream_once`; reject it with a `ValueError` unless the selected model is `VISION_MODEL`.

- [x] **Step 4: Run focused GREEN tests**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: PASS.

### Task 2: Local attachment and thumbnail lifecycle

**Files:**
- Modify: `buddy_ai.py`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Produces: `create_history_thumbnail(source_path) -> str` returning a relative managed path.
- Produces: `remove_history_thumbnails()` and enriched `append_history(..., image=None)` records.
- Consumes: `APP data directory`, an image source file and QImage-independent standard-library validation where possible.

- [x] **Step 1: Write failing attachment tests**

```python
def test_attachment_keeps_base64_out_of_memory_and_persists_thumbnail(self):
    attachment = ai.prepare_image_attachment(self.png_path)
    ai.append_history(self.memory, "user", "我拍到啦", image=attachment["history_image"])
    record = self.memory["history"][-1]
    self.assertNotIn("base64_data", record)
    self.assertTrue(os.path.exists(ai.resolve_history_image(record["image"]["thumbnail"])))

def test_attachment_rejects_unsupported_or_oversize_file(self):
    with self.assertRaisesRegex(ValueError, "图片"):
        ai.prepare_image_attachment(self.invalid_path)
```

- [x] **Step 2: Run focused RED test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: FAIL because attachments and thumbnail metadata do not exist.

- [x] **Step 3: Implement bounded local image handling**

Use `QImageReader`/`QImage` from the already bundled PyQt5 runtime to decode image dimensions and save a thumbnail; create `DATA_DIR/chat_images` with a UUID filename. Read at most the 10 MiB source after size/type validation, use `base64.b64encode` for the request-only `base64_data`, and return only `{filename, base64_data, history_image}`. Store history image data as `{"thumbnail": "chat_images/<uuid>.png", "filename": "..."}`.

- [x] **Step 4: Run focused GREEN test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: PASS.

### Task 3: Chat selection, preview, history and cleanup UI

**Files:**
- Modify: `pet.py:45-56, ChatWindow.__init__(), send(), _ai_thread(), on_done(), on_error(), confirm_clear_memory(), _set_log_messages()`
- Modify: `tests/test_chat_tools.py`

**Interfaces:**
- Consumes: `ai.is_vision_model()`, `ai.prepare_image_attachment()`, `ai.resolve_history_image()` and `ai.remove_history_thumbnails()`.
- Produces: `ChatWindow.select_image()`, `clear_pending_image()`, `_refresh_image_upload_state()` and `self._pending_image`.

- [x] **Step 1: Write failing UI tests**

```python
def test_image_tool_only_appears_for_visual_model(self):
    self.window.select_model("glm-4.7-flash")
    self.assertTrue(self.window.image_btn.isHidden())
    self.window.select_model("glm-4.6v-flash")
    self.assertFalse(self.window.image_btn.isHidden())

def test_selected_image_is_rendered_in_pending_and_saved_history(self):
    self.window.select_model("glm-4.6v-flash")
    self.window._set_pending_image(self.attachment)
    self.assertFalse(self.window.image_preview.isHidden())
    self.window.on_done("汪，我看到啦！")
    self.assertEqual(self.window.mem["history"][-2]["image"]["filename"], "dog.png")
```

- [x] **Step 2: Run focused RED test**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: FAIL because the upload widgets and selection state do not exist.

- [x] **Step 3: Implement the warm image controls and threaded payload handoff**

Import `QFileDialog`, create `image_btn` and a compact preview row above the text input. `select_image()` must use `QFileDialog.getOpenFileName` with `Images (*.png *.jpg *.jpeg *.webp)`, show a warning on `ValueError`, and call `_set_pending_image()`. Pass a snapshot of the attachment to the background thread, render its thumbnail in user bubbles, append its memory metadata on both success and fallback, and call `clear_pending_image()` after the result. Selecting the text model must clear the pending image. Call `ai.remove_history_thumbnails()` only after the existing clear-memory confirmation succeeds.

- [x] **Step 4: Run focused GREEN test**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: PASS.

### Task 4: User documentation and full verification

**Files:**
- Modify: `README.md:135-157`
- Modify: `config.json.example`
- Modify: `docs/superpowers/specs/2026-08-11-multimodal-chat-design.md`
- Modify: `docs/superpowers/plans/2026-08-11-multimodal-chat-plan.md`
- Create/Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/图文陪伴聊天设计.md`
- Create/Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/图文陪伴聊天实施计划.md`

**Interfaces:**
- Consumes: completed model and UI behaviour.
- Produces: current user-facing configuration instructions and synchronized project records.

- [x] **Step 1: Review documentation scope**

The README and example configuration are human-facing prose, so a source-text assertion would only be a change detector rather than a behaviour test. Review the rendered text against the completed UI and request behaviour instead.

- [x] **Step 2: Update documentation**

Document that `GLM-4.7-Flash` is text-only, `GLM-4.6V-Flash` enables one image per turn, images are sent to the configured Zhipu API, and only local history thumbnails are retained. Change the example model to `glm-4.7-flash`. Mirror the final design and plan to Obsidian with YAML frontmatter and related links.

- [x] **Step 3: Run final verification**

Run:
```powershell
python -m pytest tests/test_ai_config.py tests/test_chat_tools.py tests/test_release_metadata.py -q
python -m pytest -q
python -m py_compile buddy_ai.py pet.py
git diff --check
```

Expected: every command exits `0`.

## Implementation Result

- `tests/test_ai_config.py`: 9 passed.
- `tests/test_chat_tools.py`: 11 passed.
- Focused regression (`test_ai_config`, `test_chat_tools`, `test_release_metadata`): 25 passed in 1.05s.
- Full suite: 313 passed in 37.89s.
- `python -m py_compile buddy_ai.py pet.py` and `git diff --check`: exit 0.

### Post-implementation regression: empty streamed response

- [x] Added a RED test for `data: [DONE]` with no `delta.content`; the former parser incorrectly produced `("done", "")`.
- [x] `_stream_once()` now emits `("error", "empty_response")` for that response shape, so `ChatWindow` uses the existing offline fallback instead of persisting an empty assistant bubble.
- [x] Focused AI/chat tests: 21 passed in 0.71s; final full suite: 314 passed in 73.95s.

### Post-implementation regression: GLM-4.7 thinking budget

- [x] Diagnosed the live SSE response without exposing API credentials or reply text: GLM-4.7 returned many `reasoning_content` chunks, then reached `finish_reason: length` before app-context requests received answer text.
- [x] Added `"thinking": {"type": "disabled"}` to every companion-chat request and a request-body regression assertion.
- [x] A live privacy-safe validation received 46 response characters after the change.
- [x] Added friendly fallback coverage for `rate_limit` and `empty_response`; error codes no longer appear in chat bubbles.
- [x] Final full suite: 315 passed in 37.56s.

## Self-Review

- Model replacement, legacy migration, model gating, one-image handling, local thumbnail history, privacy boundaries, error handling and full documentation each map to Tasks 1–4.
- The plan contains concrete tests, command lines and function interfaces; it contains no `TODO`/`TBD` placeholders.
- `ChatWindow` consumes only the named `buddy_ai` helpers, while `buddy_ai` owns persistence and request shaping, so the interfaces are consistent across tasks.
