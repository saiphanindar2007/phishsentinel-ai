"""
PhishSentinel AI — URL & Domain Intelligence Module
-----------------------------------------------------
Detects typosquatting, homograph attacks, suspicious TLDs, IP-based URLs,
and other lexical red flags in a URL.

Design note:
This module ALWAYS returns a usable score, even with zero training data,
because `heuristic_score()` is a hand-tuned weighted rule engine. Once you
run `training/train_url_model.py` on a labelled dataset (e.g. PhishTank +
Kaggle phishing URLs), a real LogisticRegression/XGBoost model is saved to
`URL_MODEL_PATH` and this module will prefer it automatically — same
function signature, drop-in upgrade, nothing else in the codebase changes.
"""
import re
import math
import difflib
import ipaddress
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import List
import os

try:
    import joblib
except ImportError:
    joblib = None

from app.config import URL_MODEL_PATH
from app.models.shap_explainer import shap_explainer
from app.models.brands import TRUSTED_BRAND_DOMAINS

# Brand list lives in app/models/brands.py (shared with email-header checks).

SUSPICIOUS_KEYWORDS = [
    "login", "verify", "secure", "account", "update", "confirm", "banking",
    "password", "signin", "webscr", "suspend", "unlock", "reward", "gift",
    "invoice", "billing", "urgent", "click", "免费", "bonus",
]

SUSPICIOUS_TLDS = {
    "zip", "mov", "xyz", "top", "gq", "cf", "tk", "ml", "ga", "work", "click", "loan",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly",
}


@dataclass
class URLFeatures:
    length: int = 0
    num_dots: int = 0
    num_hyphens: int = 0
    num_digits: int = 0
    num_subdomains: int = 0
    has_ip_host: bool = False
    has_at_symbol: bool = False
    has_https: bool = False
    suspicious_tld: bool = False
    is_shortener: bool = False
    suspicious_keyword_hits: int = 0
    typosquat_distance: float = 1.0  # 0 = exact match to a trusted brand, 1 = unrelated
    typosquat_target: str = ""
    raw: str = ""


def _extract_host(url: str) -> str:
    if "://" not in url:
        url = "http://" + url
    return urlparse(url).netloc.lower().split(":")[0]


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def extract_features(url: str) -> URLFeatures:
    url_l = url.lower().strip()
    if "://" not in url_l:
        parse_target = "http://" + url_l
    else:
        parse_target = url_l
    parsed = urlparse(parse_target)
    host = parsed.netloc.split(":")[0]
    path_and_query = (parsed.path or "") + (("?" + parsed.query) if parsed.query else "")

    f = URLFeatures(raw=url)
    f.length = len(url_l)
    f.num_dots = host.count(".")
    f.num_hyphens = host.count("-")
    f.num_digits = sum(c.isdigit() for c in host)
    f.num_subdomains = max(host.count(".") - 1, 0)
    f.has_ip_host = _is_ip(host)
    f.has_at_symbol = "@" in url_l
    f.has_https = parsed.scheme == "https"
    tld = host.split(".")[-1] if "." in host else ""
    f.suspicious_tld = tld in SUSPICIOUS_TLDS
    f.is_shortener = host in URL_SHORTENERS
    f.suspicious_keyword_hits = sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in path_and_query or kw in host)

    # Typosquatting distance: closest trusted brand domain via sequence
    # similarity. Checked two ways — against the full host (catches
    # "paypal-secure.com" style) and against individual hyphen/dot
    # separated tokens (catches "paypa1.something.com" style where the
    # brand name is buried alongside other words).
    best_ratio = 0.0
    best_brand = ""
    core_host = host[4:] if host.startswith("www.") else host
    # Compare the registrable name WITHOUT the TLD, not the full host —
    # comparing "example.com" to "apple.com" as whole strings gives a
    # deceptively high ratio (0.80) purely because both end in ".com",
    # which would falsely flag almost any two same-TLD domains as
    # typosquats of each other. Stripping the TLD before comparing fixes
    # that false-positive while still catching real typosquats like
    # "paypa1-secure.com" vs "paypal".
    core_host_no_tld = core_host.rsplit(".", 1)[0] if "." in core_host else core_host
    tokens = re.split(r"[.\-]", core_host)
    concat_host = re.sub(r"[.\-\d]", "", core_host)  # "icici-bank-secure.gq" -> "icicibanksecuregq"
    for brand in TRUSTED_BRAND_DOMAINS:
        brand_name = brand.split(".")[0]
        whole_ratio = difflib.SequenceMatcher(None, core_host_no_tld, brand_name).ratio()
        token_ratio = max(
            (difflib.SequenceMatcher(None, tok, brand_name).ratio() for tok in tokens if tok), default=0.0
        )
        # Catches brand names split across hyphens, e.g. "icici-bank-secure"
        # containing "icicibank" once separators are stripped.
        concat_ratio = 0.85 if brand_name in concat_host else 0.0
        ratio = max(whole_ratio, token_ratio, concat_ratio)
        if ratio > best_ratio:
            best_ratio = ratio
            best_brand = brand
    if core_host == best_brand:
        f.typosquat_distance = 1.0  # exact match to the real brand = not a typosquat
    elif best_ratio > 0.72:
        # High similarity to a brand but NOT an exact match -> suspicious.
        # Convert similarity into a "distance-from-safe" style score.
        f.typosquat_distance = 1.0 - best_ratio
        f.typosquat_target = best_brand
    else:
        f.typosquat_distance = 1.0  # unrelated to any known brand, neutral

    return f


