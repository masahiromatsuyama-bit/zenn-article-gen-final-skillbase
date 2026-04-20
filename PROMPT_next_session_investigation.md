# 次セッション：システム深部調査 & 改善計画プロンプト

作業ディレクトリ: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`

---

## このセッションの目的

**コードとプロンプトを修正するのではなく、まず「何が壊れているか / 何が設計として甘いか」を正確に把握し、優先度付きの改善計画を立てること。**

前セッションの本番テスト実行（End-to-Endラン）の詳細ログ分析により、以下のカテゴリで問題が発見されています。
あなたはこのシステムの設計を熟知する技術レビュアーとして、各仮説をコードを引用しながら検証し、改善計画を作成してください。

**修正は行わない。調査・分析・計画立案のみ。**

---

## 背景：このシステムとは

Zenn技術記事を一言の指示から全自動生成するシステム（v5.1 Skillbaseアーキテクチャ）です。

```
Layer1（戦略策定）
  → Material PDCA（素材磨き / max 5 iter / 閾値 0.85）
    → Article PDCA（記事磨き / max 10 iter / 閾値 0.80）
      → Finalize
```

主要ファイル構成:
```
.claude/scripts/          ← Python決定論ロジック（checkpoint, metrics, fb_log等）
.claude/skills/           ← Orchestrator / Material PDCA / Article PDCA の INSTRUCTIONS
.claude/agents/           ← 各サブエージェント定義（strategist, writer, reviewer等）
human-bench/              ← ベンチマーク記事（v5.0から移植済み、詳細は後述）
dry_run_validate.py       ← 仕様テスト（spec-as-code）
output/                   ← 前回実行の成果物（checkpoint.json, review.json等）
```

---

## 前回実行で判明した最重要の発見：評価ループが自己参照になっている

前回の本番テスト実行では **Material PDCA・Article PDCA ともに iter 1 でスコアが閾値を突破** しました（0.866 / 0.856）。これによりPDCAループは実質1回しか回らず、以下の機構が**完全未テスト**のままです:

- gap_alert（3 iter 停滞検知）
- MATERIAL_FALLBACK（article_iter ≥ 3 かつ score < 0.70）
- Consolidator（article_iter == 5 時のみ起動）
- fb_log の stagnation_check との連携
- iter 2 以降の ThesisDesigner / Writer の「前回フィードバック反映」

**根本原因として判明したこと**: v5.0 では EvalDesigner が `human-bench/`（実際にTrend入りしたZenn記事8本）を読んで評価基準を設計していました。v5.1 への移行時にこのディレクトリが**丸ごと消えた**ため、評価基準がこの記事専用の自己参照になっています。

```python
# v5.0 meta_agents.py（旧システム）での EvalDesigner プロンプト
_DEFAULT_EVAL_DESIGNER_PROMPT = """\
You are the Eval Designer. Read strategy.md and human-bench/ to generate
eval_criteria.md ...
"""
```

現在の v5.1 では EvalDesigner は `strategy.md` だけを読んでいます。
「この記事の方針」をそのまま「この記事の評価基準」にしているため、
生成した記事が iter 1 で高得点を取るのは構造上必然です。

---

## 調査対象ファイル（全て読んでください）

### Python スクリプト
- `.claude/scripts/checkpoint.py`
- `.claude/scripts/metrics.py`
- `.claude/scripts/fb_log.py`
- `.claude/scripts/stagnation_check.py`
- `.claude/scripts/gap_alert.py`

### スキル INSTRUCTIONS
- `.claude/skills/zenn-orchestrator/INSTRUCTIONS.md`
- `.claude/skills/zenn-material-pdca/INSTRUCTIONS.md`
- `.claude/skills/zenn-article-pdca/INSTRUCTIONS.md`

### エージェント定義（全て）
- `.claude/agents/` 配下の全 .md ファイル

### ベンチマーク資産
- `human-bench/index.yaml`（8本のベンチマーク記事の目次）
- `human-bench/articles/` 配下の記事（必要に応じて）

### 前回実行の成果物（証拠として参照）
- `output/checkpoint.json`
- `output/eval_criteria.md`（現在の評価基準 — 自己参照になっている実物）
- `output/material_reviews/1/review.json`（スコア 0.866 の証拠）
- `output/iterations/1/review.json`（スコア 0.856 の証拠）
- `output/report.json`

---

## 検証してほしい仮説リスト

---

### 🔴 カテゴリA：確定バグ（実行すると壊れる）

**A-1: fb_log の呼び出しシグネチャが4箇所全てミスマッチ**

INSTRUCTIONS に書かれている呼び出しコードと、実際の Python 関数シグネチャが一致していない可能性があります。

確認ポイント（コードを引用して判定してください）:

| 呼び出し箇所 | INSTRUCTIONS での呼び方 | 実際のシグネチャ | ミスマッチの内容 |
|---|---|---|---|
| `load_fb_log()` | 引数なしで呼ぶ | `load_fb_log(path: str)` | path引数が必須なのに渡していない |
| `should_trigger_gap_alert(fb_log, phase="material")` | phase=キーワードを渡す | `should_trigger_gap_alert(entries, threshold, window)` | phaseパラメータ存在しない・thresholdが渡されていない・entriesの型が違う（FBEntryリスト vs dict with score） |
| `format_gap_alert(alert)` | 1引数で呼ぶ | `format_gap_alert(current_score, threshold, feedback_history)` | 3引数必要なのに1引数 |
| `append_fb_diff(iter=, phase=, score=, feedback=)` | 4引数キーワードで呼ぶ | `append_fb_diff(path, entries, prev_entries, iteration, phase)` | シグネチャが完全に異なる |

各ミスマッチを該当コードの引用付きで確認してください。

**A-2: fix_code_ratio() が存在しない**

`metrics.py` には `fix_desu_masu()` と `fix_consecutive_length()` があるが、
code_ratio の HARD FAIL（コードブロック比率超過）を自動修正する関数がない可能性があります。
前回実行では code_ratio が 0.25 に超過したが、オーケストレーターが手動でコードブロックをトリムして対処しました。

確認ポイント:
- `metrics.py` に `fix_code_ratio` またはそれに相当する関数が存在するか
- `zenn-article-pdca/INSTRUCTIONS.md` の HARD FAIL 修正フローで code_ratio の修正手順が書かれているか
- code_ratio HARD FAIL 時の「自動修正不能」という問題が明示されているか

**A-3: Material PDCA の fb_log 書き込みパスが存在しない**

`zenn-material-pdca/INSTRUCTIONS.md` に fb_log を**書く**ステップが存在しない可能性があります。

確認ポイント:
- `zenn-material-pdca/INSTRUCTIONS.md` の全ステップを列挙し、fb_log 書き込みステップの有無を確認
- `zenn-article-pdca/INSTRUCTIONS.md` には Step 8 として `append_fb_diff()` がある。素材側にも相当するステップがあるか

---

### 🟠 カテゴリB：チェックポイント設計の欠陥（セッション断絶で壊れる）

**B-1: SystemAnalyst のステートが checkpoint に存在しない**

`requires_system_analysis: true` の場合、SystemAnalyst は EvalDesigner 完了後・Material PDCA 開始前に実行される。
しかし checkpoint の `next_action` は EvalDesigner 完了直後に `run_material_iter` に進む可能性があります。

確認ポイント:
- `checkpoint.py` の `advance_layer1("eval_designer")` が返す `next_action` を確認
- `VALID_TRANSITIONS` に `run_system_analyst` が存在するか
- `zenn-orchestrator/INSTRUCTIONS.md` の Stage Dispatch Table に SystemAnalyst のエントリがあるか
- セッション断絶後に再起動した場合、SystemAnalyst がスキップされるか否か

**B-2: MATERIAL_FALLBACK 後のファイル上書き問題**

`trigger_material_fallback()` は `article_iter = 0` にリセットします。
その後の新しい Article PDCA iter 1 は `output/iterations/1/article.md` に書き込みます。
この時点で、フォールバック前の `best_article_iter` が指すファイルが上書きされる可能性があります。

確認ポイント:
- `checkpoint.py` の `trigger_material_fallback()` が `best_article_iter` をリセットするか確認
- フォールバック後に新 article iter 1 が走ると `output/iterations/1/` が上書きされる構造を確認
- `finalizer.md` が `best_article_iter` のファイルを参照する設計か確認
- フォールバック前の `best_article_iter` が指すファイルが上書きされる場合、Finalizer が壊れるか

---

### 🟡 カテゴリC：エージェント間のファイル受け渡し設計の抜け漏れ

**C-1: system_analysis.md が ThesisDesigner・Writer の入力リストにない**

SystemAnalyst が生成する `output/knowledge/system_analysis.md` は、
ThesisDesigner と Writer が参照すべき重要素材ですが、
それぞれのエージェント定義（.md）の入力リストに含まれていない可能性があります。
前回実行ではオーケストレーターが手動でこれを補いました。

確認ポイント:
- `thesis_designer.md` の「入力」セクションに `system_analysis.md` が含まれているか
- `writer.md` の「入力」セクションに `system_analysis.md` が含まれているか
- `zenn-material-pdca/INSTRUCTIONS.md` の ThesisDesigner spawn 指示に含まれているか
- `zenn-article-pdca/INSTRUCTIONS.md` の Writer spawn 指示に含まれているか

**C-2: fb_log のファイルパスが未定義**

`fb_log.py` の `load_fb_log(path: str)` は path 引数が必須ですが、
INSTRUCTIONS には引数なしで書かれている可能性があります。
`output/fb_log.json` というパスがシステム全体のどこにも定義されていない可能性があります。

確認ポイント:
- INSTRUCTIONS 全体を横断して `fb_log.json` のパスが明記されているか確認
- `output/` 以下の期待ファイル一覧にfb_logが含まれているか

**C-3: thesis.md にバージョン管理がない**

thesis.md は毎 iter `output/thesis.md` に上書きされます。
material_reviews/{iter}/review.json のように iter 番号付きで保存されていない可能性があります。
これにより過去の thesis との差分追跡ができず、改善がどこに効いたか不明になります。

確認ポイント:
- `zenn-material-pdca/INSTRUCTIONS.md` で thesis.md の保存先パスを確認（固定 or iter番号付き）
- MaterialReviewer の入力に「前回の thesis.md」が含まれているか、または thesis.md が上書きされていてもよい設計か確認

---

### 🔵 カテゴリD：品質ループ設計の構造的問題

**D-1: ベンチマーク記事（human-bench/）が評価に使われていない**

**これが最重要の構造的問題です。**

v5.0 では EvalDesigner が `human-bench/`（実際にTrend入りしたZenn記事8本）を読んで評価基準を設計していました。
v5.1 への移行時にこのディレクトリが消え、現在の EvalDesigner は `strategy.md` のみを入力としています。

```python
# v5.0 meta_agents.py でのプロンプト（旧）
"You are the Eval Designer. Read strategy.md and human-bench/ to generate eval_criteria.md"
```

現在の `output/eval_criteria.md`（前回実行の成果物）を読むと、ベンチマーク記事への参照が一切ない自己参照的な評価基準になっています。

確認ポイント:
- `eval_designer.md` の入力リストに `human-bench/` が含まれているか
- `material_reviewer.md` の入力リストにベンチマーク記事参照があるか
- `article_reviewer.md` の入力リストにベンチマーク記事参照があるか
- `human-bench/index.yaml` を読んでどのような記事が揃っているか把握する
- v5.0の `meta_agents.py` がある場合（`/Users/masahiromatsuyama/zenn-article-gen-final/orchestrator/meta_agents.py`）を参照してv5.0での使われ方を確認する

**D-2: major feedback があってもスコアにペナルティがない**

前回実行では ArticleReviewer が major feedback 2件を出しながら 0.856 を採点しました。
major feedback はスコアを下げるルールが存在しないため、
「重大な問題があっても合格」という状況が構造的に発生します。

確認ポイント:
- `article_reviewer.md` に major feedback 件数とスコアの関係が定義されているか
- `material_reviewer.md` に同様のルールがあるか
- `zenn-article-pdca/INSTRUCTIONS.md` の Step 5（スコア計算）で major feedback が考慮されているか
- `apply_hard_fail()` は metrics のみを対象にしており、reviewer feedback を考慮しない設計であることを確認

**D-3: Consolidator の起動条件が品質向上に逆行している**

Consolidator（iter 1-5 の最良部分を統合するエージェント）は `article_iter == 5` のみ起動します。
しかし Article PDCA は `score >= 0.80` の時点で即 finalize します。
つまり品質が高い記事ほど Consolidator が起動されないという逆転現象が起きている可能性があります。

確認ポイント:
- `advance_article_iter()` の finalize 条件（score >= 0.80 → finalize）を確認
- Consolidator が起動する実際の条件（iter 5 まで score < 0.80 が5回続いた場合のみ）を整理
- 「Consolidatorによる品質向上」と「早期 finalize」が両立しない設計になっていないか評価
- 解決策の方向性として「iter 3 以降は毎回 Consolidator を走らせる」「score >= 0.80 でも iter 5 まで継続する」等の選択肢を検討する

---

### ⚪ カテゴリE：設計意図の確認

**E-1: HARD FAIL 後スコアの扱いが未定義**

HARD FAIL が発動して article.md を修正し、再チェックでクリアした場合、
スコアに cap を適用すべきか否かのルールが INSTRUCTIONS に存在しない可能性があります。
前回実行では「修正後クリア → cap なし → 0.856 採用」という判断をしましたが、これが仕様として正しいか不明です。

確認ポイント:
- `zenn-article-pdca/INSTRUCTIONS.md` の Step 5（スコア計算）に「修正後クリアした場合」の記述があるか
- `apply_hard_fail(raw_score, hf)` を呼ぶタイミングが修正前か修正後かが明記されているか

**E-2: MATERIAL_FALLBACK 後の knowledge/ 再生成の設計意図**

`trigger_material_fallback()` は `material_iter = 0` にリセットします。
次の Material PDCA の iter 1 では TrendResearcher + PainExtractor が再実行され、
`knowledge/trends.md` と `knowledge/reader_pains.md` が上書きされます。
これは意図的な設計か設計上の見落としか。

確認ポイント:
- `zenn-orchestrator/INSTRUCTIONS.md` と `zenn-material-pdca/INSTRUCTIONS.md` に
  フォールバック後の knowledge/ 再生成について明記があるか
- SystemAnalyst が生成する `system_analysis.md` は MATERIAL_FALLBACK 後も再生成されないが、問題にならないか

---

## 調査の進め方

1. **全ファイルを読む**（上記「調査対象ファイル」を全て精読する）
2. **各仮説を検証する**（コードを引用して「確定バグ/設計課題/問題なし」を判定）
3. **新たな問題を発見したら追記する**（仮説リストに含まれていない問題でも積極的に報告）
4. **優先度付き改善計画を作成する**

---

## 出力フォーマット

### Part 1: 仮説検証結果

各仮説について以下の形式で報告:
```
### 仮説 X-N: [タイトル]
判定: 🔴 確定バグ / 🟠 設計課題 / 🟡 要検討 / ✅ 問題なし
根拠: [該当コード引用 + 説明]
影響範囲: [どのフローが壊れるか / どの記事品質に影響するか]
```

### Part 2: 新規発見の問題（仮説リスト外）

調査中に発見した問題があれば同フォーマットで追記。

### Part 3: 優先度付き改善計画

```
## 改善計画

