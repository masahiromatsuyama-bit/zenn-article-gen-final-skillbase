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
| `knowledge/system_analysis.md` | SystemAnalyst の出力（`requires_system_analysis=true` の場合のみ存在） |
| `material_reviews/{iter-1}/review.json` | 前回レビュー（iter > 1 の場合のみ） |
| `fb_log.json` | 過去フィードバック履歴 |

## パス定数

```python
FB_LOG_PATH = "output/fb_log.json"
SYSTEM_ANALYSIS_PATH = "output/knowledge/system_analysis.md"  # 存在しない場合あり
THESIS_PATH = "output/thesis.md"
MATERIAL_THRESHOLD = 0.85  # gap_alert 判定に使用
```

---

## 実行手順

### iter == 1 の場合

**Step 1: PainExtractor を spawn**

TrendResearcher は Topic Selection フェーズで実行済み（`output/knowledge/trends.md` 生成済み）。
iter==1 では PainExtractor のみ spawn する。

- **PainExtractor**
  - 入力: `strategy.md`
  - 出力: `knowledge/reader_pains.md`
  - 返却: ファイルパス + 2〜4文サマリー

**Step 2: ThesisDesigner を spawn**

- 入力: `strategy.md`, `knowledge/trends.md`（存在する場合のみ。Topic Selectionが生成）, `knowledge/reader_pains.md`, `knowledge/experience_log.md`（存在する場合のみ。**著者の生々しい経験の一次情報源。最優先**）, `knowledge/system_analysis.md`（存在する場合のみ）, `output/topic.md`（存在する場合のみ。存在しない場合は strategy.md のスコープ情報を代わりに使用）
- 出力: `thesis.md`
- 返却: ファイルパス + 2〜4文サマリー

**Step 3: MaterialReviewer を spawn**

- 入力: `thesis.md`, `material_eval_criteria.md`（存在しない場合は `eval_criteria.md` を代替使用し、review.json に `"fallback_note": "material_eval_criteria.md not found, fallback to eval_criteria.md"` を追加すること）, `human-bench/articles/`（## ベンチマーク で参照されている3-4本）
- 採点方針（必須）:
  - 各軸のコメントには、参照したベンチマーク記事（タイトルを明記）と比較して何が優れているか・何が劣っているかを具体的に書くこと。
  - 生成物がベンチマーク記事と同等以下の品質の軸は、スコアを 0.75 上限とする。
  - ベンチマーク記事を明確に上回っている場合のみ 0.80 以上を許容する。
  - 「ベンチXXのYYに比べて〜が不足」という形式で feedback の text を書くこと。この形式を守れない feedback は minor ではなく major として扱うこと。
- 出力: `material_reviews/1/review.json`
  ```json
  {
    "axes": {"軸名": {"score": 0.xx, "comment": "..."}, ...},
    "weighted_average": 0.xx,
    "feedback": [{"axis": "...", "severity": "major|minor", "text": "..."}]
  }
  ```
- 返却: ファイルパス + 2〜4文サマリー

**Step 4: fb_log 更新**（iter == 1 でも実行）

下記 iter >= 2 の Step 5 と同じ処理を行う。

---

### iter >= 2 の場合

**Step 1: 前回レビュー読み込み + 前回 thesis のアーカイブ**

```python
import os, shutil, json

# 前回レビューを読む（フィードバック反映用）
with open(f"output/material_reviews/{iter-1}/review.json") as f:
    prev_review = json.load(f)
prev_feedback = prev_review["feedback"]

# 前回の thesis.md を thesis_history/ に退避（上書き前のスナップショット）
os.makedirs("output/thesis_history", exist_ok=True)
if os.path.exists(THESIS_PATH):
    shutil.copy2(THESIS_PATH, f"output/thesis_history/{iter-1}.md")
```

**Step 2: gap_alert チェック**

