from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Settings:
    output_dir: Path = Path("output")
    screenshot_dirname: str = "screenshots"
    jobs_dirname: str = "jobs"
    example_dir: Path = Path("example")
    browser_timeout_ms: int = 15000
    http_timeout_seconds: int = 8
    viewport_width: int = 1280
    viewport_height: int = 800
    random_seed: int = 42
    suspicious_tlds: set[str] = field(
        default_factory=lambda: {
            "tk",
            "ml",
            "gq",
            "cf",
            "ga",
            "xyz",
            "top",
            "club",
            "work",
            "icu",
            "vip",
            "online",
            "site",
            "fun",
        }
    )
    brand_keywords: set[str] = field(
        default_factory=lambda: {
            "paypal",
            "facebook",
            "amazon",
            "google",
            "apple",
            "microsoft",
            "netflix",
            "bank",
            "secure",
            "login",
            "account",
            "verify",
            "update",
            "confirm",
        }
    )
    brand_colors: dict[str, list[tuple[int, int, int]]] = field(
        default_factory=lambda: {
            "paypal": [(0, 70, 127), (0, 157, 220)],
            "facebook": [(24, 119, 242), (255, 255, 255)],
            "google": [(66, 133, 244), (234, 67, 53), (52, 168, 83), (251, 188, 5)],
            "amazon": [(255, 153, 0), (35, 47, 62)],
            "microsoft": [(243, 83, 37), (127, 186, 0), (0, 161, 241), (255, 187, 0)],
            "apple": [(51, 51, 51), (255, 255, 255)],
            "netflix": [(229, 9, 20), (0, 0, 0)],
            "bankofam": [(228, 32, 38), (0, 51, 160)],
        }
    )

    @property
    def screenshot_dir(self) -> Path:
        return self.output_dir / self.screenshot_dirname

    @property
    def jobs_dir(self) -> Path:
        return self.output_dir / self.jobs_dirname

    @property
    def features_path(self) -> Path:
        return self.output_dir / "features.csv"

    @property
    def report_path(self) -> Path:
        return self.output_dir / "phishing_report.csv"

    @property
    def metrics_path(self) -> Path:
        return self.output_dir / "metrics.json"

    def ensure_output_dirs(self) -> None:
        self.output_dir.mkdir(exist_ok=True)
        self.screenshot_dir.mkdir(exist_ok=True)
        self.jobs_dir.mkdir(exist_ok=True)

    def with_output_dir(self, output_dir: Path) -> "Settings":
        return Settings(
            output_dir=output_dir,
            screenshot_dirname=self.screenshot_dirname,
            jobs_dirname=self.jobs_dirname,
            example_dir=self.example_dir,
            browser_timeout_ms=self.browser_timeout_ms,
            http_timeout_seconds=self.http_timeout_seconds,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            random_seed=self.random_seed,
            suspicious_tlds=set(self.suspicious_tlds),
            brand_keywords=set(self.brand_keywords),
            brand_colors={brand: list(colors) for brand, colors in self.brand_colors.items()},
        )


DEFAULT_SETTINGS = Settings()
