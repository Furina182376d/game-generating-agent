# AI 小游戏生成智能体

从一句自然语言描述，端到端生成可在 PC / 手机浏览器运行的 H5 小游戏（当前实现为弹幕射击类型）。

核心设计思想：**LLM 只负责"理解需求"，把自由文本压成一份结构化配置；游戏代码由确定性模板生成**。这样把大模型的不确定性隔离在配置层，模板产出的代码始终可运行、可调试。

## 架构

```
自然语言描述
   │  agent/nl_to_config.py    Stage 1：Claude 工具调用 → 结构化 GameConfig
   ▼
GameConfig  (agent/schema.py，贯穿全流程的数据契约)
   │  agent/asset_retriever.py Stage 2：CLIP 语义检索 → 为每个 *_query 匹配素材
   ▼
GameConfig + 素材路径
   │  agent/code_generator.py  Stage 3：填充 Phaser 模板，素材内联为 base64
   ▼
可运行 H5 游戏  output/<name>/index.html （单文件、零外链、双击即玩）
```

素材库由 `crawler/` 离线爬取一次生成，`agent/asset_retriever.py build` 再把它编码成 CLIP 索引，之后每次生成游戏都复用该索引。

## 目录

每个目录下都有独立 README，讲解其核心思路与具体实现。

| 路径 | 作用 |
|------|------|
| [agent/](agent/) | 智能体核心：需求理解、素材检索、代码生成，以及串联三者的管道 |
| [assets/](assets/) | 游戏素材库（5 类，430 张 PNG）+ `index.json` 元数据 + `embeddings.npy` CLIP 索引 |
| [crawler/](crawler/) | 素材爬虫：从 GitHub `phaserjs/examples` 抓图、分类打标、建索引 |
| [templates/](templates/) | Phaser.js 参数化游戏模板（`{{PLACEHOLDER}}` 占位） |
| [frontend/](frontend/) | 用户输入界面（一句话描述 → 预览生成结果） |
| [docs/](docs/) | 周报 + 最终技术报告 |
| `vendor/` | 内联进产物的第三方依赖（`phaser.min.js`） |
| `output/` | 生成的游戏产物（每个游戏一个 `index.html`） |

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env          # 填入 ANTHROPIC_API_KEY（可选）

# 1. 收集素材并建立检索索引（一次性）
python -m crawler.scrape_assets          # 抓取 → assets/ + index.json
python -m agent.asset_retriever build    # 编码 → assets/embeddings.npy

# 2. 生成一款游戏
python -m agent.pipeline "一个霓虹像素风太空射击游戏" my_shooter

# 3. 本地预览
python -m http.server -d output/my_shooter 8080
```

无 `ANTHROPIC_API_KEY` 时，Stage 1 自动降级为内置默认配置（见 `agent/nl_to_config.py` 的 `_fallback_config`），整条管道仍可离线跑通。

## 对照实验要求

| 实验要求 | 落地位置 |
|----------|----------|
| 自然语言 → 完整小游戏的代码生成智能体 | `agent/pipeline.py` 一条命令串通四阶段 |
| 爬取 300-500 张素材，五类整理，建标签与检索索引 | `crawler/`（430 张）+ `assets/index.json` + `embeddings.npy` |
| 根据主题/玩法/风格检索素材而非随机调用 | `agent/asset_retriever.py`（CLIP 文本-图像共享空间检索） |
| 可运行 H5，完整开始/游玩/结束/重开流程，无阻塞错误 | `templates/shooter_base.js`（四场景 + 缺图占位容错） |
| 适配 PC 与移动端分辨率 | 模板 `Phaser.Scale.FIT` + 键盘/触屏双输入 |

## 当前状态与已知缺口

- [x] 端到端管道：NL → GameConfig → 素材检索 → Phaser 代码 → 单文件 H5
- [x] 素材库 430 张 + CLIP 检索索引
- [x] 弹幕射击模板（完整流程 + 响应式 + 容错）
- [ ] 仅有 `shooter` 一个模板，schema 中的 `platformer / puzzle / tower_defense` 目前都回退到 shooter
- [ ] 离线 fallback 配置只生成 2 种敌人（在线 Claude 路径可生成 2-4 种）
- [ ] `frontend/index.html` 依赖的后端接口 `/api/generate`（`agent/server.py`）尚未实现