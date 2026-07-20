"""Shared data schema for the game-generation pipeline.

The GameConfig is the contract between every stage:
    NL description --> GameConfig --> asset selection --> code generation
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

AssetCategory = Literal["characters", "backgrounds", "items", "ui", "effects"]


class EnemySpec(BaseModel):
    type: str = Field(description="movement pattern, e.g. straight/zigzag/homing")
    hp: int = 1
    speed: float = 120.0
    sprite_query: str = Field(description="semantic query used to retrieve a sprite")
    sprite: Optional[str] = Field(default=None, description="resolved asset path")


class PlayerSpec(BaseModel):
    speed: float = 200.0
    fire_rate: float = 0.25
    lives: int = 3
    sprite_query: str = "player spaceship"
    sprite: Optional[str] = None


class GameConfig(BaseModel):
    """Structured, engine-agnostic description of a game to generate."""

    title: str
    genre: Literal[
        "shooter", "platformer", "puzzle", "tower_defense"
    ] = "shooter"
    theme: str = Field(description="e.g. 'space war', 'deep ocean', 'fantasy'")
    art_style: str = Field(description="e.g. 'pixel', 'cartoon', 'realistic'")

    player: PlayerSpec = PlayerSpec()
    enemies: list[EnemySpec] = Field(default_factory=list)

    background_query: str = "starfield space background"
    background: Optional[str] = None

    win_condition: str = "survive and reach target score"
    target_score: int = 1000
    difficulty: Literal["easy", "progressive", "hard"] = "progressive"

    # free-form style keywords used to bias asset retrieval
    style_keywords: list[str] = Field(default_factory=list)
