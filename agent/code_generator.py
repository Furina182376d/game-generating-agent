"""Stage 3: GameConfig (+ resolved assets) -> runnable Phaser.js H5 game.

Fills a parameterized Phaser template with the config. The template is plain
JS with `{{PLACEHOLDER}}` markers so generation is deterministic and
debuggable; the LLM is used upstream (config) rather than to emit raw code,
which keeps output reliably runnable.

Output is a SINGLE self-contained index.html: Phaser, the game code, and every
image asset (as data URIs) are inlined. This means the file can be downloaded
or double-clicked in isolation and still runs — no sibling files, no server,
no network. This matters for grading/demo where one game = one shareable file.
"""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from .schema import GameConfig

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"


def _template_for(genre: str) -> Path:
    mapping = {"shooter": "shooter_base.js"}
    name = mapping.get(genre, "shooter_base.js")
    return TEMPLATE_DIR / name


def _data_uri(rel: str | None) -> str | None:
    """Encode an asset (relative to ASSETS_DIR) as a base64 data URI, or None."""
    if not rel:
        return None
    src = ASSETS_DIR / rel
    if not src.exists():
        return None
    mime = mimetypes.guess_type(src.name)[0] or "image/png"
    data = base64.b64encode(src.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def generate(cfg: GameConfig, out_dir: str | Path) -> Path:
    """Render a single self-contained index.html. Returns its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Inline resolved assets as data URIs so the HTML has zero external deps.
    cfg.player.sprite = _data_uri(cfg.player.sprite)
    cfg.background = _data_uri(cfg.background)
    for enemy in cfg.enemies:
        enemy.sprite = _data_uri(enemy.sprite)

    template = _template_for(cfg.genre).read_text(encoding="utf-8")
    game_js = template.replace(
        "{{GAME_CONFIG}}", json.dumps(cfg.model_dump(), ensure_ascii=False, indent=2)
    ).replace("{{GAME_TITLE}}", cfg.title)

    phaser_src = VENDOR_DIR / "phaser.min.js"
    if not phaser_src.exists():
        raise FileNotFoundError(
            f"Phaser not vendored at {phaser_src}. "
            "Download it once: see README (vendor/ setup)."
        )
    phaser_js = phaser_src.read_text(encoding="utf-8")

    html = _html_shell(cfg.title, phaser_js, game_js)
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def _html_shell(title: str, phaser_js: str, game_js: str) -> str:
    # Everything inlined: one file, no siblings, no network, runs on file://.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, \
maximum-scale=1.0, user-scalable=no" />
  <title>{title}</title>
  <style>
    html, body {{ margin: 0; height: 100%; background: #0b0e1a; overflow: hidden; }}
    #game {{ width: 100vw; height: 100vh; display: flex;
             align-items: center; justify-content: center; }}
  </style>
</head>
<body>
  <div id="game"></div>
  <script>{phaser_js}</script>
  <script>{game_js}</script>
</body>
</html>
"""


if __name__ == "__main__":
    from .nl_to_config import _fallback_config

    cfg = _fallback_config("demo")
    path = generate(cfg, "output/demo")
    print(f"Generated {path}")
