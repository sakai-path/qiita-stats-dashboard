import requests, pandas as pd, streamlit as st
from datetime import datetime
from functools import lru_cache

st.set_page_config(page_title="Qiita 可視化（LGTM / Stocks）", layout="wide")

# 1) トークンの取得（Secrets推奨。なければ入力欄）
token = st.secrets.get("QIITA_TOKEN", None)
if not token:
    with st.sidebar:
        token = st.text_input("Personal Access Token を入力", type="password")
if not token:
    st.warning("左のサイドバーで QIITA_TOKEN を入力するか、Secrets に設定してください。")
    st.stop()

H = {"Authorization": f"Bearer {token}"}
BASE = "https://qiita.com/api/v2"

@st.cache_data(show_spinner=False)
def fetch_all_items():
    items, page = [], 1
    while True:
        r = requests.get(f"{BASE}/authenticated_user/items",
                         headers=H, params={"page": page, "per_page": 100}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        items += batch
        link = r.headers.get("Link", "")
        if 'rel="next"' not in link or not batch:
            break
        page += 1
    return items

@st.cache_data(show_spinner=False)
def get_stock_count(item_id):
    # 1件だけ取得し Total-Count ヘッダから件数だけ取る（高速）
    r = requests.get(f"{BASE}/items/{item_id}/stockers", headers=H, params={"per_page": 1}, timeout=30)
    r.raise_for_status()
    return int(r.headers.get("Total-Count", 0))

st.title("Qiita 可視化（LGTM / ストック）")

# データ取得
raw = fetch_all_items()
if not raw:
    st.info("記事が見つかりませんでした。")
    st.stop()

df = pd.DataFrame([{
    "id": it["id"],
    "created_at": pd.to_datetime(it["created_at"]),
    "title": it["title"],
    "url": it["url"],
    "likes": it.get("likes_count", 0),
} for it in raw])

# ストック数を補完
stocks = []
for it in raw:
    stocks.append(get_stock_count(it["id"]))
df["stocks"] = stocks

# フィルタ
with st.sidebar:
    st.caption("表示フィルタ")
    start = st.date_input("開始日", value=df["created_at"].min().date())
    end = st.date_input("終了日", value=df["created_at"].max().date())
    df = df[(df["created_at"] >= pd.to_datetime(start)) & (df["created_at"] <= pd.to_datetime(end))]

# KPI
col1, col2, col3 = st.columns(3)
col1.metric("記事数", len(df))
col2.metric("LGTM合計", int(df["likes"].sum()))
col3.metric("ストック合計", int(df["stocks"].sum()))

# 月次サマリ
monthly = df.set_index("created_at")[["likes","stocks"]].resample("M").sum()
st.subheader("月次推移")
st.line_chart(monthly)

# 累積
cumsum = df.set_index("created_at")[["likes","stocks"]].sort_index().cumsum()
st.subheader("累積（Cumulative）")
st.line_chart(cumsum)

# ランキング
st.subheader("ランキング（上位20）")
ranked = df.sort_values(["likes","stocks"], ascending=False).head(20)
st.dataframe(ranked[["title","likes","stocks","url"]], use_container_width=True)
