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
| `knowledge/system_analysis.md` | SystemAnalyst 出力（存在する場合のみ） |
| `style_memory/style_guide.md` | スタイルガイド（iter 1 では存在しない場合あり） |
| `agent_memory/memory.json` | エージェントメモリ（iter 1 では存在しない場合あり） |
| `fb_log.json` | 過去フィードバック履歴 |
| `iterations/{iter-1}/article.md` | 前回記事（iter > 1 の場合のみ） |

## パス定数

```python
FB_LOG_PATH = "output/fb_log.json"
SYSTEM_ANALYSIS_PATH = "output/knowledge/system_analysis.md"  # 存在しない場合あり
ARTICLE_THRESHOLD = 0.80  # gap_alert 判定に使用
```

---

## 実行手順

### Step 0: gap_alert チェック（Writer spawn 前に実施）

```python
import os, json
from stagnation_check import should_trigger_gap_alert
from gap_alert import format_gap_alert
from fb_log import load_fb_log

# (1) iterations/ からスコア履歴を構築
score_history = []
for i in range(1, iter):
    p = f"output/iterations/{i}/review.json"
    if os.path.exists(p):
        with open(p) as f:
            r = json.load(f)
            score_history.append({"score": r["weighted_average"]})

# (2) 停滞判定（article 閾値 = 0.80）
gap_alert_text = None
if should_trigger_gap_alert(score_history, ARTICLE_THRESHOLD):
    fb_entries = load_fb_log(FB_LOG_PATH)
    feedback_history = [
        {"description": e.description}
        for e in fb_entries if e.phase == "article"
    ]
    current_score = score_history[-1]["score"]
    gap_alert_text = format_gap_alert(current_score, ARTICLE_THRESHOLD, feedback_history)
```

### Step 1: Writer を spawn

- 入力:
  - `strategy.md`
  - `thesis.md`
  - `knowledge/system_analysis.md`（存在する場合のみ）
  - `style_memory/style_guide.md`（存在する場合）
  - `iterations/{iter-1}/article.md` と `iterations/{iter-1}/review.json`（iter > 1 の場合）
  - `gap_alert_text`（存在する場合はプロンプトに埋め込む）
- 出力: `iterations/{iter}/article.md`
- 返却: ファイルパス + 2〜4文サマリー

---

### Step 2: HARD FAIL チェック

```python
from metrics import (
    compute_article_metrics, check_hard_fail,
    fix_desu_masu, fix_consecutive_length, fix_code_ratio,
    apply_hard_fail,
)

article_path = f"output/iterations/{iter}/article.md"
article_text = open(article_path).read()
metrics = compute_article_metrics(article_text)
hf = check_hard_fail(metrics)
hard_fail_applied = hf.applied  # 初回検出の履歴を記録（修正成否に関わらず True）

if hf.applied:
    # hf は HardFailResult(applied, cap, reasons) dataclass。
    # reasons は文字列リスト。該当理由を部分一致で判定する。
    reasons_str = " ".join(hf.reasons)
    if "code_ratio" in reasons_str:
        article_text = fix_code_ratio(article_text)
    if "desu_masu_ratio" in reasons_str:
        article_text = fix_desu_masu(article_text)
    if "consecutive_same_length" in reasons_str:
        article_text = fix_consecutive_length(article_text)

    # 修正後に再チェック + 上書き保存
    open(article_path, "w").write(article_text)
    metrics = compute_article_metrics(article_text)
    hf = check_hard_fail(metrics)
```

**HARD FAIL スコア扱いのルール**:
- 初回 `check_hard_fail()` で `hf.applied=True` でも、`fix_*` 関数適用後の再チェックで `hf.applied=False` になれば cap は適用しない（`apply_hard_fail` が raw_score を返す）
- 修正試行後もまだ `hf.applied=True` なら cap を適用
- `hard_fail_applied` フラグは「検出した」事実を True として report.json に記録（修正成否に関わらず）

---

### Step 3: StyleGuideUpdater を spawn

- 入力: `iterations/{iter}/article.md`（修正済み）, `style_memory/style_guide.md`（前回版）
- 出力: `style_memory/style_guide.md`（更新・上書き）
- 返却: ファイルパス + 2〜4文サマリー

---

### Step 4: ArticleReviewer を spawn

- 入力: `iterations/{iter}/article.md`, `eval_criteria.md`, `agent_memory/memory.json`（存在する場合）, `human-bench/articles/`（eval_criteria.md ## ベンチマーク で参照されている3-4本）
- 出力: `iterations/{iter}/review.json`
  ```json
  {
    "axes": {"軸名": {"score": 0.xx, "comment": "..."}, ...},
    "weighted_average": 0.xx,
    "feedback": [{"axis":"...","severity":"major|minor","text":"..."}, ...]
  }
  ```
- 返却: ファイルパス + 2〜4文サマリー

---

### Step 5: スコア計算

```python
from metrics import apply_hard_fail, apply_major_penalty
import json

with open(f"output/iterations/{iter}/review.json") as f:
    review = json.load(f)
raw_score = review["weighted_average"]

# (1) HARD FAIL cap（修正後でも残っている場合のみ適用）
after_hf = apply_hard_fail(raw_score, hf)

# (2) major feedback ペナルティ
major_count = sum(1 for f in review["feedback"] if f.get("severity") == "major")
final_score = apply_major_penalty(after_hf, major_count)

# apply_major_penalty の cap は:
#   major=1: 0.84  / major=2: 0.79  / major=3+: 0.70
# これにより major feedback が 2件以上残っているうちは article threshold 0.80 を突破できない
```

---

### Step 6: agent_memory.json 更新

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

### Step 7: fb_log 更新

```python
from fb_log import load_fb_log, record_fb, append_fb_diff

# (1) 前回エントリを読む
prev_entries = load_fb_log(FB_LOG_PATH)

# (2) review.json の feedback を FBEntry に変換
new_entries = record_fb(
    entries=prev_entries,
    new_feedbacks=review["feedback"],
    iteration=iter,
    phase="article",
)

# (3) diff を計算して fb_log に追記
diff = append_fb_diff(
    path=FB_LOG_PATH,
    entries=new_entries,
    prev_entries=prev_entries,
    iteration=iter,
    phase="article",
)
```

---

## Consolidator について

Consolidator 起動はこのスキル内では行わない。
`advance_article_iter(cp, final_score)` が `next_action="consolidate"` を返した時、
**orchestrator 側が別ステージとして起動する**（`zenn-orchestrator/INSTRUCTIONS.md` の consolidate ステージ参照）。

旧仕様の「iter == 5 のみ」は廃止。新仕様では `iter >= 3 AND (score >= 0.80 OR iter == 10)` で起動される。

---

## 返り値フォーマット

```json
{
  "score": 0.xx,
  "raw_score": 0.xx,
  "major_count": N,
  "feedback": [{"axis":"...","severity":"...","text":"..."}, ...],
  "iter": N,
  "hard_fail_applied": true,
  "output_path": "iterations/N/article.md"
}
```

---

## SubAgent spawn ルール

- **10KB rule**: 各 agent はファイルに書き込み、返却はファイルパス + 2〜4文サマリーのみ。大量テキストを返さない。
- **シリアル実行**: Writer → StyleGuideUpdater → ArticleReviewer は依存関係があるため、必ずシリアル実行。
- **Consolidator は呼ばない**: orchestrator が consolidate ステージで別途起動する。
