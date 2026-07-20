# templates/ — Phaser.js 游戏模板

参数化的游戏代码模板。`agent/code_generator.py` 把 `GameConfig` 填进模板的占位符，产出可运行的游戏 JS。

## 核心思路

**模板是纯 JS 加 `{{占位符}}`，LLM 不生成代码**。这样代码生成是确定性、可调试、可复用的——LLM 只在上游把需求理解成配置，模板负责把配置变成经过验证、必定可运行的游戏。同一类型游戏共用一个模板，生成效率和稳定性都更高（对应实验建议 5）。

占位符：
- `{{GAME_CONFIG}}` → 替换为 `GameConfig` 的 JSON；
- `{{GAME_TITLE}}` → 替换为游戏标题。

## 唯一模板：`shooter_base.js`

一个参数化的 Phaser 3 弹幕射击游戏，四场景走完实验要求 3 的完整流程：

```
BootScene → MenuScene → PlayScene → GameOverScene → (重开) → PlayScene
```

### 各场景职责

- **BootScene**：按 config 加载素材。关键容错——若某素材未解析出来，`makeFallback` 用纯色方块生成占位纹理，保证"绝不因缺图阻塞运行"（要求 3：无阻塞错误）。
- **MenuScene**：开始页，键盘 SPACE 或触屏 tap 开始。
- **PlayScene**：核心玩法。
  - 滚动背景、玩家、三个物理组（子弹/敌人/敌弹）；
  - **双输入**：方向键 + 触屏拖动（含坐标缩放换算，适配 FIT 缩放）；
  - **自动开火**，按 `fire_rate` 节流；
  - **难度**：spawn 间隔随时间递减，再按 easy/hard 乘系数；
  - **敌人行为**由 config 的 `type` 决定：`zigzag` 正弦横移、`homing` 朝玩家逼近、其余直线下落；
  - **碰撞/计分/胜负**：子弹打敌人扣血加分，敌人/敌弹撞玩家扣命并镜头抖动；到达 `target_score` 判胜，命数归零判负。
- **GameOverScene**：显示胜负与得分，SPACE 或 tap 重开。

### 响应式适配
游戏配置用 `Phaser.Scale.FIT` + `CENTER_BOTH`，自动缩放到视口并居中，适配 PC 与移动端分辨率（要求 3）。视口逻辑分辨率固定 480×720。

## 如何新增游戏类型

1. 在此目录新建模板，如 `platformer_base.js`，同样用 `{{GAME_CONFIG}}` 占位；
2. 在 `agent/code_generator.py` 的 `_template_for` 里把对应 genre 映射到新模板。

> 目前仅实现 shooter 模板，其余 genre 会回退到 `shooter_base.js`。