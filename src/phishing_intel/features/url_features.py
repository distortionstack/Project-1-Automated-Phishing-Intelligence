from __future__ import annotations

import math
import re
from urllib.parse import urlparse

from ..config import Settings


def extract_url_features(url: str, settings: Settings) -> dict[str, float | int]:
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path

    has_ip = bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$", domain))
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    keyword_hits = sum(1 for keyword in settings.brand_keywords if keyword in url.lower())
    subdomains = domain.split(".")[:-2]
    special_chars = len(re.findall(r"[-@_%~]", url))

    return {
        "url_length": len(url),
        "domain_length": len(domain),
        "n_dots": domain.count("."),
        "n_hyphens": domain.count("-"),
        "has_ip": int(has_ip),
        "has_at_symbol": int("@" in url),
        "has_double_slash": int("//" in path),
        "suspicious_tld": int(tld in settings.suspicious_tlds),
        "brand_kw_in_url": keyword_hits,
        "n_subdomains": len(subdomains),
        "url_entropy": shannon_entropy(domain),
        "special_char_count": special_chars,
        "path_depth": path.count("/"),
        "has_https": int(parsed.scheme == "https"),
        "query_param_count": len(parsed.query.split("&")) if parsed.query else 0,
    }


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0

    frequencies: dict[str, int] = {}
    for char in value:
        frequencies[char] = frequencies.get(char, 0) + 1

    total = len(value)
    return -sum((count / total) * math.log2(count / total) for count in frequencies.values())
