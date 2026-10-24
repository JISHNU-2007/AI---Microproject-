# database.py - SQLAlchemy models and database engine setup.
# Uses SQLite (fraud.db inside /backend).

import os
from datetime import datetime
from sqlalchemy import (create_engine, Column, Integer, Float, String,
                        Boolean, DateTime, Text)
from sqlalchemy.orm import declarative_base, sessionmaker

# Engine setup
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraud.db").replace("\\", "/")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
if DATABASE_URL.startswith("sqlite:///./"):
    rel_name = DATABASE_URL[12:]
    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_name).replace("\\", "/")
    DATABASE_URL = f"sqlite:///{abs_path}"

engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


# ORM Models

class Transaction(Base):
    # Stores every transaction that passed through the system.
    __tablename__ = "transactions"

    id                          = Column(Integer, primary_key=True, index=True)
    transaction_id              = Column(String(20), unique=True, index=True)
    channel                     = Column(String(20))   # Card / UPI / Wallet / NetBanking
    amount                      = Column(Float)
    merchant_category           = Column(String(50))
    location                    = Column(String(50))
    device                      = Column(String(30))
    transaction_hour            = Column(Integer)
    transactions_last_hour      = Column(Integer)
    is_international            = Column(Boolean, default=False)
    days_since_last_transaction = Column(Integer, default=0)
    avg_amount_last_7d          = Column(Float, default=0.0)
    amount_to_avg_ratio         = Column(Float, default=1.0)
    is_new_merchant             = Column(Boolean, default=False)
    weekend_flag                = Column(Boolean, default=False)

    # ML output
    risk_score   = Column(Float, default=0.0)   # 0-1 probability
    risk_level   = Column(String(10))           # Low / Review / High
    decision     = Column(String(10))           # Approved / Review / Blocked
    signal       = Column(String(100))          # human-readable top reason
    top_features = Column(Text, default="[]")   # JSON string of SHAP contributions

    # Ground truth (for seeded/known data)
    is_fraud  = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    # High-risk transactions requiring human review.
    __tablename__ = "alerts"

    id             = Column(Integer, primary_key=True)
    transaction_id = Column(String(20), index=True)
    risk_score     = Column(Float)
    risk_level     = Column(String(10))
    amount         = Column(Float)
    channel        = Column(String(20))
    signal         = Column(String(100))
    resolved       = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    # Stores conversation history per session for the AI agent.
    __tablename__ = "chat_sessions"

    id         = Column(Integer, primary_key=True)
    session_id = Column(String(50), index=True)
    role       = Column(String(10))   # user / model
    message    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


def create_tables():
    # Create all tables if they do not exist.
    Base.metadata.create_all(bind=engine)


def get_db():
    # FastAPI dependency: yields a DB session and closes it after the request.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
