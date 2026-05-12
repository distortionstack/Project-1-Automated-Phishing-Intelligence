from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phishing_intel.browser import BrowserInstrument
from src.phishing_intel.config import Settings
from src.phishing_intel.contracts import UrlRecord


class BrowserFallbackTests(unittest.TestCase):
    def test_no_browser_uses_visible_fallback_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(output_dir=Path(tmpdir), example_dir=Path("example"))
            settings.ensure_output_dirs()
            browser = BrowserInstrument(settings=settings, use_browser=False)

            snapshot = browser.capture(
                UrlRecord(url="https://phish-login.example.tk", label=1, source="fixture"),
                idx=0,
            )

            self.assertTrue(snapshot.fallback_used)
            self.assertEqual(snapshot.capture_mode, "fallback")
            self.assertEqual(snapshot.error_reason, "browser_disabled")
            self.assertTrue(snapshot.html)
            if snapshot.screenshot_path:
                self.assertTrue(Path(snapshot.screenshot_path).exists())


if __name__ == "__main__":
    unittest.main()
