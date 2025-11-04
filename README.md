# 📊 Qiita データハック・ダッシュボード

**Qiita の全投稿データ（いいね・ストック・タグ）を可視化・分析できる Streamlit アプリです。**  
作者自身のアカウントに対して、申請不要の Personal Access Token だけで動作します。

---

## ✅ 主な機能

| 機能カテゴリ | 内容 |
|--------------|------|
| **記事分析** | ・全記事の「いいね」「ストック」数を一覧化<br>・ランキング（いいね順 / ストック順）<br>・累積曲線・月別推移グラフ |
| **タグ分析（全タグ対象）** | ・タグごとの記事数 / 合計いいね / 合計ストック<br>・タグ別ランキング & 棒グラフ<br>・タグ×月の推移（人気の変化） |
| **データハック系分析** | ・ストック > いいね の記事抽出（保存型の記事）<br>・いいね×ストック散布図<br>・バズ記事候補の可視化 |
| **CSVエクスポート** | ・記事一覧データ（created_at, title, likes, stocks…）<br>・タグ集計データ（likes_sum, stocks_sum…） |

---

## ✅ 画面イメージ

- 指標（記事数・全いいね・全ストック・最新投稿日）
- グラフ（いいね / ストックの推移・累積）
- ランキング表（上位記事）
- タグ別の棒グラフ・推移グラフ
- 散布図や「保存されやすい記事」抽出
- CSVダウンロード

---

## ✅ 必要なもの

| 必須 | 内容 |
|------|------|
| ✅ GitHubアカウント | アプリを公開する場合（Streamlit Community Cloudを使う） |
| ✅ Qiita Personal Access Token | スコープは `read_qiita` だけでOK |
| ✅ Python環境 or Streamlit Cloud | ローカル実行 / Webデプロイいずれも可 |

---

## ✅ 1. トークンの作成方法（Qiita）

1. Qiita にログイン  
2. 右上アイコン → **Settings（設定）**  
3. 左メニューから **Applications**  
4. **「アクセストークンを発行する」** をクリック  
5. `read_qiita` にチェック → 発行  
6. 表示されたトークンをコピー（後で使います）

---

## ✅ 2. ローカル実行する場合

```bash
git clone https://github.com/あなたのリポジトリ/qiita-dashboard.git
cd qiita-dashboard
pip install -r requirements.txt

# トークンを環境変数にセット（例）
export QIITA_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxx

streamlit run app.py
