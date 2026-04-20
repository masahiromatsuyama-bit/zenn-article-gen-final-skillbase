# zenn-article-pdca — INSTRUCTIONS

## 役割

1回分のArticle PDCAイテレーションを実行するサブスキル。`zenn-orchestrator` からのみ呼び出される。Finalizer の呼び出しとチェックポイント管理はオーケストレーター側が行う。本スキルは指定された `iter` で1回だけ実行し、結果をJSONで返す。

---

## 入力

| 項目 | 説明 |
|------|------|
| `iter` | 現在のイテレーション番号（1〜10） |
| `strategy.md` | Layer 1 で生成された戦略 |
| `eval_criteria.md` | Layer 1 で生成された評価基準 |
| `thesis.md` | 最新の素材（Material PDCA 出力） |
| `style_memory/style_guide.md` | スタイルガイド（iter 1 では存在しない場合あり） |
| `agent_memory/memory.json` | エージェントメモリ（iter 1 では存在しない場合あり） |
| `fb_log.json` | 過去フィードバック履歴 |
| `iterations/{iter-1}/article.md` | 前回記事（iter > 1 の場合のみ） |

---

## 実行手順

### Step 1: Writer を spawn

- 入力:
  - `strategy.md`
  - `thesis.md`
  - `style_memory/style_guide.md`（存在する場合）
  - `iterations/{iter-1}/article.md`（iter > 1 の場合）
  - gap_alert テキスト（後述、存在する場合はプロンプトに含める）
- 出力: `iterations/{iter}/article.md`
- 返却: ファイルパス + 2〜4文サマリー

gap_alert チェック（Writer spawn 前に実施）:

```python
from stagnation_check import should_trigger_gap_alert
from gap_alert import format_gap_alert
from fb_log import load_fb_log

fb_log = load_fb_log()
alert = should_trigger_gap_alert(fb_log, phase="article")
gap_alert_text = format_gap_alert(alert) if alert else None
```

---

### Step 2: HARD FAIL チェック

```python
from metrics import compute_article_metrics, check_hard_fail, fix_desu_masu, fix_consecutive_length, apply_hard_fail

article_text = open(f"iterations/{iter}/article.md").read()
metrics = compute_article_metrics(article_text)
hf = check_hard_fail(metrics)
```

HARD FAIL が発生した場合:

```python
if hf.get("desu_masu_ratio"):
    article_text = fix_desu_masu(article_text)
if hf.get("consecutive_length"):
    article_text = fix_consecutive_length(article_text)

# 修正後に再チェック
metrics = compute_article_metrics(article_text)
hf = check_hard_fail(metrics)

# 修正後テキストを上書き保存
open(f"iterations/{iter}/article.md", "w").write(article_text)
```

`hard_fail_applied = True` として記録する（修正の有無に関わらず、HARD FAIL 検出時は True）。

---

### Step 3: StyleGuideUpdater を spawn

- 入力: `iterations/{iter}/article.md`（修正済み）, `style_memory/style_guide.md`（前回版）
- 出力: `style_memory/style_guide.md`（更新・上書き）
- 返却: ファイルパス + 2〜4文サマリー

---

### Step 4: ArticleReviewer を spawn

- 入力: `iterations/{iter}/article.md`, `eval_criteria.md`, `agent_memory/memory.json`（存在する場合）
- 出力: `iterations/{iter}/review.json`
  ```json
  {
    "axes": {"軸名": スコア, ...},
    "weighted_average": 0.xx,
    "feedback": ["...", "..."]
  }
  ```
- 返却: ファイルパス + 2〜4文サマリー

---

### Step 5: スコア計算

```python
review = json.load(open(f"iterations/{iter}/review.json"))
raw_score = review["weighted_average"]
final_score = apply_hard_fail(raw_score, hf)
```

`apply_hard_fail` は HARD FAIL の重篤度に応じてスコアにペナルティを適用する。

---

### Step 6: Consolidator（iter == 5 のみ）

iter が 5 の場合のみ、通常フローの後に Consolidator を追加 spawn する。

- 入力: `iterations/1/` 〜 `iterations/5/` の全 `article.md` と `review.json`
- 出力: `iterations/5/article.md`（統合版で上書き）
- 統合後: 上書きされた `iterations/5/article.md` を再度 ArticleReviewer で評価し `final_score` を再計算する

---

### Step 7: agent_memory.json 更新

```python
import json

memory = {
    "score_by_axis": review["axes"],
    "death_patterns": [f for f in review["feedback"] if "過多" in f or "NG" in f]
}
json.dump(memory, open("agent_memory/memory.json", "w"), ensure_ascii=False, indent=2)
```

既存の `memory.json` が存在する場合はマージ（`death_patterns` はリストに追記、重複除去）する。

---

### Step 8: fb_log 更新

```python
from fb_log import append_fb_diff

append_fb_diff(
    iter=iter,
    phase="article",
    score=final_score,
    feedback=review["feedback"]
)
```

---

## 返り値フォーマット

```json
{
  "score": 0.xx,
  "feedback": ["...", "..."],
  "iter": N,
  "hard_fail_applied": true,
  "output_path": "iterations/N/article.md"
}
```

---

## SubAgent spawn ルール

- **10KB rule**: 各 agent はファイルに書き込み、返却はファイルパス + 2〜4文サマリーのみ。大量テキストを返さない。
- **シリアル実行**: Writer → StyleGuideUpdater → ArticleReviewer は依存関係があるため、必ずシリアル実行。
- **Consolidator は iter 5 のみ**: ArticleReviewer 完了後に追加で spawn し、スコアを再計算して最終値とする。
