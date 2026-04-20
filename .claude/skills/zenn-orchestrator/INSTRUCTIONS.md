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
| `run_strategist` | Spawn strategist agent → `output/strategy.md` | `advance_layer1("strategist")` |
| `run_eval_designer` | Spawn eval_designer agent → `output/eval_criteria.md` | `advance_layer1("eval_designer")` |
| `run_material_iter` | Invoke `zenn-material-pdca` skill | `advance_material_iter(score)` |
| `run_article_iter` | Invoke `zenn-article-pdca` skill | `advance_article_iter(score)` |
| `material_fallback` | `trigger_material_fallback()` | → next: `run_material_iter` |
| `finalize` | Spawn finalizer agent → `output/final_article.md` | `mark_done()` |
| `done` | stdout に report.json を出力 | END |

## Layer 1 実行（初回のみ）

```
next_action=run_strategist:
  Spawn: strategist agent
  入力: なし（ユーザー要求のみ）
  出力: output/strategy.md
  → checkpoint: advance_layer1("strategist") → next: run_eval_designer

next_action=run_eval_designer:
  Spawn: eval_designer agent
  入力: output/strategy.md
  出力: output/eval_criteria.md
  → checkpoint: advance_layer1("eval_designer") → phase: material_pdca, next: run_material_iter
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
- 各イテレーション後:

```python
from checkpoint import advance_article_iter, write_checkpoint
cp = advance_article_iter(cp, score=current_score)
write_checkpoint(checkpoint_path, cp)
# next_action は advance_article_iter が決定:
#   score >= 0.80 → finalize
#   iter>=3 & score<0.70 & fallbacks<2 → material_fallback
#   iter == 10 → finalize
#   else → run_article_iter
```

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
- **Phase 0 (material iter 1)**: TrendResearcher + PainExtractorは並列spawn可

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
