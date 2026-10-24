"""
PhishSentinel AI — Trusted brand registry
---------------------------------------------
Single source of truth for brands the detectors protect. Used by the URL
typosquat check and by email-header display-name spoofing detection.
Add the brands your users actually deal with (banks, payment apps,
campus/company portals) — it is the cheapest way to raise real-world
accuracy.
"""

TRUSTED_BRAND_DOMAINS = [
    "google.com", "microsoft.com", "apple.com", "amazon.com", "paypal.com",
    "facebook.com", "instagram.com", "netflix.com", "sbi.co.in", "hdfcbank.com",
    "icicibank.com", "irctc.co.in", "onlinesbi.com", "github.com", "linkedin.com",
]

# Second-level public suffixes we need to treat as a single "TLD" when
# working out the registrable domain (a deliberately small list; swap in
# the `tldextract` package for full public-suffix-list accuracy).
MULTI_PART_TLDS = {
    "co.in", "co.uk", "org.uk", "ac.uk", "com.au", "co.nz", "co.jp", "com.br",
    "com.cn", "co.za", "com.sg", "com.mx", "net.in", "org.in", "gov.in", "ac.in",
}


def registrable_domain(host: str) -> str:
    """'mail.accounts.paypal.com' -> 'paypal.com'; 'x.sbi.co.in' -> 'sbi.co.in'."""
    host = (host or "").lower().strip(".")
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in MULTI_PART_TLDS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def brand_name(domain: str) -> str:
    """'paypal.com' -> 'paypal'; 'sbi.co.in' -> 'sbi'."""
    return domain.split(".")[0]