```python
import os, json
from stagnation_check import should_trigger_gap_alert
from gap_alert import format_gap_alert
from fb_log import load_fb_log

# (1) material_reviews/ からスコア履歴を構築
score_history = []
for i in range(1, iter):
    p = f"output/material_reviews/{i}/review.json"
    if os.path.exists(p):
        with open(p) as f:
            r = json.load(f)
            score_history.append({"score": r["weighted_average"]})

# (2) 停滞判定（material 閾値 = 0.85）
gap_alert_text = None
if should_trigger_gap_alert(score_history, MATERIAL_THRESHOLD):
    # (3) feedback_history は fb_log の material phase エントリから構築
    fb_entries = load_fb_log(FB_LOG_PATH)
    feedback_history = [
        {"description": e.description}
        for e in fb_entries if e.phase == "material"
    ]
    current_score = score_history[-1]["score"]
    gap_alert_text = format_gap_alert(current_score, MATERIAL_THRESHOLD, feedback_history)
```

**Step 3: ThesisDesigner を spawn**

- 入力:
  - `strategy.md`
  - `knowledge/trends.md`（存在する場合のみ）, `knowledge/reader_pains.md`
  - `knowledge/experience_log.md`（存在する場合のみ。**著者の生々しい経験の一次情報源。最優先**）
  - `knowledge/system_analysis.md`（存在する場合のみ）
  - `output/topic.md`（存在する場合のみ。存在しない場合は strategy.md のスコープ情報を代わりに使用）
  - `thesis_history/{iter-1}.md`（前回 thesis スナップショット）
  - 前回レビューの `feedback`（Step 1 で取得済み）
  - `gap_alert_text`（存在する場合はプロンプトに埋め込む）
- 出力: `thesis.md`（上書き）
- 返却: ファイルパス + 2〜4文サマリー

**Step 4: MaterialReviewer を spawn**

- 入力: 更新された `thesis.md`, `material_eval_criteria.md`（存在しない場合は `eval_criteria.md` を代替使用し、review.json に `"fallback_note": "material_eval_criteria.md not found, fallback to eval_criteria.md"` を追加すること）, `human-bench/articles/`（同上）
- 採点方針（必須）:
  - 各軸のコメントには、参照したベンチマーク記事（タイトルを明記）と比較して何が優れているか・何が劣っているかを具体的に書くこと。
  - 生成物がベンチマーク記事と同等以下の品質の軸は、スコアを 0.75 上限とする。
  - ベンチマーク記事を明確に上回っている場合のみ 0.80 以上を許容する。
  - 「ベンチXXのYYに比べて〜が不足」という形式で feedback の text を書くこと。この形式を守れない feedback は minor ではなく major として扱うこと。
- 出力: `material_reviews/{iter}/review.json`
- 返却: ファイルパス + 2〜4文サマリー

**Step 5: fb_log 更新**

```python
from fb_log import load_fb_log, record_fb, append_fb_diff
import json

# (1) 前回エントリを読む（初回は空）
prev_entries = load_fb_log(FB_LOG_PATH)

# (2) review.json の feedback を FBEntry に変換
with open(f"output/material_reviews/{iter}/review.json") as f:
    review = json.load(f)
new_entries = record_fb(
    entries=prev_entries,
    new_feedbacks=review["feedback"],   # [{axis, severity, text}, ...]
    iteration=iter,
    phase="material",
)

# (3) diff を計算して fb_log に追記
diff = append_fb_diff(
    path=FB_LOG_PATH,
    entries=new_entries,
    prev_entries=prev_entries,
    iteration=iter,
    phase="material",
)
```

---

## スコア計算

```python
from metrics import apply_major_penalty

raw_score = review["weighted_average"]
major_count = sum(1 for f in review["feedback"] if f.get("severity") == "major")
final_score = apply_major_penalty(raw_score, major_count)
# major_count >= 1: score は 0.78 を超えない → material threshold 0.85 を突破できない
# これにより major feedback が残っているうちは必ず次イテに進む
```

## 返り値フォーマット

```json
{
  "score": 0.xx,
  "raw_score": 0.xx,
  "major_count": N,
  "feedback": [{"axis":"...","severity":"...","text":"..."}, ...],
  "iter": N,
  "output_path": "material_reviews/N/review.json"
}
```

`score` は `apply_major_penalty(raw_score, major_count)` の結果を使う。

---

## SubAgent spawn ルール

- **10KB rule**: 各 agent はファイルに書き込み、返却はファイルパス + 2〜4文サマリーのみ。大量テキストを返さない。
- **並列 spawn は行わない**: iter 1 では PainExtractor のみ（TrendResearcher は Topic Selection 済み）。ThesisDesigner 以降はシリアル実行。
- **iter 2 以降はシリアル**: 前回フィードバックの依存関係があるため。
