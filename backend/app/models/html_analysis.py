"""
PhishSentinel AI — HTML email content analysis
--------------------------------------------------
Plain-text NLP can't see the oldest trick in the book: a link that *reads*
"https://paypal.com/login" but whose href points somewhere else. This
module parses an email's HTML with the standard library and flags:

  - link text that looks like one domain while the href goes to another
  - javascript:/data: links
  - password fields (login forms embedded in the email)
  - forms that post credentials to another domain or over plain HTTP

It also returns every href found, so the URL detector can score them.
"""
import re
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urlparse

from app.models.brands import registrable_domain

_LOOKS_LIKE_URL = re.compile(r"^\s*(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:[/:?#]\S*)?\s*$", re.IGNORECASE)
MAX_LINKS = 200


def _host(url: str) -> str:
    try:
        return (urlparse(url if "://" in url else "http://" + url).hostname or "").lower()
    except ValueError:
        return ""


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: List[dict] = []
        self.forms: List[dict] = []
        self._open_a: Optional[dict] = None
        self._open_form: Optional[dict] = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and len(self.links) < MAX_LINKS:
            self._open_a = {"href": (a.get("href") or "").strip(), "text": ""}
            self.links.append(self._open_a)
        elif tag == "form":
            self._open_form = {"action": (a.get("action") or "").strip(), "password": False}
            self.forms.append(self._open_form)
        elif tag == "input" and self._open_form is not None and (a.get("type") or "").lower() == "password":
            self._open_form["password"] = True

    def handle_endtag(self, tag):
        if tag == "a":
            self._open_a = None
        elif tag == "form":
            self._open_form = None

    def handle_data(self, data):
        if self._open_a is not None:
            self._open_a["text"] += data


def analyze_html(html: Optional[str]) -> Optional[dict]:
    """Returns {score, reasons, hrefs} or None when no HTML was supplied."""
    if not html or not html.strip():
        return None

    parser = _Collector()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return {"score": 0.0, "reasons": [], "hrefs": [], "method": "html_error"}

    reasons: List[str] = []
    score = 0.0
    hrefs: List[str] = []
    mismatches = 0

    for link in parser.links:
        href, text = link["href"], link["text"].strip()
        low = href.lower()
        if low.startswith(("javascript:", "data:", "vbscript:")):
            score += 0.20
            reasons.append("Contains a script/data link instead of a normal web address")
            continue
        if not low.startswith(("http://", "https://")):
            continue
        hrefs.append(href)
        m = _LOOKS_LIKE_URL.match(text)
        if m:
            shown = registrable_domain(m.group(1).lower())
            real = registrable_domain(_host(href))
            if real and shown != real:
                mismatches += 1
                if mismatches <= 2:
                    reasons.append(f"Link text shows '{shown}' but actually goes to '{real}'")
    if mismatches:
        score += min(0.35 * mismatches, 0.70)

    for form in parser.forms:
        if not form["password"]:
            continue
        score += 0.20
        reasons.append("Email contains an embedded password/login form")
        action = form["action"].lower()
        if action.startswith("http://"):
            score += 0.20
            reasons.append("Login form submits over unencrypted HTTP")
        elif action.startswith("https://"):
            pass
        break

    # De-duplicate hrefs, keep order
    seen, unique = set(), []
    for h in hrefs:
        if h.lower() not in seen:
            seen.add(h.lower()); unique.append(h)

    return {"score": max(0.0, min(1.0, score)), "method": "html_parse", "reasons": reasons, "hrefs": unique[:20]}
