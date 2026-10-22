# main.py
# FastAPI application -- AI-Based Fraud Detection Backend
# Port: 8000  |  Docs: http://localhost:8000/docs
#
# Endpoints:
#   POST   /api/predict             Single transaction prediction
#   POST   /api/predict/batch       CSV batch prediction
#   GET    /api/transactions         Filtered transaction list
#   GET    /api/stats                Dashboard summary
#   GET    /api/model/metrics        ML model performance
#   POST   /api/agent/chat           AI Fraud Analyst agent
#   GET    /api/alerts               High-risk unresolved alerts

import os, io, json, time, random, string
from datetime import datetime
from typing import Optional, List

import pandas as pd
from fastapi import FastAPI, Depends, File, UploadFile, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load .env before any other imports that read env vars
load_dotenv()

import database, crud, schemas, predictor, agent as fraud_agent
from database import get_db, create_tables

app = FastAPI(
    title="SecureBank Fraud Detection API",
    description="AI-powered fraud detection backend for SecureBank dashboard.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS -- allows the frontend file:// origin + localhost
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
origins = [o.strip() for o in CORS_ORIGINS.split(",")] if CORS_ORIGINS != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_tables()
    print("Database tables ready.")


def _make_txn_id() -> str:
    return "TXN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def _amount_display(amount: float) -> str:
    return "Rs " + "{:,.0f}".format(amount)


def _save_prediction(db: Session, req_data: dict, txn_id: str,
                     score: float, level: str, dec: str,
                     signal: str, top_feats: list) -> None:
    crud.create_transaction(db, {
        "transaction_id":               txn_id,
        "channel":                      req_data.get("channel", "Card"),
        "amount":                       req_data.get("amount", 0),
        "merchant_category":            req_data.get("merchant_category", "Other"),
        "location":                     req_data.get("location", "Unknown"),
        "device":                       req_data.get("device", "mobile"),
        "transaction_hour":             req_data.get("transaction_hour", 12),
        "transactions_last_hour":       req_data.get("transactions_last_hour", 1),
        "is_international":             bool(req_data.get("is_international", 0)),
        "days_since_last_transaction":  req_data.get("days_since_last_transaction", 1),
        "avg_amount_last_7d":           req_data.get("avg_amount_last_7d", 5000),
        "amount_to_avg_ratio":          req_data.get("amount_to_avg_ratio", 1.0),
        "is_new_merchant":              bool(req_data.get("is_new_merchant", 0)),
        "weekend_flag":                 bool(req_data.get("weekend_flag", 0)),
        "risk_score":                   score,
        "risk_level":                   level,
        "decision":                     dec,
        "signal":                       signal,
        "top_features":                 json.dumps(top_feats),
        "is_fraud":                     level == "High",
        "timestamp":                    datetime.utcnow(),
    })


# ROUTES

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "SecureBank Fraud Detection API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/predict", response_model=schemas.PredictResponse, tags=["Predictions"])
def predict_single(req: schemas.PredictRequest, db: Session = Depends(get_db)):
    """
    Score a single transaction for fraud probability.

    Returns risk_score (0-1), risk_level (Low/Review/High),
    decision (Approved/Review/Blocked), and top contributing features.

    Sample curl:

        curl -X POST http://localhost:8000/api/predict
          -H "Content-Type: application/json"
          -d '{"amount":84500,"channel":"Card","transaction_hour":2,"transactions_last_hour":8}'
    """
    data  = req.model_dump()
    score, level, dec, signal, top_feats, explanation, ms = predictor.predict(data)
    txn_id = _make_txn_id()
    _save_prediction(db, data, txn_id, score, level, dec, signal, top_feats)

    return schemas.PredictResponse(
        transaction_id=txn_id,
        channel=req.channel,
        amount=req.amount,
        amount_display=_amount_display(req.amount),
        risk_score=round(score, 4),
        risk_level=level,
        decision=dec,
        signal=signal,
        top_features=[schemas.FeatureContribution(**f) for f in top_feats],
        explanation=explanation,
        processing_ms=ms,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post("/api/predict/batch", tags=["Predictions"])
async def predict_batch(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a CSV file with transaction rows; returns predictions for all rows.
    CSV must have at least an 'amount' column. Extra columns are ignored.

    Sample curl:

        curl -X POST http://localhost:8000/api/predict/batch -F "file=@transactions.csv"
    """
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if "amount" not in df.columns:
        raise HTTPException(status_code=422, detail="CSV must have an 'amount' column")

    defaults = {
        "channel": "Card", "merchant_category": "Other", "location": "Mumbai",
        "device": "mobile", "transaction_hour": 12, "transactions_last_hour": 1,
        "is_international": 0, "days_since_last_transaction": 1,
        "avg_amount_last_7d": 5000.0, "amount_to_avg_ratio": 1.0,
        "is_new_merchant": 0, "weekend_flag": 0,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    results = []
    counts  = {"Low": 0, "Review": 0, "High": 0}
    for _, row in df.iterrows():
        data   = row.to_dict()
        score, level, dec, signal, top_feats, explanation, ms = predictor.predict(data)
        txn_id = _make_txn_id()
        _save_prediction(db, data, txn_id, score, level, dec, signal, top_feats)
        counts[level] += 1
        results.append({
            "transaction_id": txn_id,
            "amount":         data.get("amount"),
            "amount_display": _amount_display(float(data.get("amount", 0))),
            "risk_score":     round(score, 4),
            "risk_level":     level,
            "decision":       dec,
            "signal":         signal,
        })

    return {"total": len(results), "summary": counts, "predictions": results}


@app.get("/api/transactions", tags=["Transactions"])
def list_transactions(
    risk_level: Optional[str]   = Query(None,  description="Low | Review | High | all"),
    date_from:  Optional[str]   = Query(None,  description="ISO date string"),
    date_to:    Optional[str]   = Query(None,  description="ISO date string"),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    limit:      int             = Query(50,    ge=1, le=500),
    offset:     int             = Query(0,     ge=0),
    db: Session = Depends(get_db)
):
    """
    List transactions with optional filters.

    Sample curl:

        curl "http://localhost:8000/api/transactions?risk_level=High&limit=10"
    """
    txns = crud.get_transactions(db, risk_level=risk_level, date_from=date_from,
                                 date_to=date_to, min_amount=min_amount,
                                 max_amount=max_amount, limit=limit, offset=offset)
    return [schemas.TransactionOut(
        transaction_id=t.transaction_id,
        channel=t.channel,
        amount=t.amount,
        amount_display=_amount_display(t.amount),
        risk_score=round(t.risk_score, 4),
        risk_level=t.risk_level,
        decision=t.decision,
        signal=t.signal,
        is_fraud=bool(t.is_fraud),
        timestamp=t.timestamp.isoformat() if t.timestamp else "",
    ) for t in txns]


@app.get("/api/stats", response_model=schemas.StatsResponse, tags=["Dashboard"])
def get_stats(db: Session = Depends(get_db)):
    """
    Return dashboard summary numbers and chart data.

    Sample curl:

        curl http://localhost:8000/api/stats
    """
    s = crud.get_stats(db)
    return schemas.StatsResponse(
        total_transactions=s["total_transactions"],
        high_risk_alerts=s["high_risk_alerts"],
        fraud_rate_pct=s["fraud_rate_pct"],
        amount_saved=s["amount_saved"],
        detection_precision=s["detection_precision"],
        avg_scoring_ms=s["avg_scoring_ms"],
        risk_distribution=s["risk_distribution"],
        chart_data=schemas.ChartData(**s["chart_data"]),
    )


@app.get("/api/model/metrics", response_model=schemas.ModelMetricsResponse, tags=["ML Model"])
def model_metrics():
    """
    Return saved model performance metrics from model_metrics.json.

    Sample curl:

        curl http://localhost:8000/api/model/metrics
    """
    m = predictor.load_metrics()
    return schemas.ModelMetricsResponse(
        best_model=m.get("best_model", "N/A"),
        precision=m.get("precision", 0),
        recall=m.get("recall", 0),
        f1=m.get("f1", 0),
        roc_auc=m.get("roc_auc", 0),
        pr_auc=m.get("pr_auc", 0),
        confusion_matrix=m.get("confusion_matrix", [[0, 0], [0, 0]]),
        top_features=m.get("top_features", []),
        models_compared=[schemas.ModelComparison(**mc) for mc in m.get("models_compared", [])],
    )


@app.post("/api/agent/chat", response_model=schemas.AgentChatResponse, tags=["AI Agent"])
def agent_chat(req: schemas.AgentChatRequest, db: Session = Depends(get_db)):
    """
    Chat with the Gemini-powered Fraud Analyst Assistant.

    Sample curl:

        curl -X POST http://localhost:8000/api/agent/chat
          -H "Content-Type: application/json"
          -d '{"session_id":"demo1","message":"Why was the last transaction flagged?"}'
    """
    history_rows = crud.get_chat_history(db, req.session_id)
    history = [{"role": h.role, "message": h.message} for h in history_rows]
    crud.append_chat(db, req.session_id, "user", req.message)
    result = fraud_agent.run_agent(
        session_id=req.session_id,
        user_message=req.message,
        history=history,
        db_session=db
    )
    crud.append_chat(db, req.session_id, "model", result["reply"])
    return schemas.AgentChatResponse(
        session_id=req.session_id,
        reply=result["reply"],
        action_suggestion=result.get("action_suggestion"),
        reasoning=result.get("reasoning"),
        sources=result.get("sources", []),
    )


@app.get("/api/alerts", tags=["Alerts"])
def get_alerts(
    resolved: bool = Query(False, description="True to see resolved alerts"),
    limit:    int  = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Return unresolved high-risk transaction alerts.

    Sample curl:

        curl "http://localhost:8000/api/alerts?resolved=false&limit=20"
    """
    alerts = crud.get_alerts(db, resolved=resolved, limit=limit)
    return [schemas.AlertOut(
        id=a.id,
        transaction_id=a.transaction_id,
        risk_score=round(a.risk_score, 4),
        risk_level=a.risk_level,
        amount=a.amount,
        channel=a.channel,
        signal=a.signal,
        resolved=bool(a.resolved),
        created_at=a.created_at.isoformat() if a.created_at else "",
    ) for a in alerts]