def heuristic_score(f: URLFeatures) -> float:
    """Hand-tuned weighted rule engine. Returns a phishing-likelihood in [0, 1]."""
    score = 0.0
    if f.has_ip_host:
        score += 0.30
    if f.has_at_symbol:
        score += 0.15
    if not f.has_https:
        score += 0.10
    if f.suspicious_tld:
        score += 0.15
    if f.is_shortener:
        score += 0.10
    if f.num_subdomains >= 3:
        score += 0.10
    if f.num_hyphens >= 3:
        score += 0.08
    score += min(f.suspicious_keyword_hits * 0.07, 0.25)
    if f.typosquat_target:
        # closer to a real brand (small distance) => more suspicious
        score += max(0.0, 0.35 - f.typosquat_distance * 0.35)
    if f.length > 90:
        score += 0.08
    return max(0.0, min(1.0, score))


class URLAnalyzer:
    def __init__(self, model_path: str = URL_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.feature_order = [
            "length", "num_dots", "num_hyphens", "num_digits", "num_subdomains",
            "has_ip_host", "has_at_symbol", "has_https", "suspicious_tld",
            "is_shortener", "suspicious_keyword_hits", "typosquat_distance",
        ]
        self.reload()

    def reload(self, model_path: str = None) -> bool:
        """(Re)loads the trained model from disk, re-attaching SHAP if
        available. Called once at startup, and callable again any time
        (see app/routers/admin.py's POST /admin/reload-models) after
        training/train_url_model.py writes a fresh artifact — lets a
        retrained model go live without restarting the server. Returns
        True if a model was loaded, False if falling back to heuristics."""
        if model_path:
            self.model_path = model_path
        self.model = None
        if joblib and os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                background = None
                background_path = os.path.join(os.path.dirname(self.model_path), "url_model_background.pkl")
                if os.path.exists(background_path):
                    try:
                        background = joblib.load(background_path)
                    except Exception:
                        background = None
                shap_explainer.attach(self.model, background_data=background)
            except Exception:
                self.model = None  # corrupt/incompatible file -> fall back safely
        return self.model is not None

    def _vectorize(self, f: URLFeatures) -> List[float]:
        return [
            f.length, f.num_dots, f.num_hyphens, f.num_digits, f.num_subdomains,
            float(f.has_ip_host), float(f.has_at_symbol), float(f.has_https),
            float(f.suspicious_tld), float(f.is_shortener), f.suspicious_keyword_hits,
            f.typosquat_distance,
        ]

    def analyze(self, url: str) -> dict:
        f = extract_features(url)
        shap_reasons = None
        if self.model is not None:
            vector = self._vectorize(f)
            proba = self.model.predict_proba([vector])[0][1]
            score = float(proba)
            method = "trained_model"
            shap_reasons = shap_explainer.explain(vector)
        else:
            score = heuristic_score(f)
            method = "heuristic"

        if shap_reasons:
            # A trained model + SHAP available: real per-feature
            # attributions replace the rule-engine's canned strings.
            return {"score": score, "method": "trained_model+shap", "reasons": shap_reasons, "features": f.__dict__}

        reasons = []
        if f.has_ip_host:
            reasons.append("URL uses a raw IP address instead of a domain name")
        if f.typosquat_target:
            reasons.append(f"Domain closely resembles trusted brand '{f.typosquat_target}' (possible typosquat)")
        if f.suspicious_tld:
            reasons.append("Uses a top-level domain commonly abused for phishing")
        if f.suspicious_keyword_hits:
            reasons.append(f"Contains {f.suspicious_keyword_hits} credential-harvesting keyword(s)")
        if not f.has_https:
            reasons.append("No HTTPS encryption")
        if f.is_shortener:
            reasons.append("Uses a URL shortener, hiding the real destination")

        return {"score": score, "method": method, "reasons": reasons, "features": f.__dict__}


# Singleton instance used by the API layer
url_analyzer = URLAnalyzer()
