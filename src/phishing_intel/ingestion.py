from __future__ import annotations

import io
import logging
import zipfile

from .config import Settings
from .contracts import UrlRecord
from .utils import http_get

logger = logging.getLogger(__name__)


class DataIngestion:
    def __init__(self, settings: Settings):
        self.settings = settings
        example_dir = settings.example_dir
        self.demo_malicious = [
            example_dir / "paypal_login_clone" / "index.html",
            example_dir / "Instagram-and-Facebook-login-page" / "facebook-login.html",
            example_dir / "Google-login-page-clone" / "index.html",
            example_dir / "microsoft-login-clone" / "index.html",
            "https://stackoverflow.com/users/login?ssrc=head&returnurl=https%3a%2f%2fstackoverflow.com%2fquestions",
        ]
        self.demo_benign = [
            "https://www.paypal.com/signin?country.x=TH&locale.x=en_GB&langTgl=en",
            "https://www.facebook.com",
            "https://www.google.com",
            "https://www.microsoft.com",
            "https://stackoverflow.com"
        ]

    def get_url_records(
        self,
        n_phish: int = 10,
        n_benign: int = 10,
        offline_only: bool = False,
    ) -> list[UrlRecord]:
        phish_urls = self.demo_malicious[:n_phish]
        benign_urls = self.demo_benign[:n_benign]

        if not offline_only:
            fetched_phish = self._try_phishtank(n_phish)
            fetched_benign = self._try_tranco(n_benign)
            if fetched_phish:
                phish_urls = fetched_phish
            if fetched_benign:
                benign_urls = fetched_benign

        records = [UrlRecord(url=str(url), label=1, source="phishtank") for url in phish_urls]
        records.extend(UrlRecord(url=str(url), label=0, source="tranco") for url in benign_urls)

        logger.info(
            "Loaded %s URLs (%s phishing, %s benign)",
            len(records),
            len(phish_urls),
            len(benign_urls),
        )
        return records

    def _try_phishtank(self, n: int) -> list[str] | None:
        try:
            response = http_get(
                "http://data.phishtank.com/data/online-valid.json",
                timeout=5,
                headers={"User-Agent": "phishtank/demo"},
            )
            data = response.json()
            return [item["url"] for item in data[:n]]
        except Exception as exc:
            logger.warning("PhishTank fetch failed, using demo data: %s", exc)
            return None

    def _try_tranco(self, n: int) -> list[str] | None:
        try:
            response = http_get("https://tranco-list.eu/top-1m.csv.zip", timeout=5)
            archive = zipfile.ZipFile(io.BytesIO(response.content))
            lines = archive.read(archive.namelist()[0]).decode().splitlines()
            return [f"https://{line.split(',')[1]}" for line in lines[:n]]
        except Exception as exc:
            logger.warning("Tranco fetch failed, using demo data: %s", exc)
            return None
