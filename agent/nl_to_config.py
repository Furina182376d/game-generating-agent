"""Stage 1: Natural language description -> structured GameConfig.

Uses Claude with a tool/JSON-schema constraint so the output is always a
valid GameConfig. Falls back to a deterministic default if the API is
unavailable, so the rest of the pipeline stays testable offline.
"""
from __future__ import annotations

import json
import os

from .schema import GameConfig

SYSTEM_PROMPT = """You are a game design compiler. Convert a user's short \
natural-language description into a structured game configuration.

Rules:
- Pick sensible defaults where the user is silent.
- `sprite_query` / `background_query` fields must be short English visual \
phrases suitable for CLIP image retrieval (e.g. "red enemy fighter jet").
- Include 2-4 distinct enemy types with varied movement patterns.
- `style_keywords` should capture the requested visual style for asset matching.
Return ONLY the configuration via the provided tool."""


def _config_json_schema() -> dict:
    """Anthropic tool input_schema derived from the pydantic model."""
    return GameConfig.model_json_schema()


def nl_to_config(description: str, model: str | None = None) -> GameConfig:
    """Compile a natural-language description into a GameConfig."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_config(description)

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    model = model or os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[
            {
                "name": "emit_game_config",
                "description": "Emit the structured game configuration.",
                "input_schema": _config_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "emit_game_config"},
        messages=[{"role": "user", "content": description}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == "emit_game_config":
            return GameConfig.model_validate(block.input)

    raise RuntimeError("Model did not return a game config tool call")


def _fallback_config(description: str) -> GameConfig:
    """Offline default so the pipeline runs without an API key."""
    from .schema import EnemySpec

    return GameConfig(
        title="Untitled Shooter",
        theme="space war",
        art_style="pixel",
        enemies=[
            EnemySpec(type="straight", hp=1, sprite_query="small enemy ship"),
            EnemySpec(type="zigzag", hp=2, sprite_query="fast enemy fighter"),
        ],
        style_keywords=["space", "pixel", "neon"],
    )


if __name__ == "__main__":
    import sys

    desc = " ".join(sys.argv[1:]) or "a retro space shooter with waves of aliens"
    cfg = nl_to_config(desc)
    print(json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))
