# predictor.py
# Loads the trained ML model + preprocessor and exposes a predict() function.
# Handles the case where model files do not exist yet (returns a rule-based fallback).

import os, json, time
from typing import List, Tuple
import joblib
import numpy as np
import pandas as pd

ML_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml")
MODEL_PATH   = os.path.join(ML_DIR, "fraud_model.joblib")
PREP_PATH    = os.path.join(ML_DIR, "preprocessor.joblib")
METRICS_PATH = os.path.join(ML_DIR, "model_metrics.json")

NUMERIC_FEATURES = [
    "amount", "transaction_hour", "transactions_last_hour",
    "is_international", "days_since_last_transaction",
    "avg_amount_last_7d", "amount_to_avg_ratio",
    "is_new_merchant", "weekend_flag"
]
CATEGORIC_FEATURES = ["channel", "merchant_category", "location", "device"]
ALL_FEATURES       = NUMERIC_FEATURES + CATEGORIC_FEATURES

_model        = None
_preprocessor = None


def _load():
    global _model, _preprocessor
    if _model is None and os.path.exists(MODEL_PATH):
        _model        = joblib.load(MODEL_PATH)
        _preprocessor = joblib.load(PREP_PATH)
        print(f"[predictor] Loaded model from {MODEL_PATH}")


def _risk_level(score: float) -> str:
    if score >= 0.78:  return "High"
    if score >= 0.45:  return "Review"
    return "Low"


def _decision(level: str) -> str:
    return {"High": "Blocked", "Review": "Review", "Low": "Approved"}[level]


SIGNAL_MAP = {
    "transactions_last_hour":       "Unusual velocity",
    "amount_to_avg_ratio":          "Amount deviation",
    "is_international":             "International transaction",
    "is_new_merchant":              "New merchant",
    "transaction_hour":             "Off-hours activity",
    "days_since_last_transaction":  "Sudden re-activation",
    "amount":                       "Large amount",
    "location":                     "Location deviation",
    "device":                       "Device mismatch",
}

FRIENDLY_NAMES = {
    "transactions_last_hour":       "Transaction velocity",
    "amount_to_avg_ratio":          "Amount deviation",
    "is_international":             "International flag",
    "is_new_merchant":              "New merchant",
    "transaction_hour":             "Off-hours activity",
    "days_since_last_transaction":  "Inactivity period",
    "amount":                       "Transaction amount",
    "avg_amount_last_7d":           "Historical avg amount",
    "weekend_flag":                 "Weekend transaction",
}


def get_feature_contributions(row_df: pd.DataFrame) -> List[dict]:
    _load()
    if _model is None:
        return []
    try:
        row_t    = _preprocessor.transform(row_df)
        ohe_cols = (_preprocessor.named_transformers_["cat"]
                    .named_steps["ohe"].get_feature_names_out(CATEGORIC_FEATURES).tolist())
        all_cols = NUMERIC_FEATURES + ohe_cols

        importances = getattr(_model, "feature_importances_", None)
        if importances is None or len(importances) != len(all_cols):
            return []

        vals   = row_t[0]
        scores = importances * np.abs(vals)
        idx    = np.argsort(scores)[::-1][:5]
        total  = scores.sum() + 1e-9
        contribs = []
        for i in idx:
            col    = all_cols[i]
            base_c = col.split("_")[0] if "_" in col else col
            fname  = FRIENDLY_NAMES.get(col, FRIENDLY_NAMES.get(base_c, col))
            contribs.append({"feature": fname, "contribution": round(float(scores[i] / total), 4)})
        return contribs
    except Exception as e:
        print(f"[predictor] feature_contributions error: {e}")
        return []


def predict(data: dict) -> Tuple[float, str, str, str, List[dict], str, int]:
    # Returns (risk_score, risk_level, decision, signal, top_features, explanation, ms).
    _load()
    t0  = time.time()
    row = pd.DataFrame([{f: data.get(f, 0) for f in ALL_FEATURES}])

    if _model is not None and _preprocessor is not None:
        row_t     = _preprocessor.transform(row)
        score     = float(_model.predict_proba(row_t)[0, 1])
        top_feats = get_feature_contributions(row)
    else:
        # Rule-based heuristic fallback when model not trained yet
        score = 0.1
        if data.get("transactions_last_hour", 0) >= 5:  score += 0.30
        if data.get("is_international", 0):              score += 0.25
        if data.get("amount_to_avg_ratio", 1) > 5:      score += 0.25
        if data.get("transaction_hour", 12) <= 5:        score += 0.10
        if data.get("is_new_merchant", 0):               score += 0.10
        score     = min(score, 0.99)
        top_feats = []

    ms    = max(1, int((time.time() - t0) * 1000))
    level = _risk_level(score)
    dec   = _decision(level)

    # Top signal
    if top_feats:
        key    = top_feats[0]["feature"].lower().replace(" ", "_")
        signal = SIGNAL_MAP.get(key, top_feats[0]["feature"])
    else:
        signal = ("Unusual velocity"     if data.get("transactions_last_hour", 0) >= 5
                  else "Amount deviation" if data.get("amount_to_avg_ratio", 1) > 5
                  else "Normal behavior")

    # Plain English explanation
    parts = []
    if data.get("transactions_last_hour", 0) >= 5:
        parts.append(f"{data['transactions_last_hour']} transactions in the last hour (high velocity)")
    if data.get("is_international", 0):
        parts.append("the transaction was made internationally")
    if data.get("amount_to_avg_ratio", 1) > 3:
        parts.append(f"amount is {data.get('amount_to_avg_ratio', 1):.1f}x above 7-day average")
    if data.get("transaction_hour", 12) <= 4:
        parts.append(f"made at {data['transaction_hour']}:00 (unusual hour)")
    if not parts:
        parts.append("transaction pattern appears normal across all signals")

    explanation = ("This transaction was flagged because " + "; ".join(parts) + "."
                   if level != "Low"
                   else "This transaction appears normal. " + parts[0].capitalize() + ".")

    return score, level, dec, signal, top_feats, explanation, ms


def load_metrics() -> dict:
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH) as f:
            return json.load(f)
    return {
        "best_model": "Not trained yet - run: python ml/train.py",
        "precision": 0, "recall": 0, "f1": 0,
        "roc_auc": 0, "pr_auc": 0,
        "confusion_matrix": [[0, 0], [0, 0]],
        "top_features": [],
        "models_compared": [],
    }
