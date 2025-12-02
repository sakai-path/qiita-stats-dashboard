import os
import time
import requests
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="Qiitaデータハック（いいね / ストック / タグ分析）", layout="wide")

# ========= 基本設定 =========
BASE = "https://qiita.com/api/v2"
TIMEOUT = 30
PER_PAGE = 100  # API上限
# ==========================

# ---- トークン取得（Secrets優先・なければサイドバー入力） ----
token = st.secrets.get("QIITA_TOKEN", None)
with st.sidebar:
    st.header("設定")
    if not token:
        token = st.text_input("Qiita Personal Access Token", type="password", help="read_qiita スコープでOK")
    fetch_stocks = st.toggle("ストック数も取得する（ランキングに反映）", value=True)
    top_n = st.number_input("ランキングやタグ表示の上限件数", min_value=5, max_value=100, value=30, step=5)
    st.caption("レート制限: 認証済み 1000回/時（トークン単位）")

if not token:
    st.warning("トークンを Secrets または左の入力欄に設定してください。")
    st.stop()

H = {"Authorization": f"Bearer {token}"}

# ---- API ヘルパー ----
def _has_next(link_header: str) -> bool:
    return 'rel="next"' in (link_header or "")

@st.cache_data(show_spinner=False)
def fetch_all_my_items(token_key: str):
    """認証ユーザーの記事を全件取得（ページング）。"""
    items, page = [], 1
    while True:
        r = requests.get(
            f"{BASE}/authenticated_user/items",
            headers=H,
            params={"page": page, "per_page": PER_PAGE},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        batch = r.json()
        items += batch
        if not batch or not _has_next(r.headers.get("Link", "")):
            break
        page += 1
        time.sleep(0.1)  # マナー
    return items

@st.cache_data(show_spinner=False)
def fetch_stock_count(item_id: str, token_key: str) -> int:
    """特定記事のストック数のみ（Total-Countヘッダ）を取得。"""
    r = requests.get(
        f"{BASE}/items/{item_id}/stockers",
        headers=H,
        params={"per_page": 1},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return int(r.headers.get("Total-Count", 0))

# ---- データ取得 ----
try:
    raw = fetch_all_my_items(token)
except requests.HTTPError as e:
    st.error(f"記事取得に失敗しました: HTTP {e.response.status_code}")
    st.stop()
except requests.RequestException as e:
    st.error(f"記事取得に失敗しました: {e}")
    st.stop()

if not raw:
    st.info("記事が見つかりませんでした。")
    st.stop()

# ---- DataFrame 化（全期間ベース） ----
# いいね = likes_count、views = page_views_count（なければ 0）、ストックは別途取得
df = pd.DataFrame(
    [
        {
            "id": it["id"],
            "title": it["title"],
            "url": it["url"],
            "created_at": it["created_at"],
            "likes": it.get("likes_count", 0),  # いいね
            "views": it.get("page_views_count") or 0,  # 閲覧数
            "private": it.get("private", False),       # 限定公開フラグ
            # タグ（全タグ集計用に展開）
            "tags": [t.get("name") for t in it.get("tags", []) if t.get("name")],
        }
        for it in raw
    ]
)

# タイムゾーン（UTC）→ 日本時間 → tz情報を外す（naive）に統一
df["created_at"] = (
    pd.to_datetime(df["created_at"], utc=True)
    .dt.tz_convert("Asia/Tokyo")
    .dt.tz_localize(None)
)
df["year"] = df["created_at"].dt.year
df["month"] = df["created_at"].dt.to_period("M").astype(str)  # YYYY-MM

# ---- 期間・限定公開フィルタ（サイドバー） ----
with st.sidebar:
    st.subheader("期間・対象フィルタ")

    period_mode = st.radio("集計対象期間", ("全期間", "日付を指定"), index=0)

    # デフォルトの期間は、全記事の最小/最大日付
    default_start = df["created_at"].min().date()
    default_end = df["created_at"].max().date()

    if period_mode == "全期間":
        start_date = default_start
        end_date = default_end
        st.caption(f"全期間: {start_date} ～ {end_date}")
    else:
        start_date = st.date_input("開始日", value=default_start)
        end_date = st.date_input("終了日", value=default_end)

    include_private = st.checkbox("限定公開記事も含める", value=False)

# ---- 限定公開フィルタ ----
if not include_private:
    df = df[~df["private"].fillna(False)]

# ---- 期間フィルタ ----
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # 終了日の末日まで含める

df = df[(df["created_at"] >= start_ts) & (df["created_at"] < end_ts)]

if df.empty:
    st.title("Qiita データハック・ダッシュボード（いいね / ストック / タグ分析）")
    st.info("指定した期間・公開範囲では記事がありません。")
    st.stop()

# ---- ストック数の取得（ランキングに使う） ----
if fetch_stocks:
    st.caption("ストック数を取得中…（記事数によっては少し時間がかかります）")
    stocks = []
    prog = st.progress(0.0)
    total = len(df)
    for i, item_id in enumerate(df["id"]):
        try:
            stocks.append(fetch_stock_count(item_id, token))
        except requests.RequestException:
            stocks.append(0)
        if i % 5 == 0:
            prog.progress((i + 1) / total)
        time.sleep(0.05)
    prog.progress(1.0)
    df["stocks"] = stocks
else:
    df["stocks"] = 0

# ==== タイトル（選択された期間を表示） ====
period_str = f"{start_date} ～ {end_date}"
if period_mode == "全期間":
    title_suffix = f"（全期間: {period_str}）"
else:
    title_suffix = f"（{period_str}）"

st.title(f"Qiita データハック・ダッシュボード{title_suffix}")

# ========== 上部KPI（合計） ==========
total_articles = len(df)
total_likes = int(df["likes"].sum())
total_stocks = int(df["stocks"].sum())
total_views = int(df["views"].sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("記事数", total_articles)
c2.metric("総いいね", total_likes)
c3.metric("総ストック", total_stocks)
c4.metric("総views", total_views)

# ========== KPI（平均） ==========
avg_likes = total_likes / total_articles if total_articles > 0 else 0
avg_stocks = total_stocks / total_articles if total_articles > 0 else 0
avg_views = total_views / total_articles if total_articles > 0 else 0

c5, c6, c7 = st.columns(3)
c5.metric("平均いいね / 記事", f"{avg_likes:.2f}")
c6.metric("平均ストック / 記事", f"{avg_stocks:.2f}")
c7.metric("平均views / 記事", f"{avg_views:.2f}")

# ========== 記事一覧（投稿日 / タイトル / いいね / ストック / views） ==========
st.subheader("記事一覧")

df_list = df.copy()
df_list["published_date"] = df_list["created_at"].dt.strftime("%Y-%m-%d")

# タイトルにリンクを埋め込み
df_list["記事タイトル"] = df_list.apply(
    lambda row: f"[{row['title']}]({row['url']})",
    axis=1,
)

df_display = df_list[[
    "published_date",
    "記事タイトル",
    "likes",
    "stocks",
    "views",
]].rename(columns={
    "published_date": "投稿日",
    "likes": "いいね",
    "stocks": "ストック",
    "views": "views",
})

# 投稿日の新しい順に並べ替え
df_display = df_display.sort_values("投稿日", ascending=False)

st.markdown(df_display.to_markdown(index=False), unsafe_allow_html=False)

# ========== 全記事ランキング（いいね / ストック） ==========
st.subheader("ランキング（全記事・上位）")
col_a, col_b = st.columns(2)

rank_like = df.sort_values(["likes", "stocks"], ascending=False).head(int(top_n))
rank_stock = df.sort_values(["stocks", "likes"], ascending=False).head(int(top_n))

col_a.markdown("**いいね数 ランキング**")
col_a.dataframe(rank_like[["title", "likes", "stocks", "views", "url"]], use_container_width=True)

col_b.markdown("**ストック数 ランキング**")
col_b.dataframe(rank_stock[["title", "stocks", "likes", "views", "url"]], use_container_width=True)

# ========== 時系列（期間内） ==========
st.subheader("時系列（期間内）")
monthly = df.set_index("created_at")[["likes", "stocks", "views"]].resample("M").sum()
st.line_chart(monthly)

# 累積
st.markdown("**累積（Cumulative）**")
cumsum = df.set_index("created_at")[["likes", "stocks", "views"]].sort_index().cumsum()
st.line_chart(cumsum)

# ========== いいね vs ストック 散布図 ==========
st.subheader("記事ごとの『いいね × ストック』散布図")
scatter = (
    alt.Chart(df)
    .mark_circle(size=80, opacity=0.7)
    .encode(
        x=alt.X("likes:Q", title="いいね"),
        y=alt.Y("stocks:Q", title="ストック"),
        tooltip=["title:N", "likes:Q", "stocks:Q", "views:Q", "url:N", "month:N"],
    )
    .interactive()
)
st.altair_chart(scatter, use_container_width=True)

# ========== タグ分析（全タグ集計） ==========
st.subheader("タグ分析（全タグをカウント）")

# 記事×タグを行に展開（Multi-tag explode）
df_tags = df.explode("tags")
df_tags = df_tags.dropna(subset=["tags"])

# タグ別 合計 / 平均
tag_agg = (
    df_tags.groupby("tags", as_index=False)
    .agg(
        articles=("id", "count"),
        likes_sum=("likes", "sum"),
        stocks_sum=("stocks", "sum"),
        views_sum=("views", "sum"),
        likes_avg=("likes", "mean"),
        stocks_avg=("stocks", "mean"),
        views_avg=("views", "mean"),
    )
)

# 上位タグ（合計いいね順）
top_tags = tag_agg.sort_values(["likes_sum", "stocks_sum"], ascending=False).head(int(top_n))

c5, c6 = st.columns(2)
c5.markdown("**タグ別：合計値（いいね / ストック / views） 上位**")
c5.dataframe(
    top_tags[["tags", "articles", "likes_sum", "stocks_sum", "views_sum", "likes_avg", "stocks_avg", "views_avg"]],
    use_container_width=True,
)

# 棒グラフ（合計いいねの上位タグ）
bar_likes = (
    alt.Chart(top_tags)
    .mark_bar()
    .encode(
        x=alt.X("likes_sum:Q", title="合計いいね"),
        y=alt.Y("tags:N", sort="-x", title="タグ"),
        tooltip=["tags:N", "articles:Q", "likes_sum:Q", "stocks_sum:Q", "views_sum:Q"],
    )
)
st.altair_chart(bar_likes, use_container_width=True)

# タグ × 月の推移（合計いいね）
st.markdown("**タグ×月：合計いいねの推移（上位タグのみ）**")
focus_tag_names = top_tags["tags"].tolist()
df_tags_month = (
    df_tags[df_tags["tags"].isin(focus_tag_names)]
    .groupby(["month", "tags"], as_index=False)
    .agg(likes_sum=("likes", "sum"), stocks_sum=("stocks", "sum"), views_sum=("views", "sum"))
)

line_tag_month = (
    alt.Chart(df_tags_month)
    .mark_line(point=True)
    .encode(
        x=alt.X("month:N", title="年月（YYYY-MM）", sort=None),
        y=alt.Y("likes_sum:Q", title="合計いいね"),
        color=alt.Color("tags:N", title="タグ"),
        tooltip=["month:N", "tags:N", "likes_sum:Q", "stocks_sum:Q", "views_sum:Q"],
    )
    .properties(height=350)
    .interactive()
)
st.altair_chart(line_tag_month, use_container_width=True)

# ========== データハック的ビュー ==========
st.subheader("データハック：発見を促すビュー")

# ストックが多いのに「いいね」が少ない（参考保存系？）
ref_like = df[df["stocks"] > df["likes"]].sort_values("stocks", ascending=False).head(int(top_n))
st.markdown("**ストック > いいね の記事（参考保存されやすい）**")
st.dataframe(ref_like[["title", "likes", "stocks", "views", "url"]], use_container_width=True)

# 直近で伸びやすい“バズ”候補（いいねが上位、ストックもそこそこ）
buzz = df.sort_values(["likes", "stocks"], ascending=False).head(int(top_n))
st.markdown("**直近の“バズ”上位（いいね優先・ストック順でブレークダウン）**")
st.dataframe(buzz[["title", "likes", "stocks", "views", "url"]], use_container_width=True)

# ========== CSVエクスポート ==========
st.subheader("エクスポート")
csv_all = df.sort_values("created_at").to_csv(index=False)
st.download_button("全記事（基本列）CSVをダウンロード", csv_all, file_name="qiita_articles.csv", mime="text/csv")

csv_tag = tag_agg.sort_values("likes_sum", ascending=False).to_csv(index=False)
st.download_button("タグ集計（合計・平均）CSVをダウンロード", csv_tag, file_name="qiita_tag_agg.csv", mime="text/csv")
