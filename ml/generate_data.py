# generate_data.py
# Generates a realistic synthetic credit-card / UPI / wallet fraud dataset.
# ~100,000 rows, ~1.5% fraud rate.
#
# Run:    python ml/generate_data.py
# Output: ml/fraud_dataset.csv

import numpy as np
import pandas as pd
import os

SEED       = 42
N_TOTAL    = 100_000
FRAUD_RATE = 0.015

CHANNELS   = ["Card", "UPI", "Wallet", "NetBanking"]
CATEGORIES = ["Electronics", "Grocery", "Travel", "Entertainment",
              "Fuel", "Fashion", "Utilities", "Food", "Jewelry", "Other"]
LOCATIONS  = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
              "Kolkata", "Pune", "Jaipur", "Ahmedabad", "International"]
DEVICES    = ["mobile", "desktop", "tablet", "pos_terminal", "atm"]


def generate_legit(n, rng):
    df = pd.DataFrame()
    df["amount"]                      = rng.lognormal(8.5, 1.2, n).clip(100, 250_000)
    df["channel"]                     = rng.choice(CHANNELS,    n, p=[0.45, 0.30, 0.15, 0.10])
    df["merchant_category"]           = rng.choice(CATEGORIES,  n, p=[0.08, 0.20, 0.10, 0.08, 0.08, 0.12, 0.10, 0.14, 0.02, 0.08])
    df["location"]                    = rng.choice(LOCATIONS,   n, p=[0.18, 0.16, 0.14, 0.10, 0.10, 0.09, 0.08, 0.06, 0.05, 0.04])
    df["device"]                      = rng.choice(DEVICES,     n, p=[0.50, 0.20, 0.10, 0.15, 0.05])
    df["transaction_hour"]            = rng.integers(6, 23, size=n)
    df["transactions_last_hour"]      = rng.integers(0, 4,  size=n)
    df["is_international"]            = (df["location"] == "International").astype(int)
    df["days_since_last_transaction"] = rng.integers(0, 7,  size=n)
    df["avg_amount_last_7d"]          = df["amount"] * rng.uniform(0.8, 1.3, n)
    df["amount_to_avg_ratio"]         = df["amount"] / (df["avg_amount_last_7d"] + 1)
    df["is_new_merchant"]             = rng.integers(0, 2, size=n)
    df["weekend_flag"]                = rng.integers(0, 2, size=n)
    df["label"]                       = 0
    return df


def generate_fraud(n, rng):
    df = pd.DataFrame()
    df["amount"]                      = rng.lognormal(10.2, 1.5, n).clip(500, 500_000)
    df["channel"]                     = rng.choice(CHANNELS,    n, p=[0.65, 0.15, 0.10, 0.10])
    df["merchant_category"]           = rng.choice(CATEGORIES,  n, p=[0.25, 0.05, 0.15, 0.05, 0.05, 0.10, 0.05, 0.05, 0.15, 0.10])
    df["location"]                    = rng.choice(LOCATIONS,   n, p=[0.10, 0.10, 0.08, 0.07, 0.07, 0.06, 0.06, 0.05, 0.05, 0.36])
    df["device"]                      = rng.choice(DEVICES,     n, p=[0.45, 0.25, 0.15, 0.05, 0.10])
    df["transaction_hour"]            = rng.choice([0, 1, 2, 3, 4, 5, 22, 23], size=n)
    df["transactions_last_hour"]      = rng.integers(5, 20, size=n)
    df["is_international"]            = (df["location"] == "International").astype(int)
    df["days_since_last_transaction"] = rng.integers(0, 3, size=n)
    df["avg_amount_last_7d"]          = df["amount"] * rng.uniform(0.1, 0.5, n)
    df["amount_to_avg_ratio"]         = df["amount"] / (df["avg_amount_last_7d"] + 1)
    df["is_new_merchant"]             = 1
    df["weekend_flag"]                = rng.integers(0, 2, size=n)
    df["label"]                       = 1
    return df


def main():
    rng     = np.random.default_rng(SEED)
    n_fraud = int(N_TOTAL * FRAUD_RATE)
    n_legit = N_TOTAL - n_fraud
    print(f"Generating {n_legit:,} legit + {n_fraud:,} fraud rows...")
    df = pd.concat([generate_legit(n_legit, rng), generate_fraud(n_fraud, rng)], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    for col in ["channel", "merchant_category", "location", "device"]:
        df[col + "_enc"] = df[col].astype("category").cat.codes
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraud_dataset.csv")
    df.to_csv(out, index=False)
    print(f"Saved {len(df):,} rows -> {out}")
    print(f"Fraud rate: {df['label'].mean() * 100:.2f}%")


if __name__ == "__main__":
    main()
