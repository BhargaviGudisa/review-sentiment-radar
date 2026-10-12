import json
import sqlite3
import pandas as pd
import math

YELP_BUSINESS_PATH = "data/yelp_academic_dataset_business.json"
YELP_REVIEW_PATH = "data/yelp_academic_dataset_review.json"
DB_PATH = "data/reviews.db"

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.asin(math.sqrt(a))

def load_businesses():
    rows = []
    with open(YELP_BUSINESS_PATH, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return pd.DataFrame(rows)

def find_coffee_shops(df, city="Philadelphia"):
    coffee = df[
        df["categories"].str.contains("Coffee", na=False) &
        (df["city"] == city) &
        (df["is_open"] == 1) &
        (df["review_count"] >= 150)
    ].copy()
    return coffee

def pick_scope(coffee_df):
    candidates = coffee_df[(coffee_df["stars"].between(3.5, 4.0)) & (coffee_df["review_count"] >= 300)]
    target = candidates.sort_values("review_count", ascending=False).iloc[0]

    others = coffee_df[coffee_df["business_id"] != target["business_id"]].copy()
    others["distance"] = others.apply(
        lambda r: haversine(target["latitude"], target["longitude"], r["latitude"], r["longitude"]), axis=1
    )
    nearby = others[(others["distance"] <= 2.0) & (others["review_count"] >= 150)]
    competitors = nearby.sort_values("review_count", ascending=False).head(5)

    scope = pd.concat([
        pd.DataFrame([{**target.to_dict(), "role": "target"}]),
        competitors.assign(role="competitor")
    ])
    return scope[["role", "name", "business_id", "stars", "review_count", "postal_code"]]

def load_reviews_for_scope(scope_df):
    ids = set(scope_df["business_id"])
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            place_id TEXT PRIMARY KEY, name TEXT, rating REAL, review_count INTEGER, role TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, place_id TEXT, author TEXT,
            rating INTEGER, review_text TEXT, review_date TEXT
        )
    """)
    for _, row in scope_df.iterrows():
        conn.execute(
            "INSERT OR REPLACE INTO businesses VALUES (?, ?, ?, ?, ?)",
            (row["business_id"], row["name"], row["stars"], row["review_count"], row["role"])
        )
    conn.commit()

    count = 0
    with open(YELP_REVIEW_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["business_id"] in ids:
                conn.execute(
                    "INSERT INTO reviews (place_id, author, rating, review_text, review_date) VALUES (?, ?, ?, ?, ?)",
                    (r["business_id"], r["user_id"], r["stars"], r["text"], r["date"])
                )
                count += 1
    conn.commit()
    conn.close()
    print(f"Loaded {count} reviews for {len(ids)} businesses")

if __name__ == "__main__":
    print("Loading businesses...")
    df = load_businesses()
    coffee = find_coffee_shops(df)
    print(f"Found {len(coffee)} candidate coffee shops")

    scope = pick_scope(coffee)
    scope.to_csv("data/scope.csv", index=False)
    print(scope[["role", "name", "stars", "review_count"]])

    load_reviews_for_scope(scope)