# One Piece TCG Wholesale Catalog (Torelis)

Pokémon版カタログ (`index_2.html`) と同じ設計思想 — 「データはSQLite、
表示はビルドスクリプトが静的HTMLへ焼き込む」— を踏襲した、
One Piece TCG 卸カタログです。GitHub Pages でそのまま公開できます。

## ディレクトリ構成

```
optcg-catalog/
├── data/
│   └── one_piece_tcg.db        # ソース・オブ・トゥルース (SQLite: sets / cards)
├── build/
│   └── build_optcg.py          # DB → JSON → HTML埋め込み
├── template/
│   └── index_template.html     # 手編集するのはここ (CSS/JS/レイアウト)
├── docs/
│   └── index.html              # ビルド生成物。GitHub Pagesの公開ソースに指定する
└── README.md
```

## 使い方

### データを更新したいとき
1. `data/one_piece_tcg.db` を新しいスクレイピング結果で置き換える
2. `python3 build/build_optcg.py` を実行
3. `docs/index.html` が再生成されるので、通常のファイルとしてコミット&プッシュ

`docs/index.html` は生成物なので **直接編集しない**。デザインや挙動を変えたい
ときは `template/index_template.html` を編集してから再ビルドする。

### 見た目・機能を変えたいとき
`template/index_template.html` 内の `__SERIES_JSON__` / `__CARDS_JSON__` /
`__RARITY_ORDER_JSON__` / `__TOTAL_CARDS__` / `__TOTAL_SETS__` の5箇所が
ビルド時に置換されるプレースホルダー。それ以外のCSS/JS/HTMLは自由に編集してよい。

### 価格表・注文フォームの連携 (任意)
`template/index_template.html` 内の `GAS_URL` を、Cycle Connectで使っている
ものと同様の Google Apps Script Web App の URL に差し替えると、
Google Sheets からの動的価格取得と注文フォームのPOST送信が有効になる。
未設定の間は `DP`（レアリティ別デフォルト単価, USD）がそのまま使われる。

## GitHub運用フロー (提案)

1. **データ更新PR**: `data/one_piece_tcg.db` の差し替えのみを含む小さなPRにする
   （バイナリ差分になるため中身のレビューはしづらいが、粒度を小さく保つ）
2. **自動ビルド**: `.github/workflows/build.yml` を追加し、`data/**` または
   `template/**` の変更をトリガーに `python3 build/build_optcg.py` を実行、
   `docs/index.html` の差分を自動コミットする（下記サンプル参照）
3. **公開設定**: リポジトリの Settings → Pages で
   Source を `main` ブランチの `/docs` に設定する

### GitHub Actions サンプル (`.github/workflows/build.yml`)

```yaml
name: Build catalog
on:
  push:
    paths:
      - 'data/**'
      - 'template/**'
      - 'build/**'
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python3 build/build_optcg.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'chore: rebuild catalog'
          file_pattern: docs/index.html
```

## Pokémon版 (index_2.html) との主な違い

| 項目 | Pokémon版 | One Piece版 |
|---|---|---|
| フィルター軸 | レアリティのみ | レアリティ + カラー(6色/複合色) + タイプ(LEADER/CHARACTER/EVENT/STAGE) |
| カード画像 | なし | あり (JP公式サイトの画像URLを使用) |
| パラレル版 | 番号にサフィックス | 同様に番号サフィックス (`_p1` 等) + `★` マーク表示 |
| シリーズ分類 | XY/Sun&Moon/... 手動 | set_idの接頭辞 (OP/EB/ST/PRB/P) から自動分類 |
| 通貨 | USD/JPY/SGD/HKD | 上記 + PHP (フィリピン向け販路を考慮) |

## 既知の未対応・今後の拡張候補
- BOX(未開封box)商品タブは今回のデータに含まれないため未実装
  (Pokémon版の `BOXES` 相当の仕組み)
- 買取バナー生成ツール（Pokémon版の「管理者モード」）は移植していない
- カードの `ability` / `trigger` テキストはDBにあるが、ペイロード軽量化のため
  カタログ表示には含めていない（必要なら `build_optcg.py` の `entry` に追加するだけでよい）
