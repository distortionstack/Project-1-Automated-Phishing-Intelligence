from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup


def extract_html_features(html: str) -> dict[str, int]:
    features = {
        "n_forms": 0,
        "n_iframes": 0,
        "n_external_links": 0,
        "n_password_inputs": 0,
        "n_hidden_inputs": 0,
        "n_scripts": 0,
        "n_meta_refresh": 0,
        "has_favicon": 0,
        "external_action": 0,
        "suspicious_js": 0,
        "title_length": 0,
        "html_length": len(html),
    }
    if not html:
        return features

    soup = BeautifulSoup(html, "html.parser")
    features["n_forms"] = len(soup.find_all("form"))
    features["n_iframes"] = len(soup.find_all("iframe"))
    features["n_scripts"] = len(soup.find_all("script"))
    features["n_password_inputs"] = len(soup.find_all("input", {"type": "password"}))
    features["n_hidden_inputs"] = len(soup.find_all("input", {"type": "hidden"}))

    links = soup.find_all("a", href=True)
    features["n_external_links"] = sum(
        1 for link in links if link["href"].startswith("http") and urlparse(link["href"]).netloc != ""
    )

    forms = soup.find_all("form", action=True)
    features["external_action"] = int(any(form["action"].startswith("http") for form in forms))
    features["n_meta_refresh"] = len(soup.find_all("meta", attrs={"http-equiv": "refresh"}))
    features["has_favicon"] = int(bool(soup.find("link", rel=lambda rel: rel and "icon" in rel)))

    javascript = " ".join(script.get_text() for script in soup.find_all("script"))
    suspicious_keywords = [
        "eval(",
        "atob(",
        "unescape(",
        "document.write(",
        "window.location",
        "fromCharCode",
    ]
    features["suspicious_js"] = sum(1 for keyword in suspicious_keywords if keyword in javascript)

    title = soup.find("title")
    features["title_length"] = len(title.get_text()) if title else 0
    return features
