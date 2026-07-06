#!/usr/bin/env python3
"""
build_optcg.py
----------------
One Piece TCG 卸カタログ (Torelis) のビルドスクリプト。

data/one_piece_tcg.db (SQLite: sets / cards) を読み込み、
template/index_template.html 内のプレースホルダーに
SERIES / CARDS / rarity順序 などのJSONを埋め込んで
docs/index.html (GitHub Pages公開用) を生成する。

使い方:
    python3 build/build_optcg.py
    python3 build/build_optcg.py --db data/one_piece_tcg.db --template template/index_template.html --out docs/index.html

データを更新したいときは data/one_piece_tcg.db を差し替えて
このスクリプトを再実行するだけでよい。docs/index.html は
生成物なので手編集しない（テンプレート側を編集する）。
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# レアリティの正規順序（フィルターUIやバッジ色分けの並び順に使う）
# ---------------------------------------------------------------------------
RARITY_ORDER = ["L", "C", "UC", "R", "SR", "SEC", "TR", "SP CARD", "P"]

# シリーズ分類ルール: set_id の接頭辞 -> (表示名, ソート優先度)
SERIES_RULES = [
    (re.compile(r"^OP\d+$"), "ブースターパック (OP)", 0),
    (re.compile(r"^EB\d+$"), "エクストラブースター (EB)", 1),
    (re.compile(r"^ST\d+$"), "スタートデッキ (ST)", 2),
    (re.compile(r"^PRB\d*$"), "プレミアムブースター", 3),
    (re.compile(r"^P$"), "プロモカード", 4),
]

# 弾の日本語タイトル（公式商品名）。DB側にはJP名の列が無いため手動マッピング。
# 新しい弾を追加するときはここに1行足すだけでよい。
JP_NAMES = {
    "OP01": "ROMANCE DAWN",
    "OP02": "頂上決戦",
    "OP03": "強大な敵",
    "OP04": "謀略の王国",
    "OP05": "新時代の主役",
    "OP06": "双璧の覇者",
    "OP07": "500年後の未来",
    "OP08": "二つの伝説",
    "OP09": "新たなる皇帝",
    "OP10": "王族の血統",
    "OP11": "神速の拳",
    "OP12": "師弟の絆",
    "EB01": "メモリアルコレクション",
    "EB02": "Anime 25th collection",
    "PRB01": "ONE PIECE CARD THE BEST",
    "P": "プロモカード（FILM RED プロモーションカードセット 他）",
    "ST01": "麦わらの一味",
    "ST02": "最悪の世代",
    "ST03": "王下七武海",
    "ST04": "百獣海賊団",
    "ST05": "FILM edition",
    "ST06": "海軍",
    "ST07": "ビッグ・マム海賊団",
    "ST08": "Side モンキー・D・ルフィ",
    "ST09": "Side ヤマト",
    "ST10": "\u201c三船長\u201d集結",
    "ST11": "Side ウタ",
    "ST12": "ゾロ&サンジ",
    "ST13": "3兄弟の絆",
    "ST14": "3D2Y",
    "ST15": "赤 エドワード・ニューゲート",
    "ST16": "緑 ウタ",
    "ST17": "青 ドンキホーテ・ドフラミンゴ",
    "ST18": "紫 モンキー・D・ルフィ",
    "ST19": "黒 スモーカー",
    "ST20": "黄 シャーロット・カタクリ",
    "ST21": "ギア5",
    "ST23": "赤 シャンクス",
    "ST24": "緑 ジュエリー・ボニー",
    "ST25": "青 バギー",
    "ST26": "紫/黒 モンキー・D・ルフィ",
    "ST27": "黒 マーシャル・D・ティーチ",
    "ST28": "緑/黄 ヤマト",
}


def classify_series(set_id: str):
    for pattern, label, priority in SERIES_RULES:
        if pattern.match(set_id):
            return label, priority
    return "Other", 99


def natural_set_key(set_id: str):
    """OP1, OP02, ST10 などを数値で正しく並べ替えるためのキー"""
    m = re.match(r"^([A-Za-z]+)(\d+)$", set_id)
    if m:
        return (m.group(1), int(m.group(2)))
    return (set_id, 0)


def sanitize_rarity_class(rarity: str) -> str:
    """CSSクラス名に使える形へ (例: 'SP CARD' -> 'SP-CARD')"""
    return re.sub(r"\s+", "-", rarity.strip())


def load_data(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT set_id, name, total_cards FROM sets")
    sets_rows = {r["set_id"]: dict(r) for r in cur.fetchall()}

    cur.execute(
        """
        SELECT set_id, number, is_parallel, name, rarity, type, cost, power,
               counter, color, family, attribute_name,
               image_small, image_large, image_url_jp
        FROM cards
        ORDER BY set_id, number
        """
    )
    card_rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return sets_rows, card_rows


def build_series_and_cards(sets_rows, card_rows):
    # setごとにカードをまとめる
    cards_by_set = {}
    rarities_by_set = {}
    colors_by_set = {}
    types_by_set = {}

    for row in card_rows:
        sid = row["set_id"]
        cards_by_set.setdefault(sid, [])
        rarities_by_set.setdefault(sid, set())
        colors_by_set.setdefault(sid, set())
        types_by_set.setdefault(sid, set())

        rarity = (row["rarity"] or "").strip()
        color = (row["color"] or "").strip()
        ctype = (row["type"] or "").strip()

        # 画像: JP版サイトの画像を優先、なければ英語版を使用
        img = row["image_url_jp"] or row["image_large"] or row["image_small"] or ""

        entry = {
            "n": row["number"],
            "name": row["name"],
            "r": rarity,
            "c": color,
            "t": ctype,
            "cost": row["cost"],
            "power": row["power"],
            "counter": row["counter"] if row["counter"] not in (None, "-") else None,
            "family": row["family"],
            "img": img,
            "p": bool(row["is_parallel"]),
        }
        cards_by_set[sid].append(entry)
        if rarity:
            rarities_by_set[sid].add(rarity)
        if color:
            colors_by_set[sid].add(color)
        if ctype:
            types_by_set[sid].add(ctype)

    # シリーズごとにセットをグルーピング
    series_map = {}
    for sid, meta in sets_rows.items():
        label, priority = classify_series(sid)
        series_map.setdefault(label, {"priority": priority, "sets": []})
        rarities_sorted = sorted(
            rarities_by_set.get(sid, []),
            key=lambda r: RARITY_ORDER.index(r) if r in RARITY_ORDER else 999,
        )
        series_map[label]["sets"].append(
            {
                "id": sid,
                "name": JP_NAMES.get(sid, meta["name"]),  # 表示名は日本語優先
                "name_en": meta["name"],                  # 英語の正式名も保持（検索・参照用）
                "count": meta["total_cards"],
                "rarities": rarities_sorted,
                "colors": sorted(colors_by_set.get(sid, [])),
                "types": sorted(types_by_set.get(sid, [])),
            }
        )

    series_list = []
    for label, info in sorted(series_map.items(), key=lambda kv: kv[1]["priority"]):
        sets_sorted = sorted(info["sets"], key=lambda s: natural_set_key(s["id"]))
        series_list.append({"key": label, "sets": sets_sorted})

    return series_list, cards_by_set


def render(template_path: Path, out_path: Path, series_json, cards_json,
           total_cards, total_sets, rarity_order_json):
    html = template_path.read_text(encoding="utf-8")

    replacements = {
        "__SERIES_JSON__": series_json,
        "__CARDS_JSON__": cards_json,
        "__RARITY_ORDER_JSON__": rarity_order_json,
        "__TOTAL_CARDS__": str(total_cards),
        "__TOTAL_SETS__": str(total_sets),
    }
    for placeholder, value in replacements.items():
        if placeholder not in html:
            raise RuntimeError(
                f"テンプレートにプレースホルダー {placeholder} が見つかりません。"
                f" template/index_template.html を確認してください。"
            )
        html = html.replace(placeholder, value)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent.parent
    parser.add_argument("--db", default=str(here / "data" / "one_piece_tcg.db"))
    parser.add_argument("--template", default=str(here / "template" / "index_template.html"))
    parser.add_argument("--out", default=str(here / "docs" / "index.html"))
    args = parser.parse_args()

    db_path = Path(args.db)
    template_path = Path(args.template)
    out_path = Path(args.out)

    sets_rows, card_rows = load_data(db_path)
    series_list, cards_by_set = build_series_and_cards(sets_rows, card_rows)

    series_json = json.dumps(series_list, ensure_ascii=False, separators=(",", ":"))
    cards_json = json.dumps(cards_by_set, ensure_ascii=False, separators=(",", ":"))
    rarity_order_json = json.dumps(RARITY_ORDER, ensure_ascii=False)

    total_cards = len(card_rows)
    total_sets = len(sets_rows)

    render(template_path, out_path, series_json, cards_json,
           total_cards, total_sets, rarity_order_json)

    print(f"[OK] {out_path} を生成しました。")
    print(f"     sets={total_sets}  cards={total_cards}")


if __name__ == "__main__":
    main()
