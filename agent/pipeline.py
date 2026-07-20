"""End-to-end pipeline: natural language -> runnable H5 game folder.

    python -m agent.pipeline "a neon space shooter with 3 alien waves" my_game
"""
from __future__ import annotations

import sys
from pathlib import Path

from .nl_to_config import nl_to_config
from .asset_retriever import AssetRetriever
from .code_generator import generate

OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "output"


def run(description: str, name: str = "game", skip_assets: bool = False) -> Path:
    print(f"[1/3] Understanding: {description!r}")
    cfg = nl_to_config(description)
    print(f"      -> {cfg.title} ({cfg.genre}, {cfg.art_style})")

    if not skip_assets:
        print("[2/3] Retrieving assets...")
        try:
            AssetRetriever().resolve(cfg)
        except FileNotFoundError:
            print("      ! asset index not built yet; skipping (run crawler first)")
    else:
        print("[2/3] Skipping asset retrieval")

    print("[3/3] Generating game code...")
    out = OUTPUT_ROOT / name
    index = generate(cfg, out)
    print(f"Done. Open {index}")
    return index


if __name__ == "__main__":
    desc = sys.argv[1] if len(sys.argv) > 1 else "a retro space shooter"
    name = sys.argv[2] if len(sys.argv) > 2 else "game"
    run(desc, name)
