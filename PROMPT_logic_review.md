# ロジックレビュー・改善検討プロンプト

作業ディレクトリ: /Users/masahiromatsuyama/zenn-article-gen-final-skillbase/

## このセッションの目的

このリポジトリのロジック・設計を理解し、改善点を洗い出す。
**実際のコード変更・ファイル編集は行わない。** 理解と分析のみ。

---

## 背景（必ず読んで把握してから始めること）

### このリポジトリとは

Zenn技術記事を自動生成するClaude Code skillベースのシステム（v5.1）。
前バージョン（v5.0）はAnthropic API直接呼び出し（$12-15/run）だったが、
Claude Codeサブスクリプション内で動作するよう全面再設計した。

### 構成

以下のドキュメントを **この順番で** 読んで全体像を把握すること:
1. `ARCHITECTURE.md` — システム全体設計・エージェント一覧・実行フロー
2. `REQUIREMENTS.md` — 機能要件・非機能要件・成功基準DoD
3. `TECH_SPEC.md` — checkpoint.jsonスキーマ・スクリプトAPIシグネチャ

### 主要コンポーネント

**スキル（`.claude/skills/`）:**
- `zenn-orchestrator/` — Lead。checkpoint.jsonを読んでフェーズを制御
- `zenn-material-pdca/` — 素材収集PDCAの1イテレーション（max 5 iter, threshold 0.85）
- `zenn-article-pdca/` — 記事執筆PDCAの1イテレーション（max 10 iter, threshold 0.80）

**エージェント（`.claude/agents/`）:**
- Layer 1: strategist, eval_designer
- Phase 0+1: trend_researcher, pain_extractor, thesis_designer
- Phase 2: material_reviewer
- Phase 3: writer, style_guide_updater, article_reviewer, consolidator, finalizer

**Pythonスクリプト（`.claude/scripts/`）:**
- `checkpoint.py` — 状態機械（read/write/advance/fallback）
- `metrics.py` — HARD FAIL判定・スコアキャップ・文体自動修正
- `fb_log.py` — フィードバックログ（v5.0のバグ修正済み）
- `stagnation_check.py` — 停滞検出
- `gap_alert.py` — ギャップアラート生成
- `file_registry.py` — ファイルパス定数

### 設計上の重要な判断
- **ネストPDCA**: Material PDCA(5回) → Article PDCA(10回)。記事スコアが低い場合はMATERIAL_FALLBACKで素材PDCAに戻る（最大2回）
- **checkpoint.json**: セッション断絶後の再開に使う。`next_action`フィールドがLeadのルーティングを決定
- **HARD FAIL**: code_ratio>20%→0.60キャップ、desu_masu<80%→0.55キャップ、consecutive_same_length>4→0.50キャップ
- **SubAgent 10KBルール**: エージェントはファイルに書き、pathと2-4文サマリーのみ返す

---

## やってほしいこと

### Step 1: ドキュメントを読む
上記3ファイルを読み、システムを把握する。
疑問点があれば `.claude/skills/` や `.claude/agents/` や `.claude/scripts/` も読んでよい。

### Step 2: 改善候補を洗い出す
以下の観点で分析して、改善候補をリストアップする:

**A. ロジックの穴・エッジケース**
- MATERIAL_FALLBACKした後の素材PDCAは何イテレーション回るか（max_iterのリセット問題）
- stagnation_check の window=3 は適切か
- Consolidator（iter 5のみ）は十分か、もっと早くトリガーすべきか

**B. エージェント設計の品質**
- 各 `.claude/agents/*.md` の指示が曖昧すぎる箇所はないか
- 出力フォーマットが不明確でWriterやReviewerが迷いそうな箇所はないか

**C. スコアリングの信頼性**
- eval_criteria.md の評価軸・重みは適切か
- MaterialReviewerとArticleReviewerがLLMなので、スコアがイテレーション間でばらつく可能性への対処はあるか

**D. セッション断絶耐性**
- checkpoint.jsonに足りないフィールドはないか
- 途中で失敗した場合に何を再実行すべきかが明確か

**E. コスト・スピード**
- Sonnet 4.6でほぼ全エージェントを動かす想定だが、haiku推奨エージェントはどれか
- 並列化できるステップが他にないか

### Step 3: 優先度をつける
改善候補を「Critical / High / Medium / Low」で分類する。
Critical と High のものについては改善案の方向性も示す。

---

## 制約

- コードの変更・ファイルの編集は **絶対にしない**
- 読むだけ → 分析 → 改善リスト の順で進める
- 分析結果は会話上で出力する（新規ファイルへの書き込みも不要）
