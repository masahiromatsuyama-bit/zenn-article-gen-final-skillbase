# 次セッション引き継ぎプロンプト — 問題調査フェーズ

作業ディレクトリ: /Users/masahiromatsuyama/zenn-article-gen-final-skillbase/

## このセッションの目的

前セッションで発見した設計上の問題を **深く調査し、現状を正確に把握する**。
**コードの変更・ファイルの編集は一切行わない。**
調査 → 問題の根拠確認 → 修正方針の整理、まで。

---

## 前セッションで判明していること（仮説）

前セッションで3つのドキュメント（ARCHITECTURE.md / REQUIREMENTS.md / TECH_SPEC.md）と
11個のエージェント定義 + 3つのスキルINSTRUCTIONS.mdを読んだ結果、以下の問題仮説が立っている。

### 🔴 Critical（実装できない・テストが通らないレベル）

**[B-1] next_action のenum値がドキュメント間で完全に異なる**
- REQUIREMENTS.md FR-NEW-03:
  `"trend_research", "pain_extract", "thesis_design", "material_pdca", "article_pdca", "consolidate", "finalize", "done"`
- TECH_SPEC.md §1.1 + ARCHITECTURE.md §6:
  `"run_strategist", "run_eval_designer", "run_material_iter", "run_article_iter", "material_fallback", "finalize", "done"`
- orchestrator INSTRUCTIONS.md は TECH_SPEC側の値を使っている
- → checkpoint.py / route_next_action() の実装時にどちらを使うか不明

**[C-1] HARD FAIL条件がARCHITECTURE.mdとTECH_SPEC.mdで完全に食い違う**
- ARCHITECTURE.md §9:
  `code_ratio > 20% → 0.60cap` / `desu_masu < 80% → 0.55cap` / `consecutive > 4 → 0.50cap`
- TECH_SPEC.md §3.2 (metrics.py APIシグネチャ):
  `desu_masu < 80% → 0.60cap` / `char_count < 3000 → 0.50cap` / `consecutive >= 4 → 0.70cap`
  ※ code_ratioの条件が消えて char_count に変わっている。キャップ値も全部違う
- REQUIREMENTS.md §FR-07には "code_ratio > 20% → 0.60" が書いてある（ARCH側と一致）
- → metrics.py の実装でどちらを使うか不明。DoD T-03が通らない可能性

**[A-2] MATERIAL_FALLBACK の最大回数が「1回」と「2回」で矛盾**
- REQUIREMENTS.md FR-12: 「最大1回まで」
- ARCHITECTURE.md §5.4 + §9 + TECH_SPEC.md §1.1: 最大2回（fallback_count < 2）
- orchestrator INSTRUCTIONS.md: `material_fallback_count < 2`（2回まで）
- → 実装はどちらを使うべきか。人間確認必須リスト（§4.2）とも矛盾している

**[A-1] MATERIAL_FALLBACK後の素材PDCAのmax_iterが未定義**
- REQUIREMENTS.md FR-12: 「フォールバック後は最大3イテレーション追加」と明記
- ARCHITECTURE.md / TECH_SPEC.md: material_iterはmax=5固定。フォールバック後の別上限がない
- checkpoint.json スキーマに `fallback_material_iter_max` のようなフィールドがない
- → フォールバック後に何回回るか実装者が判断できない

### 🟠 High（動くが品質・信頼性に問題）

**[A-3] Consolidatorのスコア反映タイミングが逆**
- zenn-article-pdca INSTRUCTIONS.md を読んで確認したい
- ARCHITECTURE.md §5.3のコードでは:
  `Phase 3b: ArticleReviewer → score` → `[iter==5]: Consolidator` の順
- つまりConsolidator実行後に再レビューされないため、改善がスコアに反映されない
- → iter5のConsolidator後に再度ArticleReviewerを呼ぶべきか？

**[D-2] checkpoint破損時のフォールバックがDEFAULT（=全リセット）**
- checkpoint.py の read_checkpoint() の仕様: 「JSON破損時はDEFAULT_CHECKPOINTを返す」
- これは数十分の作業が全消えを意味する
- → .claude/scripts/checkpoint.py の実装を確認し、backup/recovery機構があるか調べる

---

## やってほしいこと

### Step 1: 実装ファイルを読んで仮説を検証する

以下のファイルを読み、上記の仮説が実際のコードで何を引き起こすかを確認する:

```
.claude/scripts/checkpoint.py         ← B-1, A-2, D-2 に関係
.claude/scripts/metrics.py            ← C-1 に関係
.claude/skills/zenn-article-pdca/INSTRUCTIONS.md  ← A-3 に関係
```

### Step 2: 問題の根拠を整理する

各問題について:
1. 「どのファイルの何行目で矛盾しているか」を特定する
2. 現在の実装コードはどちら側を使っているか（ARCH側 vs TECH_SPEC側）を確認する
3. 実装変更なしで「正しい仕様」を決定するための根拠を整理する

