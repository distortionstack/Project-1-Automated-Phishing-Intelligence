from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import numpy as np

try:
    from PIL import Image
    from PIL.ImageStat import Stat
except ImportError:
    Image = None
    Stat = None

try:
    import imagehash
except ImportError:
    imagehash = None

from ..config import Settings


class VisualFeatureExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._brand_reference_hashes = self._build_brand_references()

    def extract(self, screenshot_path: str | None, url: str) -> dict[str, float | int]:
        features = {
            "min_brand_hamming": 255,
            "closest_brand_match": 0.0,
            "brand_color_score": 0.0,
            "dominant_hue": 0.0,
            "color_variance": 0.0,
            "red_ratio": 0.0,
            "green_ratio": 0.0,
            "blue_ratio": 0.0,
        }
        if not screenshot_path or not Path(screenshot_path).exists():
            return features
        if Image is None or imagehash is None or Stat is None:
            return features

        image = Image.open(screenshot_path).convert("RGB")
        perceptual_hash = imagehash.phash(image, hash_size=16)
        min_distance = 255
        for reference_hash in self._brand_reference_hashes.values():
            distance = perceptual_hash - reference_hash
            if distance < min_distance:
                min_distance = distance

        features["min_brand_hamming"] = min_distance
        features["closest_brand_match"] = 1.0 - (min_distance / 256)

        small = image.resize((64, 64))
        pixels = np.array(small).reshape(-1, 3).astype(float)
        features["red_ratio"] = float(pixels[:, 0].mean() / 255)
        features["green_ratio"] = float(pixels[:, 1].mean() / 255)
        features["blue_ratio"] = float(pixels[:, 2].mean() / 255)
        features["color_variance"] = float(pixels.var())

        stat = Stat(small)
        features["dominant_hue"] = float(sum(stat.mean) / 3 / 255)
        features["brand_color_score"] = self._brand_color_match(pixels, urlparse(url).netloc.lower())
        return features

    def _brand_color_match(self, pixels: np.ndarray, domain: str) -> float:
        _ = domain
        scores = []
        page_mean = pixels.mean(axis=0)
        for colors in self.settings.brand_colors.values():
            brand_pixels = np.array(colors, dtype=float)
            distances = [np.linalg.norm(page_mean - color) for color in brand_pixels]
            scores.append(min(distances))
        min_score = min(scores) if scores else 255
        return float(1.0 - min(min_score / 255, 1.0))

    def _build_brand_references(self) -> dict[str, object]:
        if Image is None or imagehash is None:
            return {}

        refs: dict[str, object] = {}
        for brand, colors in self.settings.brand_colors.items():
            image = Image.new("RGB", (1280, 800), colors[0])
            refs[brand] = imagehash.phash(image, hash_size=16)
        return refs
