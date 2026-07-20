# agent/ — 智能体核心

整条"自然语言 → 可运行游戏"流水线的实现所在。四个阶段各一个模块，外加一份贯穿全流程的数据契约。

## 核心思路

把大模型的不确定性**关在配置层**：LLM 只做一件事——把用户的自由描述理解成一份结构化的 `GameConfig`；此后素材检索和代码生成都是确定性的。这样保证：

1. 产物永远可运行（代码来自经过验证的模板，不是 LLM 现编）；
2. 每个阶段可独立测试、可调试；
3. 无 API key 也能靠 fallback 配置离线跑通全流程。

数据流的契约是 `GameConfig`（Pydantic 模型），它像一根扁担挑起四个阶段：

```
NL 描述 → [nl_to_config] → GameConfig → [asset_retriever] → 填入素材路径 → [code_generator] → index.html
                                              ↑ pipeline.py 负责按顺序串联
```

## 文件说明

### `schema.py` — 数据契约
定义 `GameConfig` / `PlayerSpec` / `EnemySpec` 三个 Pydantic 模型，是所有阶段共享的唯一"真相来源"。
- `GameConfig`：游戏标题、类型（shooter/platformer/puzzle/tower_defense）、主题、画风、玩家、敌人列表、背景、胜负条件、目标分、难度、风格关键词。
- `*_query` 字段（如 `sprite_query` / `background_query`）存的是**英文视觉短语**，供 CLIP 文本检索用；对应的 `sprite` / `background` 字段在检索后被填成具体素材路径。
- 用 Pydantic 的好处：能直接 `model_json_schema()` 导出 JSON Schema 交给 Claude 工具调用做输出约束，回来再 `model_validate` 二次校验。

### `nl_to_config.py` — Stage 1：语义理解
把一句描述压成 `GameConfig`。
- **在线路径**：调用 Claude，用 `tool_choice` **强制工具调用**，`input_schema` 直接由 `GameConfig` 导出，因此模型只能吐出符合 schema 的 JSON。system prompt 要求 `*_query` 写成适合 CLIP 检索的英文短语、生成 2-4 种敌人、`style_keywords` 捕捉画风。
- **调用内容**：`client.messages.create(model=..., tools=[emit_game_config], tool_choice={"type":"tool", ...})`；默认模型取环境变量 `ANTHROPIC_MODEL`，缺省 `claude-opus-4-8`。
- **离线降级**：无 `ANTHROPIC_API_KEY` 时走 `_fallback_config`，返回固定的双敌人太空射击配置，保证测试/无网环境可用。

### `asset_retriever.py` — Stage 2：CLIP 语义检索
把 `GameConfig` 里的英文 query 解析成具体素材路径。
- **模型**：`open_clip` 的 `ViT-B-32-quickgelu` + `openai` 权重（quickgelu 变体与 openai 权重的训练激活一致，普通 ViT-B-32 会告警并掉点）。模型懒加载，import 时很轻。
- **原理**：CLIP 把文本和图像编码进同一个 512 维空间。`build_index` 把全部素材编码、L2 归一化后缓存到 `assets/embeddings.npy`；`search` 把文本 query 编码后与素材矩阵做点积（都归一化，点积即余弦相似度），排序取 top-k，可按类别过滤。
- **入口 `resolve`**：把 `style_keywords` 拼到每个 query 后做检索，依次填玩家、背景、每个敌人的 sprite。这就是"按主题/风格检索而非随机调用素材"的落地点。

### `code_generator.py` — Stage 3：代码生成
把 `GameConfig`（含已解析素材）渲染成一个自包含的 `index.html`。
- 读取 `templates/` 下对应 genre 的模板，把 `{{GAME_CONFIG}}` / `{{GAME_TITLE}}` 占位符替换成实际内容。
- **全内联**：所有素材经 `_data_uri` 转成 base64 data URI，Phaser 引擎（`vendor/phaser.min.js`）也内联进 HTML。产物是单文件、零外链、可在 `file://` 下直接运行——一个游戏 = 一个可分享文件，适合验收/演示。

### `pipeline.py` — 串联入口
`run(description, name)` 顺序调用三阶段，带容错（素材索引未建时打印提示并跳过，靠模板的占位纹理仍可运行）。

```bash
python -m agent.pipeline "a neon space shooter" my_game
```

## 已知缺口
- `code_generator._template_for` 目前只映射了 `shooter`，其余 genre 都回退到射击模板。
- 离线 `_fallback_config` 只生成 2 种敌人（在线 Claude 路径可 2-4 种）。