"""
PhishSentinel AI — URL extraction from free text
----------------------------------------------------
Emails rarely arrive with a tidy "primary URL" field. Pull every link out
of the body so the URL detector can score all of them and the worst one
drives the verdict.
"""
import re
from typing import List

_URL_RE = re.compile(r"""(?:https?://|www\.)[^\s<>"'`\]\[(){}|\\^]+""", re.IGNORECASE)
_TRAILING = ".,;:!?"


def extract_urls(text: str, limit: int = 10) -> List[str]:
    """Returns up to `limit` unique URLs in order of appearance."""
    if not text:
        return []
    seen = set()
    urls: List[str] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_TRAILING)
        if url.lower().startswith("www."):
            url = "http://" + url
        key = url.lower()
        if key in seen or len(url) > 2048:
            continue
        seen.add(key)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls
