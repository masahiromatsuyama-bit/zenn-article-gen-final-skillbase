# zenn-material-pdca — INSTRUCTIONS

## 役割

1回分のMaterial PDCAイテレーションを実行するサブスキル。`zenn-orchestrator` からのみ呼び出される。チェックポイント管理はオーケストレーター側が行う。本スキルは指定された `iter` で1回だけ実行し、結果をJSONで返す。

---

## 入力

| 項目 | 説明 |
|------|------|
| `iter` | 現在のイテレーション番号（1〜5） |
| `strategy.md` | Layer 1 で生成された戦略 |
| `eval_criteria.md` | Layer 1 で生成された評価基準 |
| `material_reviews/{iter-1}/review.json` | 前回レビュー（iter > 1 の場合のみ） |
| `fb_log.json` | 過去フィードバック履歴 |

---

## 実行手順

### iter == 1 の場合

**Step 1: 並列 spawn（TrendResearcher + PainExtractor）**

TrendResearcher と PainExtractor は互いに独立しているため、同時 spawn する。

- **TrendResearcher**
  - 入力: `strategy.md`
  - 出力: `knowledge/trends.md`
  - 返却: ファイルパス + 2〜4文サマリー

- **PainExtractor**
  - 入力: `strategy.md`
  - 出力: `knowledge/reader_pains.md`
  - 返却: ファイルパス + 2〜4文サマリー

**Step 2: ThesisDesigner を spawn**

- 入力: `knowledge/trends.md`, `knowledge/reader_pains.md`
- 出力: `thesis.md`
- 返却: ファイルパス + 2〜4文サマリー

**Step 3: MaterialReviewer を spawn**

- 入力: `thesis.md`, `eval_criteria.md`
- 出力: `material_reviews/1/review.json`
  ```json
  {
    "axes": {"軸名": スコア, ...},
    "weighted_average": 0.xx,
    "feedback": ["..."]
  }
  ```
- 返却: ファイルパス + 2〜4文サマリー

---

### iter >= 2 の場合

**Step 1: 前回レビューを読み込む**

`material_reviews/{iter-1}/review.json` を読み込み、`feedback` フィールドを取得する。

**Step 2: gap_alert チェック**

```python
from stagnation_check import should_trigger_gap_alert
from gap_alert import format_gap_alert
from fb_log import load_fb_log

fb_log = load_fb_log()
alert = should_trigger_gap_alert(fb_log, phase="material")
gap_alert_text = format_gap_alert(alert) if alert else None
```

**Step 3: ThesisDesigner を spawn**

- 入力: 前回 `thesis.md`, 前回レビューの `feedback`, gap_alert（存在する場合はプロンプトに含める）
- 出力: `thesis.md`（上書き）
- 返却: ファイルパス + 2〜4文サマリー

**Step 4: MaterialReviewer を spawn**

- 入力: 更新された `thesis.md`, `eval_criteria.md`
- 出力: `material_reviews/{iter}/review.json`
- 返却: ファイルパス + 2〜4文サマリー

---

## 返り値フォーマット

```json
{
  "score": 0.xx,
  "feedback": ["...", "..."],
  "iter": N,
  "output_path": "material_reviews/N/review.json"
}
```

`score` は `review.json` の `weighted_average` をそのまま使用する。

---

## SubAgent spawn ルール

- **10KB rule**: 各 agent はファイルに書き込み、返却はファイルパス + 2〜4文サマリーのみ。大量テキストを返さない。
- **並列 spawn は iter 1 のみ**: TrendResearcher と PainExtractor のみ並列。ThesisDesigner 以降はシリアル実行。
- **iter 2 以降はシリアル**: 前回フィードバックの依存関係があるため。
