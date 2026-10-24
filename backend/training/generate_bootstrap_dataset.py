"""
PhishSentinel AI — Bootstrap URL Dataset Generator
--------------------------------------------------------
IMPORTANT — read this before you cite results from this dataset anywhere
in your report: this script generates a SYNTHETIC, rule-based dataset. It
exists so `train_url_model.py` has something to run against on a machine
with no internet access, and so you can prove the training pipeline
itself works end-to-end before you have real data.

It is NOT a substitute for real phishing data, and a model trained only
on this will look artificially good (it will have learned the exact
rules used to generate it, not the messiness of real phishing). Before
your final submission, replace this with real data:

  - PhishTank:  https://phishtank.org/developer_info.php  (free CSV/JSON feed)
  - OpenPhish:  https://openphish.com/                     (free tier feed)
  - Kaggle:     search "phishing url dataset" — several free, labeled sets
  - Legitimate URLs: Tranco top-1M (https://tranco-list.eu/) or Alexa's
    old top-1M archives, for the "safe" class

Usage:
    python training/generate_bootstrap_dataset.py --n 4000 --out training/data/urls.csv

This produces a roughly class-balanced CSV with a `url` and `label`
column (label: 1 = phishing, 0 = legitimate), exactly the format
`train_url_model.py --data training/data/urls.csv` expects.
"""
import argparse
import csv
import os
import random

LEGIT_BRANDS = [
    "google", "paypal", "amazon", "microsoft", "apple", "facebook",
    "netflix", "instagram", "linkedin", "github", "dropbox", "adobe",
    "icicibank", "hdfcbank", "sbi", "axisbank", "flipkart", "myntra",
    "irctc", "zomato", "swiggy", "paytm", "phonepe",
]
LEGIT_TLDS = ["com", "in", "co.in", "org", "net", "io"]
LEGIT_PATHS = ["", "/", "/login", "/account", "/products", "/help", "/about", "/search?q=order"]

SUSPICIOUS_TLDS = ["tk", "ml", "ga", "cf", "gq", "xyz", "top", "click", "info"]
CRED_KEYWORDS = ["login", "verify", "secure", "account", "update", "confirm", "signin", "password", "billing"]
URGENCY_WORDS = ["urgent", "alert", "suspended", "limited", "action-required", "important"]
SHORTENERS = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly"]


def random_legit_url(rng: random.Random) -> str:
    brand = rng.choice(LEGIT_BRANDS)
    tld = rng.choice(LEGIT_TLDS)
    sub = rng.choice(["", "www.", "mail.", "accounts."])
    path = rng.choice(LEGIT_PATHS)
    scheme = "https"
    return f"{scheme}://{sub}{brand}.{tld}{path}"


def _typo(brand: str, rng: random.Random) -> str:
    """Cheap typosquat generator: char substitution, hyphen insertion, or
    extra word — mirrors the patterns url_analyzer.py is designed to catch."""
    style = rng.choice(["substitute", "hyphen-suffix", "hyphen-prefix", "double-letter", "digit-swap"])
    if style == "substitute" and len(brand) > 3:
        idx = rng.randrange(1, len(brand) - 1)
        subs = {"o": "0", "l": "1", "i": "1", "e": "3", "a": "4", "s": "5"}
        ch = brand[idx]
        new_ch = subs.get(ch, ch + ch)
        return brand[:idx] + new_ch + brand[idx + 1:]
    if style == "hyphen-suffix":
        return f"{brand}-{rng.choice(CRED_KEYWORDS)}"
    if style == "hyphen-prefix":
        return f"{rng.choice(['secure', 'my', 'the', 'online'])}-{brand}"
    if style == "double-letter" and brand:
        idx = rng.randrange(len(brand))
        return brand[:idx] + brand[idx] + brand[idx:]
    if style == "digit-swap":
        return brand.replace("o", "0").replace("i", "1") or brand
    return brand + "1"


def random_phishing_url(rng: random.Random) -> str:
    brand = rng.choice(LEGIT_BRANDS)
    fake_name = _typo(brand, rng)
    tld = rng.choice(SUSPICIOUS_TLDS + LEGIT_TLDS)  # sometimes a real TLD, still phishing
    scheme = rng.choice(["http", "http", "https"])  # phishing sites skip HTTPS more often
    keyword_count = rng.randint(1, 3)
    keywords = "-".join(rng.sample(CRED_KEYWORDS, k=min(keyword_count, len(CRED_KEYWORDS))))
    path_style = rng.choice(["keyword-path", "urgency-subdomain", "shortener", "ip-host"])

    if path_style == "shortener":
        return f"{scheme}://{rng.choice(SHORTENERS)}/{rng.randint(100000,999999):x}"
    if path_style == "ip-host":
        ip = ".".join(str(rng.randint(1, 254)) for _ in range(4))
        return f"{scheme}://{ip}/{fake_name}/{keywords}"
    if path_style == "urgency-subdomain":
        urgency = rng.choice(URGENCY_WORDS)
        return f"{scheme}://{urgency}.{fake_name}.{tld}/{keywords}"
    # keyword-path (most common real-world pattern)
    return f"{scheme}://{fake_name}.{tld}/{keywords}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=4000, help="total rows to generate")
    parser.add_argument("--out", default="training/data/urls.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    n_legit = args.n // 2
    n_phish = args.n - n_legit

    rows = set()
    while len([r for r in rows if r[1] == 0]) < n_legit:
        rows.add((random_legit_url(rng), 0))
    while len([r for r in rows if r[1] == 1]) < n_phish:
        rows.add((random_phishing_url(rng), 1))

    rows = list(rows)
    rng.shuffle(rows)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "label"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows ({n_legit} legit, {n_phish} phishing) to {args.out}")
    print("Reminder: this is a SYNTHETIC bootstrap dataset — swap in real")
    print("PhishTank/OpenPhish/Kaggle data before citing accuracy numbers")
    print("in your report. See the docstring at the top of this file.")


if __name__ == "__main__":
    main()
