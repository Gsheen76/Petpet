# 多宠物聊天身份与冰淇淋睡眠一致性 Implementation Plan

> **For agentic workers:** Execute this plan task by task with red-green-refactor discipline. Do not skip the listed verification commands, and preserve unrelated working-tree files.

**Goal:** 让聊天窗口始终使用当前小狗的真实身份、头像和独立性格，清除助手消息中的多余空行，并让冰淇淋桌面睡眠复用家园的同一套 8 帧动画。

**Architecture:** 宠物注册表是身份与性格的唯一来源，`pet_id` 决定真实名、头像和提示词，昵称只负责展示。聊天服务接收显式 personality，API 根据稳定的 `pet_id` 注入；桌面动画加载器增加通用 spritesheet 切帧能力，冰淇淋桌面睡眠直接引用家园图片，不复制资源。

**Tech Stack:** Python 3, PySide6, pytest, JSON manifests, Obsidian CLI / Obsidian Flavored Markdown.

---

## Task 1: 让性格绑定稳定的 `pet_id`，并规范助手换行

**Files:**
- Modify: `assets/runtime/pets/manifest.json`
- Modify: `petpet/chat/service.py`
- Modify: `petpet/chat/api.py`
- Modify: `tests/test_chat_service.py`
- Modify: `tests/test_ai_config.py`

### Step 1: 写失败测试

新增测试覆盖：

```python
def test_clean_assistant_reply_collapses_only_extra_blank_lines():
    assert clean_assistant_reply("第一句\n\n  第二句") == "第一句\n第二句"


def test_service_uses_explicit_personality_after_pet_is_renamed():
    messages = build_messages(
        "你好",
        [],
        pet_name="奶油",
        personality="温柔可爱，语气柔软，会耐心安慰主人。",
        ...,
    )
    assert "奶油" in messages[0]["content"]
    assert "温柔可爱" in messages[0]["content"]
```

再用 API 层测试证明 `pet_id="ice_cream"` 时，即使昵称是“奶油”，仍注入冰淇淋性格，而不是根据昵称猜测。

### Step 2: 运行 RED

Run:

```powershell
python -m pytest tests/test_chat_service.py tests/test_ai_config.py -q
```

Expected: 新测试因 personality 尚未接入、连续换行尚未折叠而失败。

### Step 3: 最小实现

在注册表中加入两个字段：

```json
"chat_personality": "活泼开朗、反应轻快、好奇热情……"
```

午餐肉强调活泼开朗、好奇和快速反应；冰淇淋强调温柔可爱、耐心安慰和亲近感。两者都限制口癖频率，避免喧闹或过度撒娇。

`service.build_messages()` 增加显式 `personality` 参数，将内容附加到 system prompt；保持 service 为纯组装层，不从注册表反向导入。

`api._build_messages()` 增加 `pet_id`，通过 `pet_definition(pet_id)` 取得 `chat_personality`，并让 `_default_proxy_stream()`、`_stream_once()`、`chat_stream()` 的所有路径都传递该值。缺失字段时使用通用小狗性格作为兼容回退。

`clean_assistant_reply()` 只对助手文本执行：

```python
text = text.replace("\r\n", "\n").replace("\r", "\n")
lines = [line.strip() for line in text.split("\n")]
text = "\n".join(line for line in lines if line)
return text.strip()
```

保留正常单换行的段落顺序，不修改用户消息。

### Step 4: 运行 GREEN

Run:

```powershell
python -m pytest tests/test_chat_service.py tests/test_ai_config.py -q
```

Expected: PASS.

### Step 5: 提交

```powershell
git add assets/runtime/pets/manifest.json petpet/chat/service.py petpet/chat/api.py tests/test_chat_service.py tests/test_ai_config.py
git commit -m "feat: personalize chat by active pet"
```

---

## Task 2: 更新聊天标题与当前宠物头像

**Files:**
- Modify: `petpet/ui/chat.py`
- Modify: `tests/test_chat_tools.py`
- Modify: `tests/test_chat_profile.py`（仅在需要复用已有切换场景时）

### Step 1: 写失败测试

新增或更新断言：

```python
assert window.title.text().strip() == "summer（午餐肉）"
```

并覆盖以下行为：

- 昵称等于真实名时标题只显示 `冰淇淋`，不出现 `冰淇淋（冰淇淋）`。
- 昵称改为 `奶油` 时标题显示 `奶油（冰淇淋）`。
- `set_pet_id("ice_cream")` 后，助手头像的 `avatarSource` 指向冰淇淋桌面待机资源。
- 历史助手文本的连续空行渲染为单换行；用户消息保持原文。

### Step 2: 运行 RED

Run:

```powershell
python -m pytest tests/test_chat_tools.py tests/test_chat_profile.py -q
```

Expected: 标题仍只有昵称、头像仍固定午餐肉资源，因此新断言失败。

### Step 3: 最小实现

在 `ChatWindow` 增加一个小型展示方法：

```python
def _chat_title(self) -> str:
    nickname = self._pet_name()
    real_name = pet_definition(self.pet_id).get("default_name", nickname)
    return nickname if nickname == real_name else f"{nickname}（{real_name}）"
```

初始化和 `refresh_pet_name()` 都调用该方法。其他界面继续只使用昵称。

把助手头像源从固定的 `POSES_DIR/idle.png` 改为：

```python
pet_asset_path(self.pet_id, "desktop", "idle")
```

保留现有圆形裁剪、尺寸和用户头像逻辑；资源缺失时沿用当前占位回退。宠物切换后重新渲染历史消息，使头像立即同步。

### Step 4: 运行 GREEN

Run:

