# AI 小游戏生成智能体

从一句自然语言描述，端到端生成可在浏览器运行的 H5 小游戏（弹幕射击类型）。

## 架构

```
自然语言描述
   │  agent/nl_to_config.py   (Claude → 结构化 GameConfig)
   ▼
GameConfig (agent/schema.py)
   │  agent/asset_retriever.py (CLIP 语义检索 → 匹配素材)
   ▼
GameConfig + 素材路径
   │  agent/code_generator.py (填充 Phaser 模板)
   ▼
可运行 H5 游戏 (output/<name>/index.html)
```

## 目录

| 路径 | 作用 |
|------|------|
| `agent/` | 智能体核心：需求理解、素材检索、代码生成、管道 |
| `assets/` | 游戏素材库（5 类）+ `index.json` 元数据/标签 |
| `crawler/` | 素材爬虫（Kenney / OpenGameArt，CC0） |
| `templates/` | Phaser.js 参数化游戏模板 |
| `frontend/` | 用户输入界面 |
| `docs/` | 周报 + 最终技术报告 |

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env          # 填入 ANTHROPIC_API_KEY

# 1. 收集素材并建立检索索引（Phase 1）
python -m crawler.scrape_assets
python -m agent.asset_retriever build

# 2. 生成一款游戏
python -m agent.pipeline "一个霓虹像素风太空射击游戏" my_shooter

# 3. 本地预览
python -m http.server -d output/my_shooter 8080
```

无 API key 时管道使用内置默认配置，仍可离线跑通生成流程。

## 进度

- [x] Phase 0: 项目骨架
- [ ] Phase 1: 素材收集与检索
- [ ] Phase 2: 模板系统完善
- [ ] Phase 3: 智能体核心联调
- [ ] Phase 4: 运行测试与自动修复（可选）
- [ ] Phase 5: 前端界面 + 验收
