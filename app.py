import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

DB_PATH = "data/reviews.db"
ASPECTS = ["coffee_quality", "food", "service", "wait_time", "price", "ambience"]
ASPECT_LABELS = ["Coffee Quality", "Food", "Service", "Wait Time", "Price", "Ambience"]

st.set_page_config(page_title="Review Sentiment & Competitor Radar", layout="wide")

@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    businesses = pd.read_sql("SELECT * FROM businesses", conn)
    reviews = pd.read_sql("""
        SELECT r.*, a.vader_score, a.coffee_quality, a.food, a.service,
               a.wait_time, a.price, a.ambience
        FROM reviews r
        JOIN aspect_scores a ON r.id = a.review_id
    """, conn)
    conn.close()
    return businesses, reviews

businesses, reviews = load_data()

st.title("☕ Review Sentiment & Competitor Radar")
st.caption("Aspect-based sentiment analysis comparing a target business against nearby competitors")

# --- Sidebar ---
st.sidebar.header("Select Businesses")
all_names = businesses["name"].tolist()
target_name = businesses[businesses["role"] == "target"]["name"].iloc[0]
default_competitors = businesses[businesses["role"] == "competitor"]["name"].tolist()

selected = st.sidebar.multiselect(
    "Compare these businesses:",
    options=all_names,
   default=[target_name] + default_competitors[:2]
)

if not selected:
    st.warning("Select at least one business from the sidebar.")
    st.stop()

filtered_biz = businesses[businesses["name"].isin(selected)]
filtered_reviews = reviews[reviews["place_id"].isin(filtered_biz["place_id"])]

# --- KPI cards ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Businesses Compared", len(filtered_biz))
with col2:
    st.metric("Total Reviews", len(filtered_reviews))
with col3:
    avg_sentiment = filtered_reviews["vader_score"].mean()
    st.metric("Avg Sentiment", f"{avg_sentiment:.2f}")

# --- Radar chart ---
st.subheader("Aspect Comparison Radar")

fig = go.Figure()
for _, biz in filtered_biz.iterrows():
    biz_reviews = filtered_reviews[filtered_reviews["place_id"] == biz["place_id"]]
    values = [biz_reviews[aspect].mean() for aspect in ASPECTS]
    values.append(values[0])  # close the loop
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=ASPECT_LABELS + [ASPECT_LABELS[0]],
        fill='toself',
        name=biz["name"]
    ))

fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    showlegend=True,
    height=500
)
st.plotly_chart(fig, width='stretch')

# --- Aspect table ---
st.subheader("Aspect Scores by Business")
table_rows = []
for _, biz in filtered_biz.iterrows():
    biz_reviews = filtered_reviews[filtered_reviews["place_id"] == biz["place_id"]]
    row = {"Business": biz["name"], "Role": biz["role"]}
    for aspect, label in zip(ASPECTS, ASPECT_LABELS):
        row[label] = round(biz_reviews[aspect].mean(), 3)
    table_rows.append(row)
st.dataframe(pd.DataFrame(table_rows), width='stretch')

# --- Gap insight ---
st.subheader("Competitor Gap Insight")
target_row = filtered_biz[filtered_biz["role"] == "target"]
if not target_row.empty:
    target_id = target_row.iloc[0]["place_id"]
    target_reviews = filtered_reviews[filtered_reviews["place_id"] == target_id]
    target_scores = {a: target_reviews[a].mean() for a in ASPECTS}

    comp_reviews = filtered_reviews[filtered_reviews["place_id"] != target_id]
    comp_scores = {a: comp_reviews[a].mean() for a in ASPECTS}

    gaps = sorted(
        [(a, target_scores[a] - comp_scores[a]) for a in ASPECTS],
        key=lambda x: x[1]
    )
    worst = gaps[:3]

    st.write(f"**{target_row.iloc[0]['name']}** vs. competitor average — biggest gaps:")
    for aspect, gap in worst:
        label = ASPECT_LABELS[ASPECTS.index(aspect)]
        direction = "behind" if gap < 0 else "ahead of"
        st.write(f"- **{label}**: {direction} competitors by {abs(gap):.2f} points")
else:
    st.info("Select the target business to see gap analysis.")

# --- Review table ---
st.subheader("Browse Reviews")
aspect_filter = st.selectbox("Filter by aspect mentioned:", ["All"] + ASPECT_LABELS)
display_reviews = filtered_reviews[["review_text", "rating", "review_date", "vader_score"]].copy()
if aspect_filter != "All":
    col = ASPECTS[ASPECT_LABELS.index(aspect_filter)]
    display_reviews = filtered_reviews[filtered_reviews[col].notna()][
        ["review_text", "rating", "review_date", col]
    ]
st.dataframe(display_reviews.head(100), width='stretch')