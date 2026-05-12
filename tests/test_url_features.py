from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phishing_intel.config import Settings
from src.phishing_intel.features.url_features import extract_url_features


class UrlFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings()

    def test_suspicious_url_signals_are_detected(self) -> None:
        url = "http://secure-paypal-login.example.tk/account/verify?session=1&x=2"
        features = extract_url_features(url, self.settings)

        self.assertEqual(features["has_https"], 0)
        self.assertEqual(features["suspicious_tld"], 1)
        self.assertGreaterEqual(features["brand_kw_in_url"], 3)
        self.assertEqual(features["query_param_count"], 2)

    def test_https_benign_url_is_counted_correctly(self) -> None:
        url = "https://www.example.com/login"
        features = extract_url_features(url, self.settings)

        self.assertEqual(features["has_https"], 1)
        self.assertEqual(features["n_dots"], 2)
        self.assertEqual(features["path_depth"], 1)


if __name__ == "__main__":
    unittest.main()
