# zenn-orchestrator

## 役割

Zenn記事生成システムのLead orchestrator。checkpoint.jsonを読んでフェーズを判断し、
Layer1 → Material PDCA → Article PDCAの順に実行する。
各フェーズの詳細はzenn-material-pdca / zenn-article-pdcaサブスキルに委譲する。

## 起動フロー

```
1. output/checkpoint.json を読む
   - なければ FRESH_STATE (phase=layer1, next_action=run_strategist)
2. next_action に基づいてStage Dispatch Tableでルーティング
3. 各ステージ完了後にcheckpoint.jsonを更新
4. phase==done になったらreport.jsonを出力して終了
```

## Stage Dispatch Table

| next_action | 実行内容 | 完了後のcheckpoint更新 |
|-------------|---------|----------------------|
| `run_strategist` | Spawn strategist agent → `output/strategy.md` | `advance_layer1(cp, "strategist")` |
| `run_eval_designer` | Spawn eval_designer agent → `output/eval_criteria.md`（記事評価用・7軸）と `output/material_eval_criteria.md`（素材評価用・5軸: content_originality(0.25) / pain_coverage(0.20) / argument_novelty(0.20) / source_specificity(0.20) / thesis_coherence(0.15)、`## ベンチマーク` セクションも含める）の2ファイルを出力（入力に `human-bench/` を必ず含める） | `advance_layer1(cp, "eval_designer", requires_system_analysis=<flag>)` |
| `run_system_analyst` | Spawn system-analyst agent → `output/knowledge/system_analysis.md` | `advance_layer1(cp, "system_analyst")` |
| `run_topic_selector` | Invoke `zenn-topic-selection` skill → `output/topic.md` | `advance_topic_selection(cp)` |
| `run_experience_author` | Spawn `experience_author` agent → `output/knowledge/experience_log.md` | `advance_experience_authoring(cp)` |
| `run_material_iter` | Invoke `zenn-material-pdca` skill | `advance_material_iter(cp, score)` |
| `run_article_iter` | Invoke `zenn-article-pdca` skill | `advance_article_iter(cp, score)` |
| `material_fallback` | `iterations/` を `iterations_fallback_{count}/` にリネーム後、`trigger_material_fallback(cp)` | → next: `run_material_iter` |
| `consolidate` | Spawn consolidator agent → `iterations/{N}/article.md` 上書き → ArticleReviewer 再spawnでreview.json再生成 | `advance_after_consolidate(cp)` → next: `finalize` |
| `finalize` | Spawn finalizer agent → `output/final_article.md` | `mark_done(cp)` |
| `done` | stdout に report.json を出力 | END |

## Layer 1 実行（初回のみ）

```
next_action=run_strategist:
  Spawn: strategist agent
  入力: なし（ユーザー要求のみ）
  出力: output/strategy.md（先頭 YAML frontmatter に requires_system_analysis: true/false を含む）
  → checkpoint: advance_layer1(cp, "strategist") → next: run_eval_designer

next_action=run_eval_designer:
  Spawn: eval_designer agent
  入力: output/strategy.md, human-bench/index.yaml, human-bench/articles/（strategy.md の記事型に応じて3-4本を重点読解）
  出力:
    - output/eval_criteria.md（記事評価用・7軸・現行のまま）
    - output/material_eval_criteria.md（素材評価用・以下の5軸で生成）
      素材軸の定義:
        - content_originality (weight: 0.25): 他記事では読めない独自知見があるか
        - pain_coverage (weight: 0.20): 想定読者ペインを充足しているか
        - argument_novelty (weight: 0.20): 論点・主張が既存記事と差別化されているか
        - source_specificity (weight: 0.20): 具体的な数値・コマンド等の情報ソースがあるか
        - thesis_coherence (weight: 0.15): 骨子内の論点が一貫しているか
      素材軸には ## ベンチマーク セクションも記載すること（同じベンチ記事を参照）
  → strategy.md の frontmatter から requires_system_analysis を読む:
       import yaml; flag = yaml.safe_load(open("output/strategy.md").read().split("---")[1])["requires_system_analysis"]
     （または正規表現 ^requires_system_analysis:\s*(true|false) を使う）
  → checkpoint: advance_layer1(cp, "eval_designer", requires_system_analysis=flag)
  → flag=True なら next: run_system_analyst / False なら next: run_material_iter

next_action=run_system_analyst:
  Spawn: system-analyst agent
  入力: strategy.md, 調査対象ディレクトリ（strategy.mdで指定 or デフォルト=.claude/ 配下）
  出力: output/knowledge/system_analysis.md
  → checkpoint: advance_layer1(cp, "system_analyst") → next: run_topic_selector
  注意: このファイルは ThesisDesigner と Writer の入力として必ず渡すこと

next_action=run_topic_selector:
  Invoke: zenn-topic-selection skill
  入力: output/strategy.md, output/knowledge/system_analysis.md（存在する場合のみ）
  出力: output/topic.md, output/knowledge/trends.md
  → checkpoint: advance_topic_selection(cp) → next: run_experience_author
  注意: topic.md が出力されない場合のフォールバックは zenn-topic-selection 側で処理する。
        material PDCA は topic.md の有無に関わらず実行可能。

next_action=run_experience_author:
  Spawn: experience_author agent
  入力:
    - output/strategy.md
    - output/knowledge/trends.md（存在する場合のみ）
    - output/knowledge/system_analysis.md（存在する場合のみ）
    - output/topic.md（存在する場合のみ）
    - output/eval_criteria.md（品質センス参考用）
  出力: output/knowledge/experience_log.md（著者の生々しい経験の一次情報源）
  → checkpoint: advance_experience_authoring(cp) → next: run_material_iter
  注意:
    - このファイルは ThesisDesigner の入力として必ず渡すこと（最優先ソース）
    - experience_author 失敗時は 3 回 retry 後スキップし、experience_log.md 無しで
      Material PDCA に進む。ThesisDesigner 側は「存在する場合のみ」扱い
    - このフェーズは 1 回きり実行。iter >= 2 では再実行されない
```