```powershell
python -m pytest tests/test_chat_tools.py tests/test_chat_profile.py -q
```

Expected: PASS.

### Step 5: 提交

```powershell
git add petpet/ui/chat.py tests/test_chat_tools.py tests/test_chat_profile.py
git commit -m "feat: sync chat identity with active pet"
```

---

## Task 3: 冰淇淋桌面睡眠复用家园 8 帧图

**Files:**
- Modify: `assets/runtime/pets/ice_cream/desktop/animations/manifest.json`
- Modify: `petpet/app/pet_window.py`
- Modify: `tests/test_pet_window_boundary.py`
- Verify: `assets/runtime/pets/ice_cream/home/poses/home-pet-sleep.png`

### Step 1: 写失败测试

新增真实资源集成测试：

```python
window.refresh_pet_definition("ice_cream")
assert len(window.animation_frames["sleep"]) == 8
assert window.animation_specs["sleep"]["fps"] == 3
assert window.animation_specs["sleep"]["scale"] == pytest.approx(0.62)
assert window.animation_specs["sleep"]["anchor_bottom"] is True
```

同时断言第一帧尺寸来自 640×640 单元格中的 `[24, 176, 592, 288]` 内容裁剪，并确认午餐肉现有 12 帧睡眠不受影响。

### Step 2: 运行 RED

Run:

```powershell
python -m pytest tests/test_pet_window_boundary.py tests/test_sleep_interaction.py -q
```

Expected: 冰淇淋桌面清单尚无 sleep、加载器尚不支持 spritesheet，因此新测试失败。

### Step 3: 最小实现

给动画加载器增加通用 `spritesheet` 分支，支持以下清单元数据：

```json
"sleep": {
  "spritesheet": "../../home/poses/home-pet-sleep.png",
  "frame_size": 640,
  "frame_count": 8,
  "columns": 3,
  "content_rect": [24, 176, 592, 288],
  "fps": 3,
  "loop": true,
  "fallback": "sleep",
  "scale": 0.62,
  "anchor_bottom": true
}
```

加载流程：

1. 相对动画清单目录解析图片路径。
2. 校验 frame size、count、columns、content rect 为正数且每一帧矩形都在图片范围内。
3. 按行优先顺序切出 8 帧，只保留单元格内的内容矩形。
4. 复用现有缩放与颜色处理流程。
5. 清单或图片无效时返回空帧并沿用静态待机回退，不让应用崩溃。

桌面显示使用 3 FPS、底部锚定和 0.62 比例，目标可视尺寸约 118×57 px，与家园约 118×58 px 一致。不得复制第二份睡眠 PNG。

### Step 4: 运行 GREEN

Run:

```powershell
python -m pytest tests/test_pet_window_boundary.py tests/test_sleep_interaction.py -q
```

Expected: PASS，且午餐肉睡眠断言保持原值。

### Step 5: 提交

```powershell
git add assets/runtime/pets/ice_cream/desktop/animations/manifest.json petpet/app/pet_window.py tests/test_pet_window_boundary.py
git commit -m "feat: share ice cream sleep animation across scenes"
```

---

## Task 4: 全量验证、同步 Obsidian、重启源码小狗

**Files:**
- Create: `D:/Github Desktop/My-Obsidian/项目/Petpet/开发记录/2026-08-21 多宠物聊天身份与冰淇淋睡眠一致性.md`
- Verify: source changes and both repositories' status

### Step 1: 运行焦点和全量测试

Run:

```powershell
python -m pytest tests/test_chat_service.py tests/test_ai_config.py tests/test_chat_tools.py tests/test_chat_profile.py tests/test_pet_window_boundary.py tests/test_sleep_interaction.py -q
python -m pytest -q
python -m py_compile petpet/chat/api.py petpet/chat/service.py petpet/ui/chat.py petpet/app/pet_window.py
git diff --check
```

Expected: 所有命令退出码为 0。

### Step 2: 人工冒烟验证

依次验证：

- 选择午餐肉后打开聊天：头像为午餐肉，回答活泼开朗。
- 选择冰淇淋并改名“奶油”：标题为 `奶油（冰淇淋）`，助手头像为冰淇淋待机头像，回答温柔可爱。
- 让回复包含多段文字：没有空白行，正常换行仍存在。
- 冰淇淋进入桌面睡眠：使用与家园相同的 8 帧动作、3 FPS，尺寸与家园接近且底部不跳动。

### Step 3: 写入并用 Obsidian CLI 校验记录

笔记使用 Obsidian frontmatter、wikilink 和 callout，记录需求、架构决策、改动文件、测试结果、提交号、人工验证项和回退方式。完成后执行 CLI 的 read/outline/links 检查，确认笔记位于 `My-Obsidian` vault 且可被 Obsidian 索引。

### Step 4: 检查最终状态并重启

Run:

```powershell
git status --short
git log -4 --oneline --decorate
```

保留既有未跟踪 `.superpowers` 文件，不把它们混入提交。

停止命令行中精确包含 `D:\Agent_project\Petpet\pet.py` 的旧 `python.exe/pythonw.exe` 进程，然后用 `pythonw.exe`、工作目录 `D:\Agent_project\Petpet`、隐藏窗口重新启动该源码入口。等待约 1.2 秒后按完整入口路径验证新 PID；不得停止其他 Python 进程。

### Step 5: 最终汇报

向用户提供：

- 已完成的四项可见变化。
- 焦点测试与全量测试的精确通过数量。
- 源码提交号与 Obsidian 笔记路径。
- 新启动的源码小狗 PID，以及建议立即验证的聊天头像、标题、性格和睡眠动画。
