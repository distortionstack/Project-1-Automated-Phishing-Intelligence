from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phishing_intel.config import Settings
from src.phishing_intel.pipeline import run_pipeline


class PipelineSmokeTests(unittest.TestCase):
    def test_offline_pipeline_generates_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(output_dir=Path(tmpdir), example_dir=Path("example"))
            artifacts = run_pipeline(
                n_urls=6,
                use_browser=False,
                offline_only=True,
                settings=settings,
            )

            self.assertTrue(artifacts.features_path.exists())
            self.assertTrue(artifacts.report_path.exists())
            self.assertTrue(artifacts.metrics_path.exists())
            self.assertIn("fallback_used", artifacts.features.columns)
            self.assertIn("capture_mode", artifacts.report.columns)
            self.assertIn("test_f1", artifacts.metrics)


if __name__ == "__main__":
    unittest.main()