## Material PDCA ループ制御

- **max_iter**: 5 / **threshold**: 0.85
- 各イテレーション後:

```python
# stagnation check
from stagnation_check import should_trigger_gap_alert
if should_trigger_gap_alert(score_history, threshold=0.85):
    from gap_alert import format_gap_alert
    alert_msg = format_gap_alert(current_score, 0.85, feedback_history)
    # → 次のzenn-material-pdca呼び出しのpromptに含める

# checkpoint更新
from checkpoint import advance_material_iter, write_checkpoint
cp = advance_material_iter(cp, score=current_score)
write_checkpoint(checkpoint_path, cp)
```

- `score >= 0.85` OR `material_iter == 5` → `phase=article_pdca, next=run_article_iter`
- それ以外 → `next=run_material_iter`（ループ継続）

## Article PDCA ループ制御

- **max_iter**: 10 / **threshold**: 0.80
- **MATERIAL_FALLBACK条件**: `article_iter >= 3 AND score < 0.70 AND material_fallback_count < 2`
- **Consolidator 経由 finalize 条件**: `article_iter >= 3 AND (score >= 0.80 OR iter == 10)`
- 各イテレーション後:

```python
from checkpoint import advance_article_iter, write_checkpoint
cp = advance_article_iter(cp, score=current_score)
write_checkpoint(checkpoint_path, cp)
# next_action は advance_article_iter が決定:
#   iter 1-2 で score >= 0.80                     → finalize（Consolidator skip）
#   iter >= 3 で score >= 0.80                    → consolidate
#   iter >= 3 & score < 0.70 & fallbacks < 2      → material_fallback
#   iter == 10                                    → consolidate
#   else                                          → run_article_iter
```

### consolidate ステージの処理

```python
import json
from metrics import (
    compute_article_metrics, check_hard_fail,
    fix_desu_masu, fix_consecutive_length, fix_code_ratio,
    apply_hard_fail, apply_major_penalty,
)
from checkpoint import advance_after_consolidate, write_checkpoint

# 1. Consolidator agent を spawn
#    入力: iterations/1..N/article.md, iterations/1..N/review.json, eval_criteria.md, style_memory/style_guide.md
#    出力: iterations/{N}/article.md（統合版で上書き）
#    ※ N = best_article_iter（完了時点で最高スコアを出した iter）
N = cp["best_article_iter"]
consolidated_path = f"output/iterations/{N}/article.md"

# 2. HARD FAIL チェック → 修正（zenn-article-pdca Step 2 と同じフロー）
#    ArticleReviewer を呼ぶ前に修正済み記事にしておく
article_text = open(consolidated_path, encoding="utf-8").read()
metrics = compute_article_metrics(article_text)
hf = check_hard_fail(metrics)
if hf.applied:
    reasons_str = " ".join(hf.reasons)
    if "code_ratio" in reasons_str:
        article_text = fix_code_ratio(article_text)
    if "desu_masu_ratio" in reasons_str:
        article_text = fix_desu_masu(article_text)
    if "consecutive_same_length" in reasons_str:
        article_text = fix_consecutive_length(article_text)
    with open(consolidated_path, "w", encoding="utf-8") as fh:
        fh.write(article_text)
    hf = check_hard_fail(compute_article_metrics(article_text))

# 3. 統合後（修正済み）記事を ArticleReviewer で再採点
#    入力: iterations/{N}/article.md（修正済み統合版）, eval_criteria.md
#    出力: iterations/{N}/review.json（上書き）

# 4. スコア確定（apply_hard_fail + apply_major_penalty）
with open(f"output/iterations/{N}/review.json", encoding="utf-8") as fh:
    review = json.load(fh)
raw_score = review["weighted_average"]
after_hf = apply_hard_fail(raw_score, hf)
major_count = sum(1 for fb in review["feedback"] if fb.get("severity") == "major")
final_score = apply_major_penalty(after_hf, major_count)

# 5. advance_after_consolidate で finalize へ（final_score を渡して best_article_score を更新）
cp = advance_after_consolidate(cp, final_score=final_score)
write_checkpoint(checkpoint_path, cp)
```

