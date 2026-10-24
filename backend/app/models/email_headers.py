"""
PhishSentinel AI — Email header authentication analysis
-----------------------------------------------------------
Real mail gateways don't judge an email by its words alone — they look at
whether the message actually came from who it claims. This module parses
raw RFC 5322 headers and checks:

  - SPF / DKIM / DMARC results (from the receiving server's
    Authentication-Results header)
  - From vs Return-Path / Reply-To domain mismatches
  - Display-name spoofing ("PayPal Support <x@random.tk>", or a display
    name that embeds a *different* e-mail address)
  - Punycode (xn--) sender domains, a homograph-attack tell

TRUST NOTE: Authentication-Results is only meaningful if it was added by
YOUR mail server. We read the topmost one (the receiving hop) and ignore
older ones, because senders can forge extra copies lower in the chain.
Make sure your MTA strips inbound Authentication-Results headers.

Pure standard library, no network access, deterministic.
"""
import re
from email.parser import HeaderParser
from email.utils import parseaddr
from typing import Dict, List, Optional

from app.models.brands import TRUSTED_BRAND_DOMAINS, brand_name, registrable_domain

_AUTH_RE = re.compile(
    r"\b(spf|dkim|dmarc)\s*=\s*(pass|fail|softfail|neutral|none|temperror|permerror|policy)\b",
    re.IGNORECASE,
)
_EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_DOMAIN_IN_TEXT = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|net|org|in|io|co|info|biz|xyz|top|tk|ml|ga|cf|gq|app|dev|uk))\b", re.IGNORECASE)

# Points added per signal. Kept explicit so the scoring is auditable.
W = {
    "spf_fail": 0.30, "spf_softfail": 0.15, "spf_none": 0.05,
    "dkim_fail": 0.25, "dkim_none": 0.05,
    "dmarc_fail": 0.35, "dmarc_none": 0.05,
    "no_auth_results": 0.10,
    "return_path_mismatch": 0.15,
    "reply_to_mismatch": 0.20,
    "display_name_email": 0.30,
    "display_name_brand": 0.35,
    "punycode": 0.20,
}


def _domain_of(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].lower().strip(" >") if "@" in addr else ""


def parse_auth_results(value: str) -> Dict[str, str]:
    """First occurrence of each mechanism wins: 'spf=pass ... dkim=fail' -> {...}."""
    out: Dict[str, str] = {}
    for mech, result in _AUTH_RE.findall(value or ""):
        out.setdefault(mech.lower(), result.lower())
    return out


def analyze_headers(raw_headers: Optional[str]) -> Optional[dict]:
    """Returns {score, reasons, method, authentication} or None when no
    usable headers were supplied (callers then skip the signal)."""
    if not raw_headers or not raw_headers.strip():
        return None

    msg = HeaderParser().parsestr(raw_headers)
    if not msg.keys():
        return None

    reasons: List[str] = []
    score = 0.0

    display_name, from_addr = parseaddr(msg.get("From", ""))
    from_domain = _domain_of(from_addr)
    from_reg = registrable_domain(from_domain)

    # --- SPF / DKIM / DMARC -------------------------------------------------
    auth_headers = msg.get_all("Authentication-Results") or []
    auth = parse_auth_results(auth_headers[0]) if auth_headers else {}
    if not auth:
        # Fall back to Received-SPF (some MTAs only write that one)
        m = re.match(r"\s*(pass|fail|softfail|neutral|none|temperror|permerror)", msg.get("Received-SPF", "") or "", re.I)
        if m:
            auth["spf"] = m.group(1).lower()

    spf, dkim, dmarc = auth.get("spf"), auth.get("dkim"), auth.get("dmarc")
    if not auth:
        score += W["no_auth_results"]
        reasons.append("Headers contain no SPF/DKIM/DMARC results — sender identity can't be verified")
    else:
        if spf in ("fail", "permerror"):
            score += W["spf_fail"]; reasons.append("SPF failed — the sending server is not authorised for this domain")
        elif spf == "softfail":
            score += W["spf_softfail"]; reasons.append("SPF soft-failed — sending server is probably not authorised")
        elif spf in ("none", "neutral"):
            score += W["spf_none"]
        if dkim in ("fail", "permerror"):
            score += W["dkim_fail"]; reasons.append("DKIM signature failed — message may have been forged or altered")
        elif dkim == "none":
            score += W["dkim_none"]
        if dmarc in ("fail", "permerror"):
            score += W["dmarc_fail"]; reasons.append("DMARC failed — the From domain's own policy rejects this message")
        elif dmarc == "none":
            score += W["dmarc_none"]

    # --- Domain alignment ----------------------------------------------------
    _, rp_addr = parseaddr(msg.get("Return-Path", ""))
    rp_domain = _domain_of(rp_addr)
    if rp_domain and from_domain and registrable_domain(rp_domain) != from_reg:
        score += W["return_path_mismatch"]
        reasons.append(f"Return-Path domain ({rp_domain}) differs from From domain ({from_domain})")

    _, rt_addr = parseaddr(msg.get("Reply-To", ""))
    rt_domain = _domain_of(rt_addr)
    if rt_domain and from_domain and registrable_domain(rt_domain) != from_reg:
        score += W["reply_to_mismatch"]
        reasons.append(f"Replies are redirected to a different domain ({rt_domain})")

    # --- Display-name spoofing -----------------------------------------------
    name_l = (display_name or "").lower()
    if name_l and from_reg:
        embedded = {registrable_domain(d.lower()) for d in _EMAIL_IN_TEXT.findall(display_name)}
        embedded |= {registrable_domain(d.lower()) for d in _DOMAIN_IN_TEXT.findall(display_name)}
        embedded.discard(from_reg)
        if embedded:
            score += W["display_name_email"]
            reasons.append(f"Display name shows '{sorted(embedded)[0]}' but the message is from {from_domain}")
        else:
            for brand_domain in TRUSTED_BRAND_DOMAINS:
                name = brand_name(brand_domain)
                if len(name) >= 4 and name in re.sub(r"[^a-z0-9]", "", name_l) and from_reg != brand_domain:
                    score += W["display_name_brand"]
                    reasons.append(f"Display name claims '{name}' but sender domain is {from_domain}")
                    break

    if "xn--" in from_domain:
        score += W["punycode"]
        reasons.append("Sender domain uses punycode (xn--), a common look-alike (homograph) trick")

    return {
        "score": max(0.0, min(1.0, score)),
        "method": "header_analysis",
        "reasons": reasons,
        "authentication": {
            "spf": spf or "unknown",
            "dkim": dkim or "unknown",
            "dmarc": dmarc or "unknown",
            "from_domain": from_domain or None,
            "return_path_domain": rp_domain or None,
            "reply_to_domain": rt_domain or None,
        },
    }
