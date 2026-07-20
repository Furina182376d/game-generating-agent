# crawler/ — 素材爬虫

一次性离线脚本：从 GitHub 抓取游戏美术素材，分五类整理，打标签，产出 `assets/` 目录和 `assets/index.json` 检索元数据。对应实验要求 2「爬取 300-500 张素材并建立标签与检索索引」。

## 核心思路

1. **数据源选 GitHub `phaserjs/examples`**：这是 Phaser 官方示例仓库，自带大量可免费用于教学的示例美术。之所以不用 kenney.nl / itch.io——本网络环境下 kenney.nl 返回反爬错误页、itch.io 不可达，只有 GitHub 的 API 与 raw 镜像稳定。
2. **一次 API 发现全部文件**：用 GitHub Git Trees API（`?recursive=1`）一次请求递归列出整个仓库文件树，免鉴权，避免逐目录爬取。
3. **关键词归类 + 按类配额**：用文件名正则把 PNG 归入 characters/backgrounds/items/ui/effects 五类，每类设上限（合计 430，落在 300-500 区间），防止某一类刷屏。
4. **容错下载 + 唯一命名**：多镜像顺序重试、校验 PNG 有效性；本地文件名全局唯一，绝不静默覆盖。

## 唯一文件：`scrape_assets.py`

运行：
```bash
python -m crawler.scrape_assets            # 完整抓取并写 index.json
python -m crawler.scrape_assets --limit 60 # 每类限量（快速测试用）
```

### 关键 API 调用

| 调用 | 内容 | 原因 |
|------|------|------|
| GitHub Git Trees API | `GET https://api.github.com/repos/phaserjs/examples/git/trees/master?recursive=1` | 一次请求递归拿到整仓所有文件路径，免鉴权；替代逐目录遍历 |
| raw 文件镜像 | 首选 `ghproxy.net` 代理，兜底直连 `raw.githubusercontent.com` | 本网络环境直连 raw 超时、jsdelivr 会 301 死循环，ghproxy 稳定（约 0.8s/文件） |

请求都带自定义 `User-Agent`（GitHub 要求），并在类别间 `sleep(0.02)` 限速。

### 处理流程（`crawl`）

1. **`fetch_tree`** — 调 Trees API，只保留 `type=blob` 且以 `.png` 结尾的路径；若 GitHub 返回 `truncated=true` 会告警（结果可能不全）。
2. **分桶过滤** — 只要 `/assets/` 目录下的图；排除 `tests/`、`compressed/`、字体图集、spine 骨骼、3D 贴图等"匹配了关键词但不能当独立精灵用"的噪声；再用 `RULES`（一组按顺序匹配、first-match-wins 的正则）归类。
3. **下载 + 命名 + 建元数据**：
   - `download` 按镜像顺序重试，两道校验——响应体 <200 字节视为占位空图判失败；开头不是 PNG magic number(`\x89PNG`) 视为 HTML 错误页换下一镜像。
   - **全局唯一命名**：源仓库里几十个游戏目录都有 `player.png`，故本地名用 `父目录名__文件名`，仍冲突就加数字后缀。
   - 每条写 7 个字段到 index.json：`path / category / name / tags / style / source / license`。

### 辅助函数
- `classify(path)` — 按 `RULES` 顺序归类，第一条命中即定类。
- `make_tags(stem, cat)` — 文件名拆词 → 过滤纯数字/单字符 → 类别名置首去重。
- `guess_style(path)` — 从关键词猜画风（pixel/cartoon/generic）。
- `save_index(items)` — 写 `assets/index.json`（`ensure_ascii=False` 保留可读中文）。

## 产物
- `assets/<category>/*.png` — 430 张素材，按类分目录。
- `assets/index.json` — 每张图的元数据与标签，供 `agent/asset_retriever.py` 建 CLIP 索引。