from __future__ import annotations

import argparse
import logging

from src.phishing_intel import DEFAULT_SETTINGS, run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Phishing Intelligence")
    parser.add_argument("--n-urls", type=int, default=20, help="Number of URLs to analyze")
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Use bundled demo data only and skip live network sources",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Skip Playwright and use deterministic fallback capture instead",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )
    artifacts = run_pipeline(
        n_urls=args.n_urls,
        use_browser=not args.no_browser,
        offline_only=args.offline_only,
        settings=DEFAULT_SETTINGS,
    )
    print(f"Features saved to {artifacts.features_path}")
    print(f"Report saved to {artifacts.report_path}")
    print(f"Metrics saved to {artifacts.metrics_path}")


if __name__ == "__main__":
    main()
