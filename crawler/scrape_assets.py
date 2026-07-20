"""Collect game-art images from GitHub and build assets/index.json.

Source: the **phaserjs/examples** repo (MIT / bundled sample art, free to use
for this coursework). We enumerate its asset tree via the GitHub git-trees API
(one request, no auth needed) and pull the PNGs whose filenames match our five
gameplay categories, tagging each so the CLIP retriever can index it.

Why this source: in this network environment kenney.nl serves an anti-bot
Error page with a JS-rendered listing, and itch.io is unreachable. GitHub's
API + raw.githubusercontent.com are reliable. See memory: zju-game-asset-source.

Categories: characters / backgrounds / items / ui / effects
Run:  python -m crawler.scrape_assets            # crawl + write index.json
      python -m crawler.scrape_assets --limit 60 # cap per category (testing)
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

# 素材根目录（本文件位于 crawler/，故上溯两级到仓库根再进 assets/）与索引文件路径。
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
INDEX = ASSETS_DIR / "index.json"

# 实验要求的五个素材类别：角色 / 场景 / 道具 / 界面元素 / 特效。
CATEGORIES = ["characters", "backgrounds", "items", "ui", "effects"]

# 每个类别的抓取上限。总和 = 430，正好落在实验要求的 300-500 张区间内。
# 之所以要按类设配额而非一把梭：源仓库里 effects / backgrounds 素材极多，
# 不限量会让某一类刷屏、其他类饿死，破坏"五类均衡"。可用 --limit 临时覆盖。
DEFAULT_CAPS = {
    "characters": 110,
    "backgrounds": 80,
    "items": 90,
    "ui": 60,
    "effects": 90,
}

# ---- 素材来源配置 ---------------------------------------------------------
# 数据源：GitHub 上的 phaserjs/examples 官方示例仓库（自带大量可免费用于
# 教学的示例美术）。选它的原因见文件头注释：本网络环境下 kenney.nl 返回反爬
# 错误页、itch.io 不可达，只有 GitHub 的 API 与 raw 镜像稳定可用。
REPO = "phaserjs/examples"
BRANCH = "master"
# GitHub Git Trees API：一次请求即可递归列出整个仓库的文件树（?recursive=1），
# 无需鉴权。用它替代逐目录遍历，把"发现所有 PNG"压缩成一次 API 调用。
TREE_API = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
# 自定义 User-Agent：GitHub 要求带 UA，否则可能被拒；也便于对方识别本爬虫。
UA = "Mozilla/5.0 (compatible; zju-game-asset-crawler/1.0)"

# 原始文件下载镜像，按顺序尝试。本网络环境下直连 raw.githubusercontent.com 会
# 超时、jsdelivr 会 301 死循环，只有 ghproxy 镜像稳定（约 0.8s/文件），故把它
# 放在首位、直连作兜底。每个 lambda 把"仓库内相对路径"映射成完整下载 URL。
RAW_MIRRORS = [
    lambda p: f"https://ghproxy.net/https://raw.githubusercontent.com/{REPO}/{BRANCH}/{p}",
    lambda p: f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{p}",
]

# 文件名关键词 -> 类别 的归类规则，按顺序匹配，第一条命中即定类（first match wins）。
# 规则刻意写得具体，目的是只捞真正能当游戏精灵用的图，跳过 UI 测试图集之类的噪声。
# 每条为 (类别, 对小写路径做匹配的正则)。顺序很关键：例如同时含 "space" 与 "bullet"
# 的路径，谁的规则排在前面就归到谁那一类。
RULES: list[tuple[str, re.Pattern]] = [
    ("backgrounds", re.compile(r"/skies/|nebula|starfield|/space\d|background|/bg[_/]")),
    ("effects", re.compile(r"/particles/|explo|explosion|smoke|flare|fire|spark|blast|puff")),
    ("ui", re.compile(r"/ui/|button|/hud|healthbar|health-bar|cursor|crosshair|/icons?/")),
    ("items", re.compile(r"/bullets?/|bullet|laser|missile|/star\b|/coin|gem|crystal|orb|/ball|powerup|power-up|shield|/pickup")),
    ("characters", re.compile(
        r"ship|player|enemy|ufo|alien|invader|plane|jet|rocket|fighter|"
        r"monster|mummy|dude|robot|droid|zombie|skeleton|slime|creature|hero")),
]

# 画风推断规则：从路径关键词猜测素材的视觉风格，供检索时做风格匹配。命中不到则记 generic。
STYLE_HINTS: list[tuple[str, re.Pattern]] = [
    ("pixel", re.compile(r"pixel|8bit|8-bit|metalslug|megaman|mario|invader")),
    ("cartoon", re.compile(r"toon|cartoon|cute")),
]


def classify(path_lower: str) -> str | None:
    """把一个（小写的）文件路径归入某一素材类别。

    思路：按 RULES 定义的顺序逐条用正则匹配，第一条命中的规则决定类别；
    一条都不命中则返回 None（表示这张图不属于我们关心的五类，后续会被丢弃）。
    """
    for cat, rx in RULES:
        if rx.search(path_lower):
            return cat
    return None


def make_tags(stem: str, category: str) -> list[str]:
    """从文件名主干拆出可检索的标签列表，并把类别名放在首位。

    思路：
    1. 用非字母数字字符切分文件名（如 "red-ship_2" -> ["red","ship","2"]）。
    2. 过滤掉纯数字和长度 <= 1 的碎片（噪声，检索无意义）。
    3. 以"类别名 + 各词"为序去重，保证类别一定是第一个标签。
    这些标签会写进 index.json，供后续检索/展示时做关键词辅助。
    """
    words = re.split(r"[^a-z0-9]+", stem.lower())
    words = [w for w in words if w and not w.isdigit() and len(w) > 1]
    seen: list[str] = []
    for w in [category, *words]:
        if w not in seen:
            seen.append(w)
    return seen


def guess_style(path_lower: str) -> str:
    """从路径关键词猜测素材画风（pixel / cartoon），都不命中则记为 generic。

    思路与 classify 相同：按 STYLE_HINTS 顺序做正则匹配，第一条命中即返回。
    结果写进 index.json 的 style 字段，供按风格筛选/检索时使用。
    """
    for style, rx in STYLE_HINTS:
        if rx.search(path_lower):
            return style
    return "generic"


def fetch_tree() -> list[str]:
    """调用 GitHub Git Trees API，返回源仓库中所有 .png 文件的路径列表。

    为什么调这个 API：Git Trees API 支持 ?recursive=1 一次性递归返回整个仓库
    的文件树，因此只需一次 HTTP 请求就能拿到全部文件路径，无需逐目录爬取、
    也无需鉴权（公开仓库只读）。这是整个爬虫唯一的"发现"步骤。

    细节：
    - 带自定义 UA，30s 超时；raise_for_status 让非 2xx 直接抛错。
    - GitHub 对超大仓库的树会截断（truncated=true），此时只能拿到部分结果，
      故做一次告警提示，避免误以为抓全了。
    - 只保留 type 为 blob（文件，非目录）且以 .png 结尾的节点。
    """
    r = requests.get(TREE_API, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("truncated"):
        print("  ! warning: tree truncated by GitHub; results may be partial")
    return [
        node["path"]
        for node in data.get("tree", [])
        if node["type"] == "blob" and node["path"].lower().endswith(".png")
    ]


def download(repo_path: str, dest: Path) -> bool:
    """下载单个文件到 dest，依次尝试各镜像；成功写盘返回 True，否则 False。

    为什么这样下载：raw 文件在本网络环境下直连不稳定，所以按 RAW_MIRRORS 顺序
    （ghproxy 优先、直连兜底）逐个尝试，任一镜像成功即止。

    两道数据校验，避免把"看似成功实则是垃圾"的响应当成有效素材：
    1. 内容小于 200 字节：多为占位空图 / 1px 点，直接判失败（不再试其他镜像，
       因为文件本身就是空的）。
    2. 开头不是 PNG magic number(\\x89PNG)：说明镜像返回的是 HTML 错误页而非图片，
       换下一个镜像重试。
    任一镜像请求抛异常（超时/连接错）则吞掉并尝试下一个，体现爬虫的容错性。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    for make_url in RAW_MIRRORS:
        url = make_url(repo_path)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
            r.raise_for_status()
            # 过小的响应体（占位符 / 1px 点）当作无效，直接判失败。
            if len(r.content) < 200:
                return False
            if not r.content[:8].startswith(b"\x89PNG"):
                continue  # 镜像返回的是 HTML 错误页而非 PNG，换下一个镜像
            dest.write_bytes(r.content)
            return True
        except Exception:  # noqa: BLE001 - 爬虫容错：本镜像出错就试下一个
            continue
    print(f"  ! all mirrors failed for {repo_path}")
    return False


