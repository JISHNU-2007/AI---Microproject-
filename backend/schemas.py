# schemas.py - Pydantic v2 request/response models.
# Field names deliberately match the frontend table and chart data shapes.

from __future__ import annotations
from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Predict

class PredictRequest(BaseModel):
    # Single-transaction prediction request.
    amount:                      float = Field(..., gt=0, example=84500)
    channel:                     str   = Field(..., example="Card")
    merchant_category:           str   = Field(default="Other", example="Electronics")
    location:                    str   = Field(default="Mumbai", example="Mumbai")
    device:                      str   = Field(default="mobile", example="mobile")
    transaction_hour:            int   = Field(default=12, ge=0, le=23, example=2)
    transactions_last_hour:      int   = Field(default=1, ge=0, example=8)
    is_international:            int   = Field(default=0, ge=0, le=1, example=0)
    days_since_last_transaction: int   = Field(default=1, ge=0, example=0)
    avg_amount_last_7d:          float = Field(default=5000.0, gt=0, example=5000)
    amount_to_avg_ratio:         float = Field(default=1.0, example=16.9)
    is_new_merchant:             int   = Field(default=0, ge=0, le=1, example=1)
    weekend_flag:                int   = Field(default=0, ge=0, le=1, example=0)


class FeatureContribution(BaseModel):
    feature:      str
    contribution: float


class PredictResponse(BaseModel):
    # Per-transaction prediction result -- matches frontend rows[] shape.
    transaction_id: str
    channel:        str
    amount:         float
    amount_display: str          # "Rs 84,500" for display
    risk_score:     float        # 0-1
    risk_level:     str          # Low / Review / High
    decision:       str          # Approved / Review / Blocked
    signal:         str          # top human-readable reason
    top_features:   List[FeatureContribution]
    explanation:    str
    processing_ms:  int
    timestamp:      str


# Stats

class ChartData(BaseModel):
    labels:       List[str]
    transactions: List[int]
    alerts:       List[int]


class StatsResponse(BaseModel):
    total_transactions:  int
    high_risk_alerts:    int
    fraud_rate_pct:      float
    amount_saved:        float
    detection_precision: float
    avg_scoring_ms:      int
    risk_distribution:   dict
    chart_data:          ChartData


# Model metrics

class ModelComparison(BaseModel):
    name:    str
    f1:      float
    pr_auc:  float
    roc_auc: float


class ModelMetricsResponse(BaseModel):
    best_model:       str
    precision:        float
    recall:           float
    f1:               float
    roc_auc:          float
    pr_auc:           float
    confusion_matrix: List[List[int]]
    top_features:     List[Any]
    models_compared:  List[ModelComparison]


# Transactions list

class TransactionOut(BaseModel):
    transaction_id: str
    channel:        str
    amount:         float
    amount_display: str
    risk_score:     float
    risk_level:     str
    decision:       str
    signal:         str
    is_fraud:       bool
    timestamp:      str


# Alerts

class AlertOut(BaseModel):
    id:             int
    transaction_id: str
    risk_score:     float
    risk_level:     str
    amount:         float
    channel:        str
    signal:         str
    resolved:       bool
    created_at:     str


# Agent

class AgentChatRequest(BaseModel):
    session_id: str = Field(..., example="sess_abc123")
    message:    str = Field(..., min_length=1, example="Why was TXN-84A21 blocked?")


class AgentChatResponse(BaseModel):
    session_id:        str
    reply:             str
    action_suggestion: Optional[str] = None   # Approve / Hold / Block
    reasoning:         Optional[str] = None
    sources:           List[str] = []
