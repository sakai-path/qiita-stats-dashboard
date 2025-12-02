# Qiita データハック・ダッシュボード

Qiita API を利用して、自分の投稿データ（いいね・ストック・views・タグなど）を可視化する Streamlit アプリです。  
Personal Access Token があれば、自分の Qiita アカウントに対してのみ利用でき、追加申請は不要です。

このアプリでは以下のような分析ができます。

- 投稿数、いいね、ストック、views などの合計・平均
- 記事一覧の整理（投稿日順・リンク付き）
- いいね・ストック・views のランキング
- 月別推移（時系列グラフ）
- タグごとの反応の違い
- バズ傾向やストックされやすい記事の抽出
- CSV エクスポートによる二次分析

## 機能一覧

### 1. 投稿データの集計
- 記事数
- 合計いいね
- 合計ストック
- 合計 views
- 各指標の平均（1記事あたり）

### 2. 記事一覧
- 投稿日で並べ替え可能
- 記事タイトルは Qiita へのリンク
- いいね、ストック、views を一覧表示

### 3. ランキング
- いいね数ランキング
- ストック数ランキング
- views ランキング
- 棒グラフによる比較

### 4. 時系列分析
- 月別のいいね・ストック推移
- 累積カーブ

### 5. タグ分析
- タグ別の集計（記事数、合計値、平均値）
- タグの棒グラフ
- タグ × 月の推移

### 6. データハック用ビュー
- ストック > いいね の記事抽出
- バズ傾向の記事抽出
- いいね × ストック の散布図

### 7. CSV エクスポート
- 記事一覧 CSV
- タグ集計 CSV


## 必要なもの

| 種類 | 説明 |
|------|------|
| Qiita Personal Access Token | スコープ `read_qiita` のみで利用可能 |
| Python 3.9+ | ローカル実行用 |
| Streamlit Cloud（任意） | Web公開用 |

## Qiita Personal Access Token の作成方法

1. Qiita にログイン  
2. 右上アイコン → 「設定」  
3. 左メニュー → 「アプリケーション」  
4. 「個人用アクセストークン」 → 「新しくトークンを発行する」  
5. スコープは `read_qiita` のみチェック  
6. 発行されたトークンをコピーしてアプリに設定する

※ トークンは GitHub などに公開しないよう注意してください。

## ローカルでの実行方法

### 1. クローン

```bash
git clone https://github.com/your-repo/qiita-data-hack-dashboard.git
cd qiita-data-hack-dashboard
````

### 2. パッケージインストール

```bash
pip install -r requirements.txt
```

### 3. トークン設定

```bash
export QIITA_TOKEN=your_token_here
streamlit run app.py
```

Windows の場合：

```powershell
setx QIITA_TOKEN "your_token_here"
streamlit run app.py
```

## Streamlit Cloud で公開する場合

1. GitHub リポジトリを用意
2. Streamlit Cloud で「New app」を作成
3. Secrets に以下のように設定

```
QIITA_TOKEN = "your_token_here"
```

4. Deploy すれば公開完了

## ファイル構成

```
├── app.py              # メインアプリ
├── requirements.txt    # 依存パッケージ
└── README.md           # このファイル
```


## 注意点

* 取得できるデータは認証ユーザー（自分）の記事のみです
* Qiita API のレート制限は「認証済み 1000回/時」
* トークンは Secrets や環境変数で安全に扱ってください


