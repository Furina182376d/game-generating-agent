"""Collect 300-500 game asset images and build assets/index.json.

Primary source: Kenney.nl asset packs (CC0, free for any use) and
OpenGameArt. This scaffold defines the flow; per-source parsers are filled in
during Phase 1. Every downloaded file is recorded with category + tags so the
retriever can index it.

Categories: characters / backgrounds / items / ui / effects
"""
from __future__ import annotations

import json
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
INDEX = ASSETS_DIR / "index.json"

CATEGORIES = ["characters", "backgrounds", "items", "ui", "effects"]


def load_index() -> list[dict]:
    if INDEX.exists():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return []


def save_index(items: list[dict]) -> None:
    INDEX.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(items)} entries -> {INDEX}")


def add_entry(
    items: list[dict],
    path: str,
    category: str,
    name: str,
    tags: list[str],
    style: str = "",
    source: str = "",
    license: str = "CC0",
) -> None:
    """Append a normalized metadata record for one asset."""
    assert category in CATEGORIES, f"bad category: {category}"
    items.append(
        {
            "path": path,  # relative to assets/
            "category": category,
            "name": name,
            "tags": tags,
            "style": style,
            "source": source,
            "license": license,
        }
    )


def download(url: str, dest: Path) -> bool:
    """Fetch a single file. Returns True on success."""
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as exc:  # noqa: BLE001 - crawler tolerance
        print(f"  ! failed {url}: {exc}")
        return False


# TODO(Phase 1): implement per-source scrapers, e.g.
#   def scrape_kenney(pack_url): ...
#   def scrape_opengameart(query): ...
# Each should call download() + add_entry() to grow index.json to 300-500 items.


if __name__ == "__main__":
    items = load_index()
    print(f"Current index: {len(items)} assets")
    print("Implement source scrapers in Phase 1, then re-run to grow the index.")
    save_index(items)