def crawl(limit_per_cat: int | None = None) -> list[dict]:
    """爬虫主流程：发现 -> 归类分桶 -> 逐类下载并生成元数据，返回 index 条目列表。

    整体思路分三步：
    1. 调 fetch_tree() 一次性拿到源仓库全部 PNG 路径。
    2. 过滤噪声后按 classify() 把候选路径分到五个类别桶里。
    3. 按类别逐个下载，在下载的同时构造每张图的元数据（路径/类别/名字/标签/
       画风/来源/许可），并保证本地文件名全局唯一。

    limit_per_cat：每类抓取上限；为 None 时用 DEFAULT_CAPS 里各类的默认配额。
    """
    print(f"[1/3] Fetching asset tree from {REPO} ...")
    all_png = fetch_tree()
    print(f"      {len(all_png)} PNG files in repo")

    # 把候选路径按类别分桶。
    buckets: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for path in all_png:
        pl = path.lower()
        # 只从真正的美术目录取图；跳过测试图、压缩图等噪声。
        if "/assets/" not in pl:
            continue
        if re.search(r"/tests?/|/compressed/|/loader-tests/|/normal-maps/", pl):
            continue
        # 丢弃字体字形表、纹理图集(atlas)、spine 骨骼、3D obj 贴图等：
        # 这些虽能命中关键词，但无法当作独立可用的游戏精灵。
        if re.search(r"/fonts?/|/atlas/|/spine/|trimsheet|/obj/|/text/|-notrim", pl):
            continue
        cat = classify(pl)
        if cat:
            buckets[cat].append(path)

    print("[2/3] Downloading + tagging ...")
    items: list[dict] = []
    seen_rel: set[str] = set()   # 已处理过的源仓库路径（防重复处理同一源文件）
    seen_paths: set[str] = set()  # 已占用的本地目标路径（保证文件名唯一）
    for cat in CATEGORIES:
        cap = limit_per_cat if limit_per_cat else DEFAULT_CAPS.get(cat)
        got = 0
        for src_path in buckets[cat]:
            if cap and got >= cap:
                break
            stem = Path(src_path).stem
            # 仅对真正的重复去重（同一条源仓库路径出现两次）。
            if src_path in seen_rel:
                continue
            # 构造全局唯一的本地文件名。源仓库里同名文件极多（几十个 "player.png"），
            # 甚至父目录名也会撞（多个 "animations/"），因此用"父目录名__文件名"作基名，
            # 若仍冲突则不断追加数字后缀，直到路径空闲——绝不静默覆盖已有文件。
            parent = Path(src_path).parent.name
            base = f"{parent}__{Path(src_path).name}" if parent else Path(src_path).name
            rel = f"{cat}/{base}"
            n = 1
            while rel in seen_paths:
                rel = f"{cat}/{Path(base).stem}_{n}{Path(base).suffix}"
                n += 1
            dest = ASSETS_DIR / rel
            if not download(src_path, dest):
                continue
            seen_rel.add(src_path)
            seen_paths.add(rel)
            # 为这张素材构造一条元数据，稍后统一写入 index.json，供 CLIP 检索器建索引。
            items.append(
                {
                    "path": rel,
                    "category": cat,
                    "name": stem.replace("_", " ").replace("-", " "),
                    "tags": make_tags(stem, cat),
                    "style": guess_style(src_path.lower()),
                    "source": f"github:{REPO}/{src_path}",
                    "license": "phaserjs-examples (sample art)",
                }
            )
            got += 1
            time.sleep(0.02)  # 轻微限速，避免对 raw 镜像请求过猛
        print(f"      {cat:12s} {got:4d} assets")

    return items


def save_index(items: list[dict]) -> None:
    """把爬取得到的元数据列表写入 assets/index.json。

    用 ensure_ascii=False 保留非 ASCII 字符原样、indent=2 便于人工查看/diff。
    这份 index.json 是本爬虫的最终产物，也是后续检索阶段的唯一输入。
    """
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[3/3] Wrote {len(items)} entries -> {INDEX}")


def main() -> None:
    """命令行入口：解析参数 -> 爬取 -> 写索引 -> 打印每类统计。

    --limit 可临时限制每类抓取数量（便于快速联调，不必每次都拉满 430 张）。
    """
    ap = argparse.ArgumentParser(description="Crawl game-art assets into assets/index.json")
    ap.add_argument("--limit", type=int, default=None,
                    help="max assets per category (for quick testing)")
    args = ap.parse_args()
    items = crawl(limit_per_cat=args.limit)
    save_index(items)
    by_cat = {c: sum(1 for i in items if i["category"] == c) for c in CATEGORIES}
    print("Done. Per-category:", by_cat)


if __name__ == "__main__":
    main()