### MATERIAL_FALLBACK 時の挙動

`trigger_material_fallback()` 呼び出し前に、**既存の `output/iterations/` を `output/iterations_fallback_{count}/` にリネームしてアーカイブ**する:

```python
import os, shutil
fb_count = cp["material_fallback_count"] + 1  # インクリメント前の値 + 1
if os.path.isdir("output/iterations"):
    shutil.move("output/iterations", f"output/iterations_fallback_{fb_count}")
cp = trigger_material_fallback(cp)
write_checkpoint(checkpoint_path, cp)
```

- `material_iter=0` にリセット → 次の Material PDCA iter 1 で TrendResearcher + PainExtractor が **再実行**され、`trends.md` と `reader_pains.md` は上書きされる（意図的。最新トレンドと課題の再把握）
- `system_analysis.md` は **再生成しない**（コードベース不変のため）
- `best_article_iter` / `best_article_score` はコード側でリセット済み（新しい iter 群から最良を選び直す）

## セッション断絶回復

起動時に必ずcheckpoint.jsonを読む。`next_action`が途中フェーズを指していれば、
完了済みステップは再実行せずそのフェーズから再開する。

```python
from checkpoint import read_checkpoint, route_next_action
cp = read_checkpoint(Path("output/checkpoint.json"))
action = route_next_action(cp)
# → Stage Dispatch Tableに従って実行
```

## SubAgent spawn ルール

- **10KB rule**: 各agentはファイルに書き込み、親へはpath + 2-4文サマリーのみ返す
- **Layer 1**: StrategistとEvalDesignerはシリアル実行（Strategyが先）
- **Phase 0 (material iter 1)**: PainExtractorのみ（TrendResearcherはTopic Selectionで実行済み）

### Spawn テンプレート（シングル）

```
あなたは {agent_name} です。
タスク: {task_description}

入力ファイル:
{input_files_list}

出力先: {output_path}
指示: 上記ファイルに書き込み、tool_resultにはpathと2-4文のサマリーのみ返すこと。
```

## エラー時フォールバック

| 状況 | 対応 |
|------|------|
| agent spawn失敗 | 3回retry後スキップ。checkpointは更新せず再試行可能な状態を保つ |
| SystemAnalyst失敗 | `requires_system_analysis=false` に降格し `run_material_iter` へ進む（knowledge 無しで継続）。`system_analysis.md` が無いまま ThesisDesigner / Writer に渡すときは「このファイルは存在しない」ことを明示してスキップ指示を出す |
| ExperienceAuthor失敗 | 3回retry後、`advance_experience_authoring(cp)` で Material PDCA に進む（`experience_log.md` 無しで継続）。ThesisDesigner は「存在する場合のみ」扱いなので、ファイル不在でもループは回る。ただし生々しさ注入が効かないため品質が落ちる旨を report.json の `degraded_mode` フラグに記録 |
| Consolidator失敗 | Consolidator 前の `iterations/{N}/article.md` を保持したまま `advance_after_consolidate(cp)` で finalize へ進む（統合なしで元記事を最終出力） |
| スコア取得失敗 | 0.70をデフォルトスコアとして使用しループ継続 |
| checkpoint書き込み失敗 | ログ記録しメモリ上の状態で継続（次回起動時はfresh startになる） |
| zenn-material-pdca失敗 | 同イテレーションを再試行（max 2回）、失敗時は前回スコアで継続 |

## 完了時出力

```json
{
  "status": "done",
  "score": 0.82,
  "iterations": {
    "material": 3,
    "article": 5,
    "fallbacks": 0
  },
  "output_path": "output/final_article.md",
  "hard_fail_applied": false
}
```

stdoutに出力 **かつ** `output/report.json` に書き込む。