### P0（今すぐ直さないと本番ランが壊れる）
- [改善項目]: [何をどう直すか] / 種別: プロンプト or コード / 対象ファイル

### P1（複数 iter ループを正しく動かすために必要）
- [改善項目]: [何をどう直すか] / 種別: プロンプト or コード / 対象ファイル

### P2（品質向上・評価の外部キャリブレーション）
- [改善項目]: [何をどう直すか] / 種別: プロンプト or コード / 対象ファイル
```

**改善計画のルール**:
- 「プロンプト（INSTRUCTIONS/.md）修正」と「コード（.py）修正」を必ず分類する
- コード修正が先、プロンプト修正が後（コードが変わるとプロンプトに書くべき内容も変わるため）
- 修正前に `dry_run_validate.py` にテストを書くことを推奨する箇所を明示する

---

## 注意事項

- **修正は行わない**。調査・分析・計画立案のみ。
- ファイルを読む際は全文精読（関係ありそうな箇所だけ読むのは不可）。
- 「たぶんこう動くはず」ではなく、コードを引用して根拠を示すこと。
- 前回実行の `output/` 成果物は「何が実際に起きたか」の証拠として積極的に参照すること。
- v5.0 の旧実装（`/Users/masahiromatsuyama/zenn-article-gen-final/orchestrator/`）は
  設計意図の確認に使ってよい（修正対象ではなく参照のみ）。