### Step 3: 修正方針を会話で出力する

各問題について以下の形式で整理する:
- **正とすべき仕様**: どちらのドキュメントが正しいか（or どちらも間違いで新設が必要か）
- **修正が必要なファイル**: コードファイル名・ドキュメントファイル名
- **修正の難易度**: コード1行 / スキーマ変更 / 設計変更

---

## 追加調査事項（前セッション未確認）

以下は前セッションで時間切れで未読。仮説検証の参考に読むこと:

```
.claude/skills/zenn-article-pdca/INSTRUCTIONS.md  ← A-3のConsolidatorタイミング確認
.claude/skills/zenn-orchestrator/SKILL.md         ← トリガー条件確認
.claude/scripts/dry_run_validate.py（もしあれば） ← テストロジック確認
dry_run_validate.py                               ← DoD T-03,T-04,T-05の実装確認
```

---

## 制約

- コードの変更・ファイルの編集は **絶対にしない**
- 読む → 仮説検証 → 修正方針の整理、まで
- 修正方針は会話上で出力する（新規ファイルへの書き込みも不要）
- 調査完了後に「次のセッションでやること（実装タスク一覧）」を番号付きで出力すること

---

## 追加設計検討事項 — Agent 12: SystemAnalyst

バグ修正とは別に、**12番目のエージェントの設計**についても調査・整理してほしい。

### 解決したい問題

ユーザーが「自分のリポジトリ（.claude/skills/ や .claude/agents/ 等）の仕組みを記事にしたい」
と言ったとき、それらのファイルを直接orchestratorに読ませると数万トークンがコンテキストに
流れ込んで汚染される。

**解決策の方向性**: SystemAnalystをSubAgentとして呼び、ファイルを全部読ませて
「記事素材として使えるまとめ（system_analysis.md）」だけを書かせる。
親（orchestrator）はそのファイルパスだけ受け取る。10KBルールに従う。

### エージェント定義案

```
名前: SystemAnalyst
役割: 指定されたシステム（ディレクトリ・スキル群）を調査し、
      記事素材として使える「システム解説ドキュメント」を生成する

入力:
  - ユーザーの記事要望（何を伝えたいか）
  - 調査対象ディレクトリパス（例: .claude/skills/zenn-*/）

処理（分析観点）:
  - アーキテクチャの全体像（何をどの順で実行するか）
  - 設計上のユニークな仕組み（PDCAループ・フォールバック等）
  - 工夫しているポイント（10KBルール・checkpoint耐性等）
  - 技術的な意思決定とその理由（なぜこう設計したか）
  - 読者に刺さりそうなエピソード・数値・具体例

出力: output/knowledge/system_analysis.md
返却: ファイルパス + 2-4文サマリーのみ（10KBルール）
```

### 誰がいつ呼ぶか（3案。調査で検討してほしい）

**案A**: Layer 1（Strategist直後、EvalDesigner前）に呼ぶ
- メリット: EvalDesignerがsystem_analysis.mdを評価軸設計に使える
- デメリット: テーマに関係なく毎回呼ばれる

**案B**: Material PDCA iter 1 の Phase 0でTrendResearcher・PainExtractorと並列実行
- メリット: 「素材収集フェーズ」に自然に収まる。iter 1のみ実行で以降はファイル参照
- デメリット: iter 2以降は呼ばない設計を明示的に書く必要がある

**案C**: Strategistが strategy.md に `requires_system_analysis: true/false` フラグを立て、
orchestratorが条件分岐して呼ぶ
- メリット: 汎用性が高い。システム解説記事以外はスキップできる
- デメリット: Orchestratorに条件分岐ロジックが増える

### アウトプットを誰に渡すか

- **ThesisDesigner**: trends.md・pains.md と並列に system_analysis.md を参照して骨格設計
- **Writer**: 記事執筆時に正確な技術的詳細の参照元として使う

### 調査してほしいこと

1. 現在の zenn-material-pdca INSTRUCTIONS.md の Phase 0 を読み、案Bを採用した場合の
   変更箇所（何行目に何を追加するか）を特定する
2. 案A/B/Cのトレードオフを整理し、推奨案を1つ選んで理由を述べる
3. .claude/agents/ に systemanalyst.md を追加する場合のファイル雛形を会話上で出力する
   （実際には書かない。内容案だけ出力）

---

## 参考: 前セッションで読んだファイル一覧

```
ARCHITECTURE.md
REQUIREMENTS.md
TECH_SPEC.md
.claude/agents/ 配下 11ファイル全て
.claude/skills/zenn-material-pdca/INSTRUCTIONS.md
.claude/skills/zenn-orchestrator/INSTRUCTIONS.md
```

（これらは再読不要。内容は上記の仮説に反映済み）
