import os
import time
import math
import requests
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="Qiitaデータハック（いいね / ストック / タグ分析）", layout="wide")

# ========= KPI用の簡易カード =========
def metric_card(label: str, value: str, bg_color: str):
    st.markdown(
        f"""
        <div style="
            background-color:{bg_color};
            padding:8px 10px;
            border-radius:8px;
            border:1px solid #e0e0e0;
        ">
            <div style="font-size:0.9rem;color:#333;">{label}</div>
            <div style="font-size:1.4rem;font-weight:bold;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ========= 基本設定 =========
BASE = "https://qiita.com/api/v2"
TIMEOUT = 30
PER_PAGE = 100  # API上限
# ==========================

# ---- 認証（Secrets優先・なければサイドバー入力） ----
token = st.secrets.get("QIITA_TOKEN", None)
with st.sidebar:
    st.header("認証")
    if not token:
        token = st.text_input(
            "Qiita Personal Access Token",
            type="password",
            help="read_qiita スコープでOK",
        )

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
df = pd.DataFrame(
    [
        {
            "id": it["id"],
            "title": it["title"],
            "url": it["url"],
            "created_at": it["created_at"],
            "likes": it.get("likes_count", 0),        # いいね
            "stocks": it.get("stocks_count", 0),      # ストック（あれば）
            "views": it.get("page_views_count") or 0, # 閲覧数
            "private": it.get("private", False),      # 限定公開フラグ
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

# ---- サイドバー：期間・対象フィルタ + 設定（この順番で表示） ----
with st.sidebar:
    st.subheader("期間・対象フィルタ")

    period_mode = st.radio("集計対象期間", ("全期間", "日付を指定"), index=0)

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

    st.header("設定")
    top_n = st.number_input(
        "ランキングやタグ表示の上限件数",
        min_value=5,
        max_value=100,
        value=30,
        step=5,
    )
    st.caption("レート制限: 認証済み 1000回/時（トークン単位）")

# ---- 限定公開フィルタ ----
if not include_private:
    df = df[~df["private"].fillna(False)]

# ---- 期間フィルタ ----
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # 終了日の末日まで含める
df = df[(df["created_at"] >= start_ts) & (df["created_at"] < end_ts)]

if df.empty:
    st.markdown("# Qiita データハック")
    st.markdown(f"### （{start_date} ～ {end_date}）")
    st.info("指定した期間・公開範囲では記事がありません。")
    st.stop()

# ==== タイトル（選択された期間を表示） ====
period_str = f"{start_date} ～ {end_date}"
st.markdown(f"# Qiita データハック\n### （{period_str}）")

# ========== 上部KPI（合計：薄いブルー） ==========
total_articles = len(df)
total_likes = int(df["likes"].sum())
total_stocks = int(df["stocks"].sum())
total_views = int(df["views"].sum())

st.markdown("#### 合計")
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("記事数", f"{total_articles}", "#e3f2fd")
with c2:
    metric_card("総いいね", f"{total_likes}", "#e3f2fd")
with c3:
    metric_card("総ストック", f"{total_stocks}", "#e3f2fd")
with c4:
    metric_card("総views", f"{total_views}", "#e3f2fd")

# ========== KPI（平均：薄いイエロー／小数点以下2桁切り捨て） ==========
def floor2(x: float) -> float:
    return math.floor(x * 100) / 100 if x is not None else 0.0

avg_likes = floor2(total_likes / total_articles) if total_articles > 0 else 0.0
avg_stocks = floor2(total_stocks / total_articles) if total_articles > 0 else 0.0
avg_views = floor2(total_views / total_articles) if total_articles > 0 else 0.0

st.markdown("#### 平均（1記事あたり）")
a1, a2, a3 = st.columns(3)
with a1:
    metric_card("平均いいね / 記事", f"{avg_likes:.2f}", "#fff8e1")
with a2:
    metric_card("平均ストック / 記事", f"{avg_stocks:.2f}", "#fff8e1")
with a3:
    metric_card("平均views / 記事", f"{avg_views:.2f}", "#fff8e1")

# ========== 記事一覧 ==========
st.subheader("記事一覧")

df_list = df.copy()
df_list["投稿日"] = df_list["created_at"].dt.strftime("%Y-%m-%d")
df_list["投稿日"] = df_list["投稿日"].apply(
    lambda d: f'<span style="white-space: nowrap;">{d}</span>'
)
df_list["記事タイトル"] = df_list.apply(
    lambda row: f'<a href="{row["url"]}" target="_blank">{row["title"]}</a>',
    axis=1,
)
df_display = df_list[["投稿日", "記事タイトル", "likes", "stocks", "views"]].rename(
    columns={"likes": "いいね", "stocks": "ストック", "views": "views"}
)

sort_order = st.radio("並び順", ("投稿日が古い順", "投稿日が新しい順"), horizontal=True)
ascending = True if "古い" in sort_order else False
df_display = df_display.sort_values("投稿日", ascending=ascending)

html_articles = df_display.to_html(escape=False, index=False)
st.write(html_articles, unsafe_allow_html=True)

# ========== ランキング（全記事・上位：表） ==========
st.subheader("ランキング（全記事・上位）")
col_a, col_b = st.columns(2)

# いいねランキング
rank_like = df.sort_values(["likes", "stocks"], ascending=False).head(int(top_n)).copy()
rank_like["順位"] = range(1, len(rank_like) + 1)
rank_like["タイトル"] = rank_like.apply(
    lambda row: f'<a href="{row["url"]}" target="_blank">{row["title"]}</a>',
    axis=1,
)
display_like = rank_like[["順位", "タイトル", "likes", "stocks", "views"]].rename(
    columns={"likes": "いいね", "stocks": "ストック", "views": "views"}
)
html_like = display_like.to_html(escape=False, index=False)
col_a.markdown("**いいね数 ランキング**")
col_a.write(html_like, unsafe_allow_html=True)

# ストックランキング
rank_stock = df.sort_values(["stocks", "likes"], ascending=False).head(int(top_n)).copy()
rank_stock["順位"] = range(1, len(rank_stock) + 1)
rank_stock["タイトル"] = rank_stock.apply(
    lambda row: f'<a href="{row["url"]}" target="_blank">{row["title"]}</a>',
    axis=1,
)
display_stock = rank_stock[["順位", "タイトル", "stocks", "likes", "views"]].rename(
    columns={"likes": "いいね", "stocks": "ストック", "views": "views"}
)
html_stock = display_stock.to_html(escape=False, index=False)
col_b.markdown("**ストック数 ランキング**")
col_b.write(html_stock, unsafe_allow_html=True)

# ========== ランキング（グラフ） ==========
st.subheader("ランキング（グラフ）")

g1, g2 = st.columns(2)

# いいね＆ストック（上位N）
like_for_chart = rank_like.copy()  # さっき作った上位Nをそのまま利用
like_fold = like_for_chart.melt(
    id_vars=["title"],
    value_vars=["likes", "stocks"],
    var_name="指標",
    value_name="値",
)

chart_like_stock = (
    alt.Chart(like_fold)
    .mark_bar()
    .encode(
        x=alt.X("値:Q", title="件数"),
        y=alt.Y("title:N", sort="-x", title="記事タイトル"),
        color=alt.Color("指標:N", title="指標", scale=alt.Scale(domain=["likes", "stocks"], range=["#42a5f5", "#66bb6a"])),
        tooltip=["title:N", "指標:N", "値:Q"],
    )
    .properties(height=350)
)
g1.markdown("**いいね＆ストック 上位**")
g1.altair_chart(chart_like_stock, use_container_width=True)

# views ランキング（上位N）
rank_views = df.sort_values("views", ascending=False).head(int(top_n)).copy()
chart_views = (
    alt.Chart(rank_views)
    .mark_bar()
    .encode(
        x=alt.X("views:Q", title="views"),
        y=alt.Y("title:N", sort="-x", title="記事タイトル"),
        tooltip=["title:N", "views:Q", "likes:Q", "stocks:Q"],
    )
    .properties(height=350)
)
g2.markdown("**views 上位**")
g2.altair_chart(chart_views, use_container_width=True)

# ========== 時系列（期間内：いいね / ストックのみ） ==========
st.subheader("時系列（期間内）")
monthly = df.set_index("created_at")[["likes", "stocks"]].resample("M").sum()
st.line_chart(monthly)

st.markdown("**累積（Cumulative）**")
cumsum = df.set_index("created_at")[["likes", "stocks"]].sort_index().cumsum()
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

df_tags = df.explode("tags")
df_tags = df_tags.dropna(subset=["tags"])

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

top_tags = tag_agg.sort_values(["likes_sum", "stocks_sum"], ascending=False).head(int(top_n))

display_tags = top_tags[
    ["tags", "articles", "likes_sum", "stocks_sum", "views_sum", "likes_avg", "stocks_avg", "views_avg"]
].rename(
    columns={
        "tags": "タグ",
        "articles": "記事数",
        "likes_sum": "合計いいね",
        "stocks_sum": "合計ストック",
        "views_sum": "合計views",
        "likes_avg": "平均いいね",
        "stocks_avg": "平均ストック",
        "views_avg": "平均views",
    }
)

st.markdown("**タグ別：合計値 / 平均値（いいね / ストック / views） 上位**")
html_tags = display_tags.to_html(index=False)
st.write(html_tags, unsafe_allow_html=True)

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

# ストック > いいね
ref_like = df[df["stocks"] > df["likes"]].sort_values("stocks", ascending=False).head(int(top_n))
ref_like_disp = ref_like.copy()
ref_like_disp["タイトル"] = ref_like_disp.apply(
    lambda row: f'<a href="{row["url"]}" target="_blank">{row["title"]}</a>',
    axis=1,
)
ref_like_disp = ref_like_disp[["タイトル", "likes", "stocks", "views"]].rename(
    columns={"likes": "いいね", "stocks": "ストック", "views": "views"}
)
st.markdown("**ストック > いいね の記事（参考保存されやすい）**")
st.write(ref_like_disp.to_html(escape=False, index=False), unsafe_allow_html=True)

# バズ候補
buzz = df.sort_values(["likes", "stocks"], ascending=False).head(int(top_n))
buzz_disp = buzz.copy()
buzz_disp["タイトル"] = buzz_disp.apply(
    lambda row: f'<a href="{row["url"]}" target="_blank">{row["title"]}</a>',
    axis=1,
)
buzz_disp = buzz_disp[["タイトル", "likes", "stocks", "views"]].rename(
    columns={"likes": "いいね", "stocks": "ストック", "views": "views"}
)
st.markdown("**直近の“バズ”上位（いいね優先・ストック順でブレークダウン）**")
st.write(buzz_disp.to_html(escape=False, index=False), unsafe_allow_html=True)

# ========== CSVエクスポート ==========
st.subheader("エクスポート")
csv_all = df.sort_values("created_at").to_csv(index=False)
st.download_button(
    "全記事（基本列）CSVをダウンロード",
    csv_all,
    file_name="qiita_articles.csv",
    mime="text/csv",
)

csv_tag = tag_agg.sort_values("likes_sum", ascending=False).to_csv(index=False)
st.download_button(
    "タグ集計（合計・平均）CSVをダウンロード",
    csv_tag,
    file_name="qiita_tag_agg.csv",
    mime="text/csv",
)
