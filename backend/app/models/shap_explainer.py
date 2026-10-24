"""
PhishSentinel AI — SHAP Explainability Layer
-------------------------------------------------
Previously, `fusion_engine.py` only surfaced the rule-engine's canned
reason strings ("Domain closely resembles trusted brand..."), which is
honest but isn't actually SHAP — despite SHAP being named as the
explainability method in the project report and tech stack.

This module wires a *real* `shap.TreeExplainer` (or `LinearExplainer`,
depending on what `train_url_model.py` produces) against the trained URL
model, and turns per-feature SHAP values into the same plain-language
reason format the rest of the system already expects. It is used
automatically once you've trained a model (`training/train_url_model.py`)
and installed `shap` — until then, `url_analyzer`'s heuristic reasons are
used exactly as before, so nothing breaks if you skip this step.

Cost: SHAP is pure-Python/NumPy on top of a tiny tabular model here (12
features), so a single explanation takes low milliseconds on a laptop —
no GPU, no extra hosting cost, fits the ₹0 software budget.
"""
import logging
from typing import List, Optional

from app.config import SHAP_ENABLED

logger = logging.getLogger("phishsentinel.shap")

try:
    import shap
    import numpy as np
except ImportError:
    shap = None
    np = None

# Human-readable labels for each URL feature, in the exact order
# url_analyzer.URLAnalyzer._vectorize() emits them.
FEATURE_LABELS = [
    "overall URL length",
    "number of dots in the domain",
    "number of hyphens in the domain",
    "digit characters in the domain",
    "number of subdomains",
    "raw IP address used as host",
    "'@' symbol in the URL",
    "HTTPS encryption present",
    "high-risk top-level domain",
    "URL shortener used",
    "credential-harvesting keywords",
    "similarity to a known trusted brand",
]

# Features where a HIGHER raw value is safer (so a positive SHAP value
# toward "phishing" from a LOW value should read as "lacks X", not "has X").
_INVERTED = {"HTTPS encryption present"}


class ShapExplainer:
    def __init__(self):
        self.explainer = None
        self.model_kind = None  # "tree" | "linear" | None

    def attach(self, model, background_data=None):
        """Call once a trained model is loaded. Picks the cheapest
        compatible SHAP explainer for the model type."""
        if shap is None or model is None:
            return
        try:
            model_type = type(model).__name__.lower()
            if any(k in model_type for k in ("xgb", "forest", "tree", "gradientboosting")):
                self.explainer = shap.TreeExplainer(model)
                self.model_kind = "tree"
            elif "logisticregression" in model_type or "linear" in model_type:
                if background_data is not None:
                    self.explainer = shap.LinearExplainer(model, background_data)
                    self.model_kind = "linear"
            logger.info(f"SHAP explainer attached ({self.model_kind}) for {model_type}")
        except Exception as e:
            logger.warning(f"Could not attach SHAP explainer: {e}")
            self.explainer = None

    def explain(self, feature_vector: List[float], top_k: int = 3) -> Optional[List[str]]:
        """Returns up to `top_k` plain-language reasons ranked by |SHAP
        value|, or None if SHAP isn't available (caller should fall back
        to the heuristic reasons)."""
        if not SHAP_ENABLED or self.explainer is None or np is None:
            return None
        try:
            x = np.array([feature_vector])
            shap_values = self.explainer.shap_values(x)
            values = shap_values[1][0] if isinstance(shap_values, list) else shap_values[0]

            ranked = sorted(
                zip(FEATURE_LABELS, values, feature_vector),
                key=lambda t: abs(t[1]),
                reverse=True,
            )
            reasons = []
            for label, shap_val, raw_val in ranked[:top_k]:
                if abs(shap_val) < 1e-3:
                    continue
                pushes_toward = "phishing" if shap_val > 0 else "safe"
                if label in _INVERTED:
                    pushes_toward = "safe" if shap_val > 0 else "phishing"
                reasons.append(
                    f"SHAP: {label} pushed the verdict toward '{pushes_toward}' "
                    f"(impact {abs(shap_val):.2f})"
                )
            return reasons or None
        except Exception as e:
            logger.warning(f"SHAP explanation failed, falling back to heuristic reasons: {e}")
            return None


shap_explainer = ShapExplainer()
