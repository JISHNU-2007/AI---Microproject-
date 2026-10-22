# seed.py
# Seeds the SQLite database with ~500 realistic sample transactions
# so the dashboard is never empty on first launch.
#
# Run: python backend/seed.py
# (Run AFTER starting the server at least once so tables exist,
#  OR call create_tables() explicitly as done below.)

import sys, os, json, random, string
from datetime import datetime, timedelta

# Allow imports from backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from database import create_tables, SessionLocal, Transaction, Alert
from sqlalchemy import func
import predictor

CHANNELS   = ["Card", "UPI", "Wallet", "NetBanking"]
CATEGORIES = ["Electronics", "Grocery", "Travel", "Entertainment",
              "Fuel", "Fashion", "Utilities", "Food", "Jewelry", "Other"]
LOCATIONS  = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
              "Kolkata", "Pune", "Jaipur", "Ahmedabad", "International"]
DEVICES    = ["mobile", "desktop", "tablet", "pos_terminal", "atm"]

rng = random.Random(42)


def _make_txn_id():
    return "TXN-" + "".join(rng.choices(string.ascii_uppercase + string.digits, k=5))


def _make_transaction(fraud: bool, hours_ago: float):
    if fraud:
        amount   = rng.uniform(15_000, 200_000)
        hour     = rng.choice([0, 1, 2, 3, 4, 22, 23])
        vel      = rng.randint(6, 18)
        avg_amt  = amount * rng.uniform(0.05, 0.3)
        location = rng.choice(LOCATIONS[-3:])
        is_intl  = 1 if location == "International" else 0
        is_new   = 1
    else:
        amount   = rng.uniform(500, 50_000)
        hour     = rng.randint(8, 22)
        vel      = rng.randint(0, 3)
        avg_amt  = amount * rng.uniform(0.7, 1.5)
        location = rng.choice(LOCATIONS[:-1])
        is_intl  = 0
        is_new   = rng.randint(0, 1)

    ratio = amount / (avg_amt + 1)
    return {
        "amount":                      round(amount, 2),
        "channel":                     rng.choice(CHANNELS),
        "merchant_category":           rng.choice(CATEGORIES),
        "location":                    location,
        "device":                      rng.choice(DEVICES),
        "transaction_hour":            hour,
        "transactions_last_hour":      vel,
        "is_international":            is_intl,
        "days_since_last_transaction": rng.randint(0, 6),
        "avg_amount_last_7d":          round(avg_amt, 2),
        "amount_to_avg_ratio":         round(ratio, 3),
        "is_new_merchant":             is_new,
        "weekend_flag":                rng.randint(0, 1),
        "_hours_ago":                  hours_ago,
    }


def seed():
    create_tables()
    db = SessionLocal()

    count = db.query(func.count(Transaction.id)).scalar()
    if count and count > 0:
        print(f"DB already has {count} transactions. Skipping seed.")
        db.close()
        return

    print("Seeding database with 500 sample transactions...")
    n_total = 500
    n_fraud = 38    # ~7.5% for demo visibility
    n_legit = n_total - n_fraud

    rows = []
    for _ in range(n_legit):
        rows.append((_make_transaction(False, rng.uniform(0, 24 * 7)), False))
    for _ in range(n_fraud):
        rows.append((_make_transaction(True,  rng.uniform(0, 24 * 7)), True))

    rng.shuffle(rows)

    for data, is_fraud in rows:
        hours_ago = data.pop("_hours_ago")
        score, level, dec, signal, top_feats, _, _ = predictor.predict(data)
        ts = datetime.utcnow() - timedelta(hours=hours_ago)

        txn_id = _make_txn_id()
        db.add(Transaction(
            transaction_id=txn_id,
            channel=data["channel"],
            amount=data["amount"],
            merchant_category=data["merchant_category"],
            location=data["location"],
            device=data["device"],
            transaction_hour=data["transaction_hour"],
            transactions_last_hour=data["transactions_last_hour"],
            is_international=bool(data["is_international"]),
            days_since_last_transaction=data["days_since_last_transaction"],
            avg_amount_last_7d=data["avg_amount_last_7d"],
            amount_to_avg_ratio=data["amount_to_avg_ratio"],
            is_new_merchant=bool(data["is_new_merchant"]),
            weekend_flag=bool(data["weekend_flag"]),
            risk_score=round(score, 4),
            risk_level=level,
            decision=dec,
            signal=signal,
            top_features=json.dumps(top_feats),
            is_fraud=is_fraud,
            timestamp=ts,
        ))
        if score >= 0.78:
            db.add(Alert(
                transaction_id=txn_id,
                risk_score=round(score, 4),
                risk_level=level,
                amount=data["amount"],
                channel=data["channel"],
                signal=signal,
                created_at=ts,
            ))

    db.commit()
    final_t = db.query(func.count(Transaction.id)).scalar()
    final_a = db.query(func.count(Alert.id)).scalar()
    print(f"Seeded {final_t} transactions. Alerts created: {final_a}")
    db.close()


if __name__ == "__main__":
    seed()
