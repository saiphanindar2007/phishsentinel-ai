"""
PhishSentinel AI — NLP Content Classifier
--------------------------------------------
Flags social-engineering language: urgency, credential requests, threats,
reward baiting, etc.

Design note (same pattern as url_analyzer.py):
`heuristic_score()` runs with ZERO setup, so the API works immediately.
Run `training/train_nlp_model.py` on a labelled phishing-email/SMS dataset
to fine-tune a DistilBERT classifier; if a model is found at
`NLP_MODEL_DIR`, it is loaded automatically and takes over — same
`analyze()` signature, no other code changes needed.
"""
import os
import re
from typing import List

from app.config import NLP_MODEL_DIR

URGENCY_PHRASES = [
    "act now", "immediately", "urgent", "within 24 hours", "account will be suspended",
    "verify your account", "limited time", "final notice", "action required",
    "your account has been locked", "unusual activity", "expire", "act fast",
]

CREDENTIAL_REQUEST_PHRASES = [
    "confirm your password", "enter your password", "update your billing",
    "click the link below", "verify your identity", "ssn", "social security number",
    "card number", "cvv", "one time password", "otp", "login credentials", "pin number",
]

REWARD_BAIT_PHRASES = [
    "you have won", "claim your prize", "free gift", "congratulations", "lucky winner",
    "cash reward", "you've been selected",
]

THREAT_PHRASES = [
    "legal action", "your account will be closed", "suspended permanently",
    "unauthorized access detected", "payment failed",
]

GENERIC_GREETING_PATTERNS = [r"\bdear (customer|user|valued member|sir/madam)\b"]


def _count_hits(text: str, phrases: List[str]) -> int:
    return sum(1 for p in phrases if p in text)


def heuristic_score(text: str) -> dict:
    t = text.lower()
    urgency_hits = _count_hits(t, URGENCY_PHRASES)
    cred_hits = _count_hits(t, CREDENTIAL_REQUEST_PHRASES)
    reward_hits = _count_hits(t, REWARD_BAIT_PHRASES)
    threat_hits = _count_hits(t, THREAT_PHRASES)
    generic_greeting = any(re.search(p, t) for p in GENERIC_GREETING_PATTERNS)
    exclamations = t.count("!")
    all_caps_words = sum(1 for w in text.split() if len(w) > 3 and w.isupper())

    score = 0.0
    score += min(urgency_hits * 0.15, 0.35)
    score += min(cred_hits * 0.18, 0.4)
    score += min(reward_hits * 0.12, 0.25)
    score += min(threat_hits * 0.15, 0.3)
    score += 0.08 if generic_greeting else 0.0
    score += min(exclamations * 0.02, 0.08)
    score += min(all_caps_words * 0.02, 0.06)
    score = max(0.0, min(1.0, score))

    reasons = []
    if urgency_hits:
        reasons.append(f"Urgency language detected ({urgency_hits} phrase(s))")
    if cred_hits:
        reasons.append(f"Requests credentials or sensitive data ({cred_hits} phrase(s))")
    if reward_hits:
        reasons.append("Uses reward/prize bait language")
    if threat_hits:
        reasons.append("Uses threatening consequence language")
    if generic_greeting:
        reasons.append("Generic greeting instead of a personalised name")

    return {"score": score, "reasons": reasons}


class NLPClassifier:
    def __init__(self, model_dir: str = NLP_MODEL_DIR):
        self.pipeline = None
        if os.path.isdir(model_dir) and os.listdir(model_dir):
            try:
                # Imported lazily: transformers/torch are heavy, and most
                # people will run the heuristic path until they've trained
                # a model, so we avoid paying the import cost until needed.
                from transformers import pipeline
                self.pipeline = pipeline(
                    "text-classification", model=model_dir, tokenizer=model_dir, top_k=None
                )
            except Exception:
                self.pipeline = None

    def analyze(self, text: str) -> dict:
        if self.pipeline is not None:
            try:
                result = self.pipeline(text[:512])
                # Expect labels like "PHISHING"/"LEGITIMATE" from training script
                phishing_entries = [r for r in result[0] if r["label"].upper().startswith("PHISH")]
                score = float(phishing_entries[0]["score"]) if phishing_entries else 0.0
                return {"score": score, "method": "trained_model", "reasons": ["Model-based classification (see confidence)"]}
            except Exception:
                pass  # fall through to heuristic on any inference error

        result = heuristic_score(text)
        result["method"] = "heuristic"
        return result


nlp_classifier = NLPClassifier()
