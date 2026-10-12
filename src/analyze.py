import sqlite3
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

DB_PATH = "data/reviews.db"
vader = SentimentIntensityAnalyzer()

ASPECT_KEYWORDS = {
    "coffee_quality": ["coffee", "latte", "espresso", "cappuccino", "brew", "taste", "flavor", "roast"],
    "food": ["food", "pastry", "sandwich", "bagel", "croissant", "muffin", "snack"],
    "service": ["staff", "barista", "service", "friendly", "rude", "attentive", "server"],
    "wait_time": ["wait", "slow", "line", "queue", "quick", "fast", "took forever"],
    "price": ["price", "expensive", "cheap", "overpriced", "worth", "cost", "affordable"],
    "ambience": ["cozy", "vibe", "seating", "noisy", "quiet", "atmosphere", "decor", "music"],
}

def split_sentences(text: str):
    return re.split(r'(?<=[.!?])\s+', text)

def score_aspects(text: str) -> dict:
    sentences = split_sentences(text)
    scores = {aspect: [] for aspect in ASPECT_KEYWORDS}

    for sentence in sentences:
        lower = sentence.lower()
        for aspect, keywords in ASPECT_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                compound = vader.polarity_scores(sentence)["compound"]
                scores[aspect].append(compound)

    return {
        aspect: (sum(vals) / len(vals) if vals else None)
        for aspect, vals in scores.items()
    }

def get_vader_score(text: str) -> float:
    return vader.polarity_scores(text)["compound"]

def run_analysis(limit=None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aspect_scores (
            review_id INTEGER PRIMARY KEY,
            vader_score REAL,
            coffee_quality REAL, food REAL, service REAL,
            wait_time REAL, price REAL, ambience REAL
        )
    """)
    query = "SELECT id, review_text FROM reviews"
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    print(f"Scoring {len(rows)} reviews...")

    for i, (review_id, text) in enumerate(rows):
        vscore = get_vader_score(text)
        aspects = score_aspects(text)
        conn.execute(
            """INSERT OR REPLACE INTO aspect_scores
               (review_id, vader_score, coffee_quality, food, service, wait_time, price, ambience)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (review_id, vscore, aspects["coffee_quality"], aspects["food"],
             aspects["service"], aspects["wait_time"], aspects["price"], aspects["ambience"])
        )
        if i % 500 == 0:
            conn.commit()
            print(f"  {i}/{len(rows)}")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    run_analysis()  # no limit needed — this is free and fast, run on all reviews