# train.py
# Full ML training pipeline for AI-Based Fraud Detection.
#
# Steps:
#   1. Generate (or load) dataset
#   2. Feature engineering + preprocessing
#   3. Train/test split (stratified)
#   4. Handle class imbalance with SMOTE
#   5. Train 4 models: LogisticRegression, RandomForest, XGBoost, IsolationForest
#   6. Evaluate: Precision, Recall, F1, ROC-AUC, PR-AUC
#   7. Pick best by PR-AUC
#   8. Compute feature importances
#   9. Save model + preprocessor + metrics
#
# Run: python ml/train.py
# Outputs:
#   ml/fraud_model.joblib
#   ml/preprocessor.joblib
#   ml/model_metrics.json

import os, sys, json, warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model    import LogisticRegression
from sklearn.ensemble        import RandomForestClassifier, IsolationForest
from sklearn.preprocessing   import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics         import (precision_score, recall_score, f1_score,
                                     roc_auc_score, average_precision_score,
                                     confusion_matrix)
from sklearn.pipeline        import Pipeline
from sklearn.compose         import ColumnTransformer
from imblearn.over_sampling  import SMOTE
from xgboost                 import XGBClassifier

warnings.filterwarnings("ignore")

ML_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(ML_DIR, "fraud_dataset.csv")

NUMERIC_FEATURES   = [
    "amount", "transaction_hour", "transactions_last_hour",
    "is_international", "days_since_last_transaction",
    "avg_amount_last_7d", "amount_to_avg_ratio",
    "is_new_merchant", "weekend_flag"
]
CATEGORIC_FEATURES = ["channel", "merchant_category", "location", "device"]
ALL_FEATURES       = NUMERIC_FEATURES + CATEGORIC_FEATURES
TARGET             = "label"


def load_data():
    if not os.path.exists(DATA_CSV):
        print("Dataset not found. Running generate_data.py first...")
        sys.path.insert(0, ML_DIR)
        import generate_data
        generate_data.main()
    df = pd.read_csv(DATA_CSV)
    print(f"Loaded {len(df):,} rows | Fraud rate: {df[TARGET].mean() * 100:.2f}%")
    return df


def build_preprocessor():
    num_pipe = Pipeline([("scaler", StandardScaler())])
    cat_pipe = Pipeline([("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    pre = ColumnTransformer([
        ("num", num_pipe, NUMERIC_FEATURES),
        ("cat", cat_pipe, CATEGORIC_FEATURES),
    ])
    return pre


def evaluate(model, X_test, y_test, name):
    if name == "IsolationForest":
        preds_raw = model.predict(X_test)
        y_pred    = np.where(preds_raw == -1, 1, 0)
        y_prob    = -model.score_samples(X_test)
        y_prob    = (y_prob - y_prob.min()) / (y_prob.max() - y_prob.min() + 1e-9)
    else:
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

    prec  = precision_score(y_test, y_pred, zero_division=0)
    rec   = recall_score(y_test, y_pred,    zero_division=0)
    f1    = f1_score(y_test, y_pred,         zero_division=0)
    roc   = roc_auc_score(y_test, y_prob)
    prauc = average_precision_score(y_test, y_prob)
    cm    = confusion_matrix(y_test, y_pred).tolist()
    print(f"  {name:<22}  Prec={prec:.3f}  Rec={rec:.3f}  F1={f1:.3f}  "
          f"ROC={roc:.3f}  PR-AUC={prauc:.3f}")
    return {"name": name, "precision": prec, "recall": rec, "f1": f1,
            "roc_auc": roc, "pr_auc": prauc, "confusion_matrix": cm}


def get_feature_importance(model, preprocessor, n=10):
    try:
        ohe_cols = (preprocessor.named_transformers_["cat"]
                    .named_steps["ohe"].get_feature_names_out(CATEGORIC_FEATURES).tolist())
        all_cols    = NUMERIC_FEATURES + ohe_cols
        importances = getattr(model, "feature_importances_", None)
        if importances is None or len(importances) != len(all_cols):
            return []
        idx = np.argsort(importances)[::-1][:n]
        return [{"feature": all_cols[i], "importance": round(float(importances[i]), 6)} for i in idx]
    except Exception as e:
        print(f"[train] feature importance error: {e}")
        return []


def main():
    df = load_data()
    X  = df[ALL_FEATURES]
    y  = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42)

    print(f"\nTrain: {len(X_train):,} | Test: {len(X_test):,}")
    print(f"Train fraud: {y_train.sum():,} ({y_train.mean() * 100:.2f}%)")

    preprocessor = build_preprocessor()
    X_train_t    = preprocessor.fit_transform(X_train)
    X_test_t     = preprocessor.transform(X_test)

    smote            = SMOTE(random_state=42, sampling_strategy=0.3)
    X_train_sm, y_sm = smote.fit_resample(X_train_t, y_train)
    print(f"After SMOTE: {len(X_train_sm):,} rows | Fraud: {y_sm.sum():,} ({y_sm.mean() * 100:.2f}%)\n")

    models = {
        "Logistic Regression": LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=42, C=0.1),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, class_weight="balanced",
            random_state=42, n_jobs=-1),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            scale_pos_weight=int((y_sm == 0).sum() / max((y_sm == 1).sum(), 1)),
            eval_metric="aucpr", random_state=42,
            verbosity=0),
        "IsolationForest": IsolationForest(
            n_estimators=200, contamination=0.015, random_state=42),
    }

    results = []
    trained = {}
    print("Training models...")
    for name, clf in models.items():
        print(f"\n  Training: {name}")
        if name == "IsolationForest":
            clf.fit(X_train_t)
        else:
            clf.fit(X_train_sm, y_sm)
        trained[name] = clf
        metrics = evaluate(clf, X_test_t, y_test, name)
        results.append(metrics)

    # Pick best supervised model by PR-AUC
    supervised = [r for r in results if r["name"] != "IsolationForest"]
    best_meta  = max(supervised, key=lambda r: r["pr_auc"])
    best_name  = best_meta["name"]
    best_model = trained[best_name]
    print(f"\nBest model: {best_name} (PR-AUC={best_meta['pr_auc']:.4f})")

    fi = get_feature_importance(best_model, preprocessor)

    joblib.dump(best_model,   os.path.join(ML_DIR, "fraud_model.joblib"))
    joblib.dump(preprocessor, os.path.join(ML_DIR, "preprocessor.joblib"))
    print("Saved fraud_model.joblib and preprocessor.joblib")

    metrics_out = {
        "best_model":       best_name,
        "precision":        round(best_meta["precision"], 4),
        "recall":           round(best_meta["recall"],    4),
        "f1":               round(best_meta["f1"],        4),
        "roc_auc":          round(best_meta["roc_auc"],   4),
        "pr_auc":           round(best_meta["pr_auc"],    4),
        "confusion_matrix": best_meta["confusion_matrix"],
        "top_features":     fi,
        "models_compared":  [
            {"name": r["name"], "f1": round(r["f1"], 4),
             "pr_auc": round(r["pr_auc"], 4), "roc_auc": round(r["roc_auc"], 4)}
            for r in results
        ],
    }
    with open(os.path.join(ML_DIR, "model_metrics.json"), "w") as f:
        json.dump(metrics_out, f, indent=2)
    print("Saved model_metrics.json\n")
    print(json.dumps(metrics_out, indent=2))


if __name__ == "__main__":
    main()
