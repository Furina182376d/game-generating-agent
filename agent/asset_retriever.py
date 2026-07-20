"""Stage 2: semantic asset retrieval over the crawled asset library.

Builds/loads a CLIP embedding index and resolves the `*_query` fields in a
GameConfig to concrete asset paths. Text and image share the CLIP space, so a
text query like "red enemy fighter jet" retrieves the closest sprite.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schema import GameConfig

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
INDEX_META = ASSETS_DIR / "index.json"
EMB_FILE = ASSETS_DIR / "embeddings.npy"


class AssetRetriever:
    """Lazy CLIP-backed retriever. Import-time cheap; model loads on first use."""

    # openai weights were trained with QuickGELU; the -quickgelu model variant
    # matches that so activations line up (plain ViT-B-32 warns + degrades).
    def __init__(self, model_name: str = "ViT-B-32-quickgelu", pretrained: str = "openai"):
        self.model_name = model_name
        self.pretrained = pretrained
        self._model = None
        self._tokenizer = None
        self._preprocess = None
        self._meta: list[dict] = []
        self._emb = None  # np.ndarray [N, D], L2-normalized

    # --- model plumbing -------------------------------------------------
    def _ensure_model(self):
        if self._model is not None:
            return
        import open_clip
        import torch

        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=self.pretrained
        )
        self._model.eval()
        self._tokenizer = open_clip.get_tokenizer(self.model_name)
        self._torch = torch

    def _encode_text(self, text: str):
        self._ensure_model()
        with self._torch.no_grad():
            tokens = self._tokenizer([text])
            feat = self._model.encode_text(tokens)
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat.cpu().numpy()[0]

    def _encode_image(self, path: Path):
        from PIL import Image

        self._ensure_model()
        img = self._preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
        with self._torch.no_grad():
            feat = self._model.encode_image(img)
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat.cpu().numpy()[0]

    # --- index build / load --------------------------------------------
    def build_index(self) -> None:
        """Embed every asset listed in index.json and cache to disk."""
        import numpy as np

        meta = json.loads(INDEX_META.read_text(encoding="utf-8"))
        embs = []
        kept = []
        for item in meta:
            path = ASSETS_DIR / item["path"]
            if not path.exists():
                continue
            embs.append(self._encode_image(path))
            kept.append(item)
        self._emb = np.vstack(embs).astype("float32")
        self._meta = kept
        np.save(EMB_FILE, self._emb)
        print(f"Indexed {len(kept)} assets -> {EMB_FILE}")

    def load_index(self) -> None:
        import numpy as np

        self._meta = json.loads(INDEX_META.read_text(encoding="utf-8"))
        self._emb = np.load(EMB_FILE)

    # --- query ----------------------------------------------------------
    def search(
        self, query: str, category: Optional[str] = None, top_k: int = 1
    ) -> list[dict]:
        import numpy as np

        if self._emb is None:
            self.load_index()
        qv = self._encode_text(query)
        sims = self._emb @ qv  # cosine (all normalized)

        order = np.argsort(-sims)
        results = []
        for idx in order:
            item = self._meta[idx]
            if category and item.get("category") != category:
                continue
            results.append({**item, "score": float(sims[idx])})
            if len(results) >= top_k:
                break
        return results

    # --- pipeline entry -------------------------------------------------
    def resolve(self, cfg: GameConfig) -> GameConfig:
        """Fill in the concrete asset paths on a GameConfig in place."""
        style = " ".join(cfg.style_keywords)

        def q(text: str, cat: str) -> Optional[str]:
            hits = self.search(f"{text} {style}".strip(), category=cat, top_k=1)
            return hits[0]["path"] if hits else None

        cfg.player.sprite = q(cfg.player.sprite_query, "characters")
        cfg.background = q(cfg.background_query, "backgrounds")
        for enemy in cfg.enemies:
            enemy.sprite = q(enemy.sprite_query, "characters")
        return cfg


if __name__ == "__main__":
    import sys

    r = AssetRetriever()
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        r.build_index()
    else:
        for hit in r.search(" ".join(sys.argv[1:]) or "spaceship", top_k=5):
            print(f"{hit['score']:.3f}  {hit['path']}")
