"""
PhishSentinel AI — Attack Storyline / Redirect-Chain Reconstruction
---------------------------------------------------------------------
PhishSentinel doesn't follow live HTTP redirects (no outbound network
calls — see README for the ₹0 / offline-friendly design), but a single
email routinely carries several distinct links: a tracking/shortener
link, the actual credential-harvesting page, decoy "unsubscribe" links,
etc. This module turns the *set of links already scored* for an email
into an ordered narrative: which link is the real threat, which look like
redirect hops or lures, and why — instead of making the analyst read N
separate verdicts and reconstruct the story themselves.
"""
from typing import List, Tuple
from urllib.parse import urlparse

from app.services.lists import host_of

_SHORTENER_HINT = "shortener"
_LURE_WORDS = ("unsubscribe", "privacy", "terms", "help", "support", "faq")


def _role_for(url: str, fused: dict, is_worst: bool) -> str:
    reasons_text = " ".join(fused.get("top_reasons", [])).lower()
    path = urlparse(url).path.lower()
    if is_worst and fused["verdict"] in ("phishing", "suspicious"):
        return "payload"
    if _SHORTENER_HINT in reasons_text or "shortened" in reasons_text:
        return "redirector"
    if any(w in path or w in url.lower() for w in _LURE_WORDS):
        return "decoy"
    return "benign-link"


_ROLE_LABEL = {
    "payload": "Likely landing page (credential harvest / malicious action)",
    "redirector": "Redirect hop / link shortener — hides the real destination",
    "decoy": "Legitimate-looking filler link (unsubscribe/help/etc.) used to appear trustworthy",
    "benign-link": "No significant risk signal",
}


def build_storyline(hops: List[Tuple[str, dict]]) -> dict:
    """hops: ordered (url, fused_verdict) pairs, in the order the links
    appeared in the email (subject/body, then HTML hrefs)."""
    if not hops:
        return {"steps": [], "narrative": "No links were found in this message."}

    worst_idx = max(range(len(hops)), key=lambda i: hops[i][1]["confidence"])
    steps = []
    for i, (url, fused) in enumerate(hops):
        role = _role_for(url, fused, i == worst_idx)
        steps.append({
            "step": i + 1,
            "url": url,
            "host": host_of(url),
            "verdict": fused["verdict"],
            "confidence": fused["confidence"],
            "role": role,
            "role_label": _ROLE_LABEL[role],
            "top_reasons": fused.get("top_reasons", [])[:2],
        })

    worst = steps[worst_idx]
    n = len(steps)
    if worst["verdict"] == "safe":
        narrative = (f"This message contains {n} link(s); none scored above the safe threshold. "
                     f"No attack storyline — the content reads as benign.")
    else:
        chain_desc = ""
        redirectors = [s for s in steps if s["role"] == "redirector"]
        decoys = [s for s in steps if s["role"] == "decoy"]
        if redirectors:
            chain_desc += f" {len(redirectors)} link(s) act as redirectors/shorteners that obscure the final destination."
        if decoys:
            chain_desc += f" {len(decoys)} legitimate-looking link(s) (help/unsubscribe-style) are likely included to look trustworthy."
        narrative = (
            f"Of {n} link(s) found, step {worst['step']} ({worst['host'] or worst['url']}) is the likely attack "
            f"payload — verdict '{worst['verdict']}' at {worst['confidence']:.2f} confidence, driven by: "
            f"{'; '.join(worst['top_reasons']) or 'see breakdown'}." + chain_desc
        )
    return {"steps": steps, "narrative": narrative, "payload_step": worst["step"] if worst["verdict"] != "safe" else None}
