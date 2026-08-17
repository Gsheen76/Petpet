# Petpet 代码与资源结构重构设计

## 目标

- 永久保留根目录 `pet.py` 作为源码与打包启动入口。
- 按功能逐步把超大模块迁入 `petpet/` 包，每一步都保持旧导入和现有行为可用。
- 把发布时使用的运行资源与制作源图分开，发布包不再携带参考图和精灵表源文件。
- 建立“玩家进度 + 两只独立宠物”的存档边界，为后续替换桌面与家园宠物形象做好准备。

## 非目标

- 本轮不引入插件系统、事件总线、依赖注入框架或新的第三方依赖。
- 不一次性移动全部模块或全部资源。
- 不改变 `python pet.py`、PyInstaller 和现有更新器的用户入口。

## 目标代码结构

```text
pet.py
petpet/
  app/
    paths.py
    state.py
  chat/
    service.py
    memory.py
    knowledge.py
    window.py
  desktop/
    window.py
    bubbles.py
    interactions.py
  home/
    window.py
    pet.py
    geometry.py
  progression/
    model.py
    windows.py
  games/
    windows.py
  ui/
    common.py
    settings.py
    tutorial.py
```

迁移期间，根目录原模块保留为兼容转发层。只有当所有调用方和测试都改用新模块后，才删除对应旧文件。

## 玩家与宠物数据

```text
player
  level
  xp
  pet_coins
  achievements
  furniture_inventory
  decoration_inventory

pets
  desktop
    name
    hunger / mood / energy
    affection_level / affection_points
    interaction_cooldowns
    chat_memory
  home
    name
    hunger / mood / energy
    affection_level / affection_points
    interaction_cooldowns
    chat_memory
```

旧存档首次加载时，将当前宠物的名字、属性、好感与聊天记忆复制到 `desktop` 和 `home`。迁移完成后，两边独立变化；玩家等级、经验、Pet币、成就与库存继续共用。迁移必须幂等，重复加载不能再次覆盖新数据。

## 目标资源结构

```text
assets/
  runtime/
    pets/
      desktop/
        poses/
        animations/
        avatar/
      home/
        poses/
        animations/
        avatar/
    scenes/home/
    furniture/home/
    decorations/
    props/
    icons/
    sounds/
    knowledge/
  source/
    spritesheets/
    references/
    generated/
```

桌面宠物和家园宠物是两个独立宠物身份。资源目录按宠物身份区分，不再把它们解释为同一宠物在两个场景中的动作。

运行时代码只通过 `petpet.app.paths` 获取资源目录。PyInstaller 仅收集 `assets/runtime/`；`assets/source/` 保留在仓库中供制作使用，不进入发布包。

## 分阶段迁移

1. 建立包骨架与统一路径模块，根目录 `app_paths.py` 保持兼容。
2. 引入玩家/双宠物存档结构及旧存档幂等迁移。
3. 抽离聊天服务、双宠物记忆和知识库。
4. 抽离设置、教程、公共暖色圆角控件和聊天窗口。
5. 抽离桌面宠物窗口、气泡与互动。
6. 抽离家园窗口、家园宠物控制器和几何逻辑。
7. 抽离养成界面与小游戏。
8. 分批迁移运行资源，最后更新 PyInstaller 和资源完整性测试。

每个阶段只处理一个边界，不同时进行大规模代码移动与资源移动。

## 兼容与错误处理

- 旧导入继续可用，转发层不复制业务逻辑。
- 找不到新资源时，在资源迁移阶段保留旧路径回退；该回退只持续到资源阶段完成。
- 存档迁移先构造新结构，再原子写回；任何解析失败都保留原文件并使用安全默认值。
- 两只宠物的聊天记忆分别写入独立记录，清除一只宠物记忆不得影响另一只。

## 验证

- 每个迁移步骤先增加失败测试，再做最小实现。
- 每步运行相关 focused tests，再运行 `python -m pytest -q`。
- 资源阶段验证所有运行资源存在、制作资源未进入 PyInstaller datas。
- 每阶段最后使用当前 worktree 的 `pet.py` 做源码启动冒烟。
- 不使用 `git reset`、`git checkout`，不覆盖现有未提交改动。
