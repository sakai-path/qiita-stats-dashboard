import os
import time
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Qiita 可視化（LGTM / ストック）", layout="wide")

# ========== 設定 ==========
BASE = "https://qiita.com/api/v2"
DEFAULT_PER_PAGE = 100  # 最大100
TIMEOUT = 30
# =========================

# ---- トークン取得（Secrets優先・なければサイドバー入力） ----
token = st.secrets.get("QIITA_TOKEN", None)
with st.sidebar:
    st.header("設定")
    if not token:
        token = st.text_input("Qiita Personal Access Token", type="password", help="read_qiita スコープでOK")
    fetch_stocks = st.toggle("ストック数も取得する（API呼び出しが増えます）", value=True,
                             help="記事数が多い場合は時間がかかります。必要なときだけONに。")
    st.caption("※ レート制限: 認証済み 1000回/時（トークン単位）")

if not token:
    st.warning("トークンを Secrets または左の入力欄に設定してください。")
    st.stop()

H = {"Authorization": f"Bearer {token}"}

# ---- API ヘルパー ----
def has_next(link_header: str) -> bool:
    return 'rel="next"' in (link_header or "")

@st.cache_data(show_spinner=False)
def fetch_all_my_items(token_key: str):
    """認証ユーザーの記事を全件取得（ページング）。token_keyはキャッシュキー用。"""
    items, page = [], 1
    while True:
        r = requests.get(
            f"{BASE}/authenticated_user/items",
            headers=H, params={"page": page, "per_page": DEFAULT_PER_PAGE}, timeout=TIMEOUT
        )
        r.raise_for_status()
        batch = r.json()
        items += batch
        if not batch or not has_next(r.headers.get("Link", "")):
            break
        page += 1
        time.sleep(0.1)  # マナー
    return items

@st.cache_data(show_spinner=False)
def fetch_stock_count(item_id: str, token_key: str) -> int:
    """特定記事のストック数のみをヘッダ Total-Count で取得"""
    r = requests.get(f"{BASE}/items/{item_id}/stockers",
                     headers=H, params={"per_page": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    return int(r.headers.get("Total-Count", 0))

# ---- データ取得 ----
st.title("Qiita 可視化（LGTM / ストック）")

try:
    raw = fetch_all_my_items(token)  # token をキャッシュキーに
except requests.HTTPError as e:
    st.error(f"記事取得に失敗しました: HTTP {e.response.status_code}")
    st.stop()
except requests.RequestException as e:
    st.error(f"記事取得に失敗しました: {e}")
    st.stop()

if not raw:
    st.info("記事が見つかりませんでした。")
    st.stop()

# ---- DataFrame 化 ----
df = pd.DataFrame([{
    "id": it["id"],
    "created_at": it["created_at"],
    "title": it["title"],
    "url": it["url"],
    "likes": it.get("likes_count", 0),
} for it in raw])

# タイムゾーンを“naive”へ統一（バグの原因対策）
df["created_at"] = (
    pd.to_datetime(df["created_at"], utc=True)   # tz-aware(UTC)
      .dt.tz_convert("Asia/Tokyo")               # 日本時間へ
      .dt.tz_localize(None)                      # tz情報を外す（naive）
)

# ---- ストック数の取得（任意） ----
if fetch_stocks:
    st.caption("ストック数を取得中…（記事数によっては少し時間がかかります）")
    stocks = []
    prog = st.progress(0.0)
    total = len(df)
    for i, item_id in enumerate(df["id"]):
        try:
            stocks.append(fetch_stock_count(item_id, token))
        except requests.HTTPError as e:
            # 権限不足などは 0 扱い
            stocks.append(0)
        except requests.RequestException:
            stocks.append(0)
        if i % 5 == 0:
            prog.progress((i + 1) / total)
        time.sleep(0.05)
    prog.progress(1.0)
    df["stocks"] = stocks
else:
    df["stocks"] = 0

# ---- 期間フィルタ ----
with st.sidebar:
    st.subheader("表示期間")
    start = st.date_input("開始日", value=df["created_at"].min().date())
    end = st.date_input("終了日", value=df["created_at"].max().date())
# （naive同士で比較）
start_ts = pd.to_datetime(start)
end_ts = pd.to_datetime(end) + pd.Timedelta(days=1)  # 終了日の当日末まで含める
df = df[(df["created_at"] >= start_ts) & (df["created_at"] < end_ts)]

if df.empty:
    st.info("期間内のデータがありません。")
    st.stop()

# ---- KPI ----
c1, c2, c3 = st.columns(3)
c1.metric("記事数", len(df))
c2.metric("LGTM合計", int(df["likes"].sum()))
c3.metric("ストック合計", int(df["stocks"].sum()))

# ---- 可視化 ----
st.subheader("月次推移（LGTM / ストック）")
monthly = df.set_index("created_at")[["likes", "stocks"]].resample("M").sum()
st.line_chart(monthly)

st.subheader("累積（Cumulative）")
cumsum = df.set_index("created_at")[["likes", "stocks"]].sort_index().cumsum()
st.line_chart(cumsum)

st.subheader("ランキング（上位20）")
ranked = df.sort_values(["likes", "stocks"], ascending=False).head(20)
st.dataframe(ranked[["title", "likes", "stocks", "url"]], use_container_width=True)

