# REQUIREMENTS.md — Zenn記事自動生成システム v5.1 (Skillbase Rewrite)

> **対象バージョン**: v5.1  
> **前バージョン**: v5.0 (Anthropic API直接呼び出し方式)  
> **アーキテクチャ方式**: Claude Code Independent Skill  
> **作成日**: 2026-04-20  
> **ステータス**: 確定

---

## 目次

1. [スコープ](#1-スコープ)
   - 1.1 対象記事型 (in)
   - 1.2 対象外 (out)
2. [機能要件](#2-機能要件)
   - 2.1 v5.0継承FR
   - 2.2 廃止FR＋理由
   - 2.3 変更FR
   - 2.4 新設FR
3. [非機能要件](#3-非機能要件)
   - 3.1 Opusスポーン回数
   - 3.2 実行時間
   - 3.3 セッション断絶耐性
   - 3.4 並列禁止
4. [Leadの権限範囲](#4-leadの権限範囲)
   - 4.1 自発判断OK
   - 4.2 人間確認必須
5. [成功基準DoD](#5-成功基準dod)
   - 5.1 技術
   - 5.2 品質
   - 5.3 ビジネス除外
6. [既知リスクと受容可否](#6-既知リスクと受容可否)
7. [v5.0からの変更点サマリー（トレーサビリティ表）](#7-v50からの変更点サマリートレーサビリティ表)

---

## 1. スコープ

### 1.1 対象記事型 (in)

本システムが自動生成の対象とする記事型を以下に定義する。

| # | 記事型 | 説明 |
|---|--------|------|
| 1 | 体験記・試行錯誤型 | 開発者が実際に試みた過程を一人称で記述する記事 |
| 2 | ツール解説型 | 特定のOSSツール・SaaSの使い方・ハマりどころを解説する記事 |
| 3 | 比較検証型 | 複数の技術・手法を比較し、知見を提供する記事 |
| 4 | チュートリアル型 | ステップバイステップで読者がハンズオン可能な記事 |
| 5 | LLM/AI活用型 | LLMを活用した開発・業務改善の知見を共有する記事 |

**対象プラットフォーム**: Zenn（zenn.dev）専用。Markdown形式で出力する。

**対象読者ペルソナ**:
- エンジニア歴1〜5年のWebエンジニア・AIエンジニア
- LLM/AIツールに興味があり、実践的な知見を求める読者
- Zennでトレンド入りを狙うレベルの質を評価できる読者

### 1.2 対象外 (out)

以下は本システムのスコープ外とする。

| # | 対象外項目 | 理由 |
|---|------------|------|
| 1 | ニュース・速報型記事 | リアルタイム情報取得の仕組みを持たないため |
| 2 | 企業プレスリリース・PR記事 | 客観性要件と相反するため |
| 3 | 技術仕様書・リファレンス文書 | 体験記フォーマットに適合しないため |
| 4 | 英語・多言語記事 | 日本語Zenn向けスタイルガイドに特化しているため |
| 5 | 5,000字未満の短文記事 | 品質評価閾値の設計前提が2,000〜6,000字のため |
| 6 | 動画・画像リッチコンテンツ | テキスト生成のみをスコープとするため |
| 7 | Zenn以外のプラットフォーム向け記事（note, Qiita等） | スタイルガイドがZenn最適化されているため |

---

## 2. 機能要件

### 2.1 v5.0継承FR

以下の機能要件はv5.0から変更なく継承する。

#### FR-01: トレンド収集フェーズ
- TrendResearcherエージェントが最新技術トレンドを収集し、`knowledge/trends.md` に永続化する
- 実行ごとにファイルを上書き更新する（累積しない）
- トレンドソース: Zennトレンド、GitHub Trending、Twitter/X技術タグ（各エージェント実装内に定義）

#### FR-02: 読者ペインポイント抽出フェーズ
- PainExtractorエージェントがトレンドデータをもとに読者の悩みを構造化し、`knowledge/reader_pains.md` に永続化する
- 出力形式: 悩みカテゴリ、具体的ペイン文、推定頻度の3列構造

#### FR-03: 記事論点設計フェーズ
- ThesisDesignerエージェントがトレンド＋ペインをもとに記事の主張（テーゼ）と構成案を設計する
- 出力: テーゼ1本、H2セクション3〜5本、各セクションのキーポイント

#### FR-04: 素材生成PDCAフェーズ
- 最大5イテレーション、閾値0.85でMaterialReviewerが素材品質を評価する
- 各イテレーションで素材スコアが閾値未満の場合、Writerが素材を改善して再評価する
- イテレーション5終了時点で閾値未達でも記事生成フェーズへ進む（強制進行）

#### FR-05: 記事生成PDCAフェーズ
- 最大10イテレーション、閾値0.80でArticleReviewerが記事品質を評価する
- 各イテレーションで記事スコアが閾値未満の場合、Writerが記事を改善して再評価する

#### FR-06: スタイルガイド更新
- StyleGuideUpdaterが各記事PDCAイテレーション終了時に `style_memory/style_guide.md` を更新する
- 更新内容: 今回のイテレーションで発見したスタイル上の知見をdiffとして追記

#### FR-07: HARDFAILキャップ適用
- `metrics.py` が以下の条件でスコアを上書きキャップする（LLM評価より優先）
  - `code_ratio > 20%` → スコアを強制的に0.60に設定
  - `desu_masu_ratio < 80%` → スコアを強制的に0.55に設定
  - `consecutive_same_length > 4` → スコアを強制的に0.50に設定
- HARDFAILが発動した場合、fb_log.jsonにHARDFAIL発動ログを記録する

#### FR-08: フィードバックログ永続化
- `fb_log.py` が各イテレーションのフィードバックエントリを `fb_log.json` に追記保存する
- 出力形式: `{"entries": [...], "diffs": [...]}`

#### FR-09: エージェントメモリ管理
- `agent_memory/memory.json` にスコア軸別評価と死亡パターンを保存する
- 形式: `{"score_by_axis": {...}, "death_patterns": [...]}`

#### FR-10: コンソリデーション＆最終化
- **Consolidator の起動条件（v5.1）**: orchestrator が `advance_article_iter` の結果 `next_action="consolidate"` を返した時のみ。具体的には:
  - `article_iter >= 3 AND score >= 0.80`（閾値通過時の品質統合）
  - `article_iter == 10`（最終救済統合）
  - iter 1-2 で閾値通過した場合は Consolidator を **スキップして直接 finalize**
  - 旧仕様の「iter == 5 固定」は廃止
- Consolidator は iter 1〜N の全 article.md / review.json を統合し、最高スコア iter の記事に上書きする
- 統合後は ArticleReviewer を再 spawn して review.json を再生成し、`apply_hard_fail` + `apply_major_penalty` で最終スコアを確定する
- Finalizer が最終記事を Markdown 形式で `output/final_article.md` に書き出す

#### FR-11: 実行レポート出力
- システム終了時にstdoutへJSON形式のレポートを出力する
- レポートに含む項目: 最終スコア、総イテレーション数、HARDFAIL発動回数、所要時間（秒）

#### FR-12: MATERIAL_FALLBACKトリガー
- 発動条件: `article_iter >= 3 AND score < 0.70 AND material_fallback_count < 2`
- 発動時の処理:
  - `output/iterations/` を `output/iterations_fallback_{count}/` にリネームしてアーカイブ（orchestrator 側）
  - `material_iter=0`, `article_iter=0` にリセット
  - `best_article_iter=None`, `best_article_score=0.0` にリセット（v5.1 追加。Finalizer が古い iter を参照しないようにするため）
  - `material_fallback_count` をインクリメント
- バックトラック後は素材 PDCA が再度最大5イテレーション走る（元の 5 iter 制約を再適用）
- バックトラックは1ランにつき最大2回まで

### 2.2 廃止FR＋理由

以下のFRはv5.1で廃止する。

| FR番号(v5.0) | 機能名 | 廃止理由 |
|---|---|---|
| FR-A1 | Agent Editorによるワークフロー動的編集 | ワークフローをINSTRUCTIONS.mdに固定することで予測可能性を確保。動的編集はデバッグコストが高く、品質改善に寄与しなかった |
| FR-A2 | MetaReviewerによる独立メタレビュー | 記事PDCAロジック内に統合することでエージェント数を削減。独立スポーンのトークンコストに対してリターンが不十分だった |
| FR-A3 | Anthropic SDK直接呼び出しによるエージェント起動 | Claude Code Skillベースアーキテクチャへの完全移行により不要 |
| FR-A4 | 動的プロンプト文字列組み立て（文字列テンプレート方式） | 各エージェントの定義をINSTRUCTIONS.mdに記載する固定方式へ移行 |

### 2.3 変更FR

以下のFRはv5.1で仕様変更する。

#### FR-08 (変更): フィードバックログ — diffsの正確な記録

**v5.0の問題**: `save_fb_log(path, entries, [])` が常に空リストを第3引数に渡していたため、diffs配列が常に空だった（Bug #1）。

**v5.1の仕様**:
- `fb_log.py` の `save_fb_log(path, entries, diffs)` 呼び出し時に、呼び出し元で算出したdiffsリストを渡す
- diffsリストの算出: 前イテレーションスコアと現イテレーションスコアの差分を各評価軸ごとに計算し、リスト形式で渡す
- `run start` 時に `fb_log.json` を `{"entries": [], "diffs": []}` にリセットする（Bug #5対応）

#### FR-09 (変更): エージェントメモリ — review_historyのPDCA返却

**v5.0の問題**: `review_history` が `[]` でハードコードされており、エージェントメモリが常に空だった（Bug #6）。

**v5.1の仕様**:
- 記事PDCAループは `tuple[float, list[dict]]`（スコア, レビュー履歴）を返す
- 返却されたレビュー履歴を `agent_memory/memory.json` の `score_by_axis` と `death_patterns` の更新に使用する
- PDCAの各イテレーション終了時にメモリを更新する（最終イテレーション時のみでなく、毎回更新）

#### FR-04/FR-05 (変更): リソース制限チェックの必須化

**v5.0の問題**: `check_resource_limits()` が定義されているが呼び出されていなかった（Bug #2）。

**v5.1の仕様**:
- 素材PDCA・記事PDCAの各イテレーション開始時に `check_resource_limits()` を呼び出す
- リソース制限超過時は当該イテレーションをスキップし、エラーログに記録して次イテレーションへ進む
- リソース制限の定義はv5.0から継承（トークン上限、実行時間上限）

#### FR-10 (変更): ディレクトリリセット処理の確実な実行

**v5.0の問題**: リセット対象ディレクトリが `makedirs` のみで初期化され、前回実行の残存ファイルが混入していた（Bug #4）。

**v5.1の仕様**:
- ラン開始時に `shutil.rmtree(target_dir)` を実行してからディレクトリを再作成する
- 対象ディレクトリ: `output/`, `agent_memory/`, `knowledge/`（`style_memory/` は累積管理のためリセット対象外）

### 2.4 新設FR

#### FR-NEW-01: 停滞検出（Stagnation Detection）

- **担当スクリプト**: `stagnation_check.py`（新設、決定論的Pythonスクリプト）
- **検出条件**: 連続3イテレーションでスコア改善がない場合（改善 = 前イテレーション比+0.01以上）
- **発動アクション**: `gap_alert.py` を呼び出してギャップアラートを生成し、fb_log.jsonに記録する
- **カウンタ管理**: `resolution_rate_counter` を `stagnation_check.py` 内で管理し、停滞解消（改善発生）時にカウンタをリセットする
- **PDCAループ内での呼び出し**: 素材PDCA・記事PDCAの両方で適用する

#### FR-NEW-02: ギャップアラート生成（Gap Alert）

- **担当スクリプト**: `gap_alert.py`（新設、決定論的Pythonスクリプト）
- **算出ロジック**: 現在スコアと閾値のギャップ（`threshold - current_score`）を評価軸ごとに算出する
- **アラート形式**: 最大改善幅の評価軸3本を優先度順に列挙したMarkdown形式のアラートテキスト
- **出力先**: `fb_log.json` の `entries` に追記 + stdoutに警告出力（ログレベル WARNING）
- **LLMへの受け渡し**: 次イテレーションのWriterプロンプトにアラートテキストを注入する

#### FR-NEW-03: チェックポイント管理（Checkpoint Management）

- **担当スクリプト**: `checkpoint.py`（新設、決定論的Pythonスクリプト）
- **ファイル**: `checkpoint.json`（ランごとにリセット）
- **`next_action` フィールド**: セッション再開時に次に実行すべきアクションを特定するためのフィールド
  - 取りうる値: `"run_strategist"`, `"run_eval_designer"`, `"run_system_analyst"`, `"run_topic_selector"`, `"run_experience_author"`（v5.2 NEW）, `"run_material_iter"`, `"material_fallback"`, `"run_article_iter"`, `"consolidate"`, `"finalize"`, `"done"`
- **保存タイミング**: 各フェーズ完了直後に `checkpoint.json` を更新する
- **復元フロー**: セッション再開時に `checkpoint.json` を読み込み、`next_action` の値からフェーズを再開する
- **状態保持対象**: 現在のイテレーション番号、現在のスコア、レビュー履歴の件数

#### FR-NEW-04: メタエージェント簡素化（Strategist + Eval Designerのみ）

- **Strategist**: ランの開始時に記事テーマ・方向性を決定し、以降のフェーズへ引き渡す。strategy.md 先頭の YAML frontmatter に `requires_system_analysis: true/false` を必ず出力する
- **Eval Designer**: 各フェーズの評価基準（採点軸・重み）を設計し、MaterialReviewer・ArticleReviewerへ引き渡す
- **廃止エージェント**: Agent Editor（FR-A1廃止に対応）、MetaReviewer（FR-A2廃止に対応）
- **合計エージェント数**: 11（v5.0の15から4削減）

#### FR-NEW-05: SystemAnalyst の条件付き実行（v5.1 追加、FIX-B-1）

- **起動条件**: `strategy.md` frontmatter の `requires_system_analysis: true` の場合のみ、Layer 1 EvalDesigner 完了後・Material PDCA 開始前に1回だけ実行
- **出力**: `output/knowledge/system_analysis.md`（システム設計の構造化解説）
- **消費者**: ThesisDesigner / Writer の入力に含める。存在しない場合は当該ステップをスキップする（入力リストから除外）
- **checkpoint 遷移**: `advance_layer1(cp, "eval_designer", requires_system_analysis=True)` → `next_action="run_system_analyst"` → `advance_layer1(cp, "system_analyst")` → `next_action="run_material_iter"`

#### FR-NEW-06: ベンチマーク記事参照による自己参照防止（v5.1 追加、FIX-D-1）

- **問題**: v5.0 移植時に EvalDesigner / MaterialReviewer / ArticleReviewer の入力から `human-bench/` が抜けていたため、評価基準が「この記事の戦略で、この記事を採点する」自己参照状態になっていた
- **仕様**:
  - EvalDesigner は `human-bench/index.yaml` と同系統の記事 3-4 本を必ず読んで評価軸を設計する
  - eval_criteria.md の `## ベンチマーク` セクションに参照した記事 ID を最低3件明記する
  - MaterialReviewer / ArticleReviewer は eval_criteria.md で参照されているベンチ記事を必ず読み、各軸のスコアリングに比較コメントを含める

#### FR-NEW-08: Experience Authoring phase（v5.2 追加）

- **問題**: Material PDCA に渡される入力は、ユーザーの 1-2 行のテーマ発話から LLM が想像で膨らませた strategy.md / reader_pains.md / topic.md と、外部クロール結果の trends.md、静的コード解説の system_analysis.md のみ。**著者本人の生々しい経験・固有の数値・個別の失敗は 1 ビットも含まれない**。結果、ThesisDesigner / Writer が一人称の失敗描写を憶測で捏造し、記事が AI 臭くなる
- **仕様**:
  - Topic Selection 完了後・Material PDCA 開始前に 1 回だけ実行される新 phase `experience_authoring` を追加
  - `ExperienceAuthor` agent が `strategy.md` / `trends.md`（存在する場合）/ `system_analysis.md`（存在する場合）/ `topic.md`（存在する場合）/ `eval_criteria.md` を入力に、`output/knowledge/experience_log.md` を固定テンプレートで出力
  - テンプレートセクション: `## 数値で驚いたこと`（必須1件以上）/ `## ハマったこと`（必須1件以上）/ `## 「こう思ったのに違った」体験`（推奨）/ `## 未解決の疑問・迷い` / `## 既存記事とのズレを感じた箇所` / `## 使わない素材`
  - ThesisDesigner の入力に `experience_log.md` を**最優先ソース**として追加。一人称の失敗描写・生々しい数値・具体的な日時・個人的な迷い・感情反応は、必ずこのファイルから引用する（憶測禁止）
  - Writer は experience_log を**直接参照しない**（案A・単一 source of truth 維持）。thesis.md 経由で間接的に受け取る
  - 失敗時は 3 回 retry 後スキップし、experience_log.md 無しで Material PDCA に進む。ThesisDesigner は「存在する場合のみ」扱い。report.json に `degraded_mode=true` を記録
- **checkpoint 遷移**: `advance_topic_selection(cp)` → `phase="experience_authoring", next_action="run_experience_author"` → `advance_experience_authoring(cp)` → `phase="material_pdca", next_action="run_material_iter"`
- **実装方式（v5.2.1 確定）**: **Multi-Agent Drama Simulation**（Option E）。3 役（Human / Claude / Director）を 1 プロンプト内で演じ分け、情報非対称性を契約として守らせる（Claude はノーヒント・Director が罠を仕込む・Human はプロエンジニアで題材固有罠は未知）。Phase 1（Director 準備で罠 5-8 個抽出 → 事件 2-3 個選定） → Phase 2（8 ターン目安で drama 実行 → `drama_raw.md` 逐次追記） → Phase 3（`drama_raw.md` → `experience_log.md` 圧縮）。実装は擬似コード / 設計レベルに留める（実コードは走らせない）
- **副産物**: `output/knowledge/drama_raw.md`（3 役対話の生ログ）。下流からは読まず、後日のデバッグ / 再圧縮用

#### FR-NEW-07: major feedback による score cap（v5.1 追加、FIX-D-2）

- **問題**: v5.0/v5.1 初期実装では reviewer が major feedback を何件出してもスコアに影響しなかった
- **仕様**: `metrics.apply_major_penalty(score, major_count)` を Article PDCA Step 5 / Material PDCA のスコア確定時に適用
  - `major_count >= 3` → cap 0.70（MATERIAL_FALLBACK 閾値以下）
  - `major_count >= 2` → cap 0.79（article threshold 0.80 未満）
  - `major_count >= 1` → cap 0.84（material threshold 0.85 未満）
  - `major_count == 0` → 変化なし
- 「major 残存 → PDCA が通らない」を機械的に保証する

---

## 3. 非機能要件

### 3.1 Opusスポーン回数

| ID | 要件 | 値 | 根拠 |
|---|---|---|---|
| NFR-01 | 1ランあたりの最大Opus呼び出し回数 | 50回以下 | コスト上限の制約。超過した場合はSonnetへフォールバック |
| NFR-02 | Opus必須フェーズ | Strategist, Eval Designer, ArticleReviewer（最終評価のみ） | 品質判定の信頼性確保のため |
| NFR-03 | Sonnetで代替可能なフェーズ | Writer（各イテレーション）, MaterialReviewer（中間イテレーション）, StyleGuideUpdater | コスト最適化のため |

### 3.2 実行時間

| ID | 要件 | 値 | 条件 |
|---|---|---|---|
| NFR-04 | 1ランの目標完了時間 | 30分以内 | ネットワーク待機・LLM応答時間を含む |
| NFR-05 | 1ランの最大許容時間 | 60分 | 超過時はWARNINGログを出力してFinalizeを強制実行 |
| NFR-06 | 各エージェント呼び出しタイムアウト | 120秒 | タイムアウト時はリトライ1回、失敗時はスキップしてログ記録 |

### 3.3 セッション断絶耐性

| ID | 要件 | 説明 |
|---|---|---|
| NFR-07 | チェックポイントによる再開 | `checkpoint.json` の `next_action` フィールドを参照し、中断したフェーズから再開できること |
| NFR-08 | 再開時のデータ整合性 | セッション再開時に既存の `knowledge/`, `style_memory/` データを引き継ぐこと。`output/` と `agent_memory/` は再開時にクリアしない |
| NFR-09 | 再開コマンド | ユーザーが明示的な再開指示なく `checkpoint.json` が存在する場合、Leadが自動で再開フローへ誘導すること |
| NFR-10 | 最大セッション再開回数 | 1ランにつき無制限（チェックポイントが正常に更新されている限り） |

### 3.4 並列禁止

| ID | 要件 | 説明 |
|---|---|---|
| NFR-11 | エージェントの逐次実行 | 全エージェント呼び出しは逐次実行とし、並列呼び出しを行わないこと |
| NFR-12 | ファイル書き込みの排他制御 | 同一ファイルへの同時書き込みが発生しないよう、PDCAループ内でのファイルI/Oは単一スレッドで実行すること |
| NFR-13 | 禁止理由 | Claude Code Skillアーキテクチャの制約上、並列エージェント実行は状態管理の複雑性を増大させ、デバッグコストが著しく高まるため |

---

## 4. Leadの権限範囲

### 4.1 自発判断OK

Leadエージェント（Orchestrator）が人間の確認なしに自律的に実行してよい判断・操作を以下に定義する。

| # | 判断・操作 | 条件 |
|---|---|---|
| 1 | 次フェーズへの進行 | チェックポイントの `next_action` に従う場合 |
| 2 | イテレーション内でのWriter再呼び出し | スコアが閾値未満かつ上限イテレーション未到達の場合 |
| 3 | HARDFAILキャップの適用 | `metrics.py` の判定に従う場合（LLM評価を上書き） |
| 4 | 停滞検出後のギャップアラート生成と次イテレーションへの注入 | `stagnation_check.py` が停滞を検出した場合 |
| 5 | MATERIAL_FALLBACKの発動 | 記事スコアが3イテレーション後に0.70未満の場合 |
| 6 | タイムアウト後の強制Finalize | NFR-05の最大許容時間超過時 |
| 7 | Sonnetへのフォールバック | Opus呼び出し回数がNFR-01上限に達した場合 |
| 8 | `output/` `agent_memory/` ディレクトリのリセット（ラン開始時） | 新規ランの開始時 |
| 9 | `fb_log.json` の初期化（ラン開始時） | 新規ランの開始時 |

### 4.2 人間確認必須

以下の判断・操作は実行前に必ず人間の確認（ユーザーへの質問）を得ること。

| # | 判断・操作 | 理由 |
|---|---|---|
| 1 | 記事テーマ・キーワードの変更 | ユーザーの意図と乖離するリスクがあるため |
| 2 | `style_memory/style_guide.md` の全削除・初期化 | 累積的な学習データの喪失が不可逆なため |
| 3 | MATERIAL_FALLBACKの2回目以降の発動 | 1ランにつき1回上限を超えた追加バックトラックは設計外のため |
| 4 | 最大イテレーション数の引き上げ（NFR設計値を超える変更） | コスト・時間への影響が大きいため |
| 5 | 成果物（`output/` 内のファイル）の削除 | 生成物の喪失が不可逆なため |
| 6 | 外部APIや外部サービスへのデータ送信 | セキュリティ・プライバシーの観点から |

---

## 5. 成功基準DoD

### 5.1 技術

| # | 基準 | 判定方法 |
|---|---|---|
| T-01 | 全6個のBug (#1〜#6) が修正されていること | 各Bugに対するユニットテストが存在し、PASSすること |
| T-02 | `checkpoint.json` を使ったセッション再開が動作すること | 素材PDCAフェーズ完了後に中断し、再開して記事PDCAから継続できること |
| T-03 | HARDFAILキャップが正しく発動すること | `code_ratio=25%` のテスト入力に対してスコアが0.60になること |
| T-04 | 停滞検出が正しく動作すること | 3イテレーション連続スコア変化なしでギャップアラートが生成されること |
| T-05 | `fb_log.json` のdiffsが空でないこと | 2イテレーション以上実行後にdiffs配列に1件以上のエントリが存在すること |
| T-06 | エージェント数が11であること | INSTRUCTIONS.md内のエージェント定義数をカウントして確認 |
| T-07 | ディレクトリリセットが正しく動作すること | 前回ランの残存ファイルが新規ラン後の `output/` に存在しないこと |

### 5.2 品質

| # | 基準 | 判定方法 |
|---|---|---|
| Q-01 | 最終記事スコアが0.75以上 | ArticleReviewerの最終評価スコア |
| Q-02 | desu_masu_ratio（です・ます調比率）が80%以上 | `metrics.py` の `compute_article_metrics()` で計測 |
| Q-03 | code_ratio（コードブロック比率）が20%以下 | `metrics.py` の `compute_article_metrics()` で計測 |
| Q-04 | 記事文字数が2,000〜6,000字の範囲内 | `metrics.py` の `compute_article_metrics()` で計測 |
| Q-05 | Zennのfront-matter（title, emoji, type, topics, published）が全て存在すること | 正規表現によるファイル検査 |

### 5.3 ビジネス除外

以下はDoD（完了の定義）から除外する。

| # | 除外項目 | 理由 |
|---|---|---|
| B-01 | Zennトレンド入り・ビュー数・いいね数などのKPI | システム生成完了後の外部要因（投稿タイミング、タグ選択等）に依存するため |
| B-02 | SNSでのバズ・拡散数 | 同上 |
| B-03 | 読者からの具体的なフィードバック収集 | 自動化スコープ外 |

---

## 6. 既知リスクと受容可否

| # | リスク | 影響度 | 発生確率 | 受容可否 | 緩和策 |
|---|---|---|---|---|---|
| R-01 | LLM評価の揺らぎによるスコア不安定 | 中 | 高 | 受容 | HARDFAILキャップ（決定論的）で下限を保証 |
| R-02 | Claude Code Skill呼び出しのタイムアウト | 中 | 中 | 受容 | NFR-06のタイムアウト処理 + リトライ1回 |
| R-03 | チェックポイント破損によるセッション再開失敗 | 高 | 低 | 受容 | `checkpoint.json` の書き込みはアトミック操作（tmpファイル経由）で実装 |
| R-04 | Opusスポーン上限超過による品質低下 | 中 | 低 | 受容 | NFR-03に従いSonnetフォールバック。最終ArticleReviewerのみOpus確保 |
| R-05 | MATERIAL_FALLBACKループによる実行時間超過 | 高 | 低 | 受容 | NFR-05の最大許容時間（60分）に達した場合は強制Finalize |
| R-06 | `style_memory/style_guide.md` の肥大化 | 低 | 中 | 受容 | StyleGuideUpdaterが重複パターンを除去する仕様（FR-06） |
| R-07 | 停滞検出の誤検知（スコアが意図的に横ばいのケース） | 低 | 低 | 受容 | ギャップアラート注入はヒントに留め、改善の強制はしない |
| R-08 | v5.0からv5.1への移行時の設定ファイル非互換 | 中 | 中 | 受容 | 移行スクリプトを別途用意（本REQUIREMENTSのスコープ外） |
| R-09 | `_extract_sentences()` がYAML frontmatterと`---`区切り行を文として計上するデス・マス比率の構造バイアス | 中 | 高 | **未受容（Phase4修正対象）** | `_extract_sentences()` でfrontmatter行（`^---`、`^title:`等）と`---`区切り行を除外フィルタを追加する |
| R-10 | `_DESU_MASU_RE` がカバーできないです・ます終止パターン（`でしょうか。`、`ます（...）。`、体言止め等） | 中 | 高 | **未受容（Phase4修正対象）** | 正規表現パターンを拡張し、動詞が文末直前に来ないケースも検知する |
| R-11 | `fix_consecutive_length()` が文内複数文（`。`区切り）の連続同長問題を解消できない（行境界で処理するが`_extract_sentences()`は句点境界） | 中 | 高 | **未受容（Phase4修正対象）** | `fix_consecutive_length()` を句点境界で処理するよう変更、またはWriterへのプロンプトで根本防止する |
| R-12 | `advance_after_consolidate()` がConsolidator再レビュースコアで`best_article_score`を更新しないため`report.json`のスコアが旧値のまま | 低 | 中 | **未受容（Phase4修正対象）** | `advance_after_consolidate(state, new_score)` にスコア引数を追加し、`best_article_score`を更新する |
| R-13 | Article PDCA Step 6のdeath_patterns抽出ロジックがdict型feedbackに`in`演算子を使用し、常に空リストを返す | 低 | 高 | **未受容（Phase4修正対象）** | `f["text"]`へのアクセスに変更し、`"過多" in f["text"] or "NG" in f["text"]` とする |
| R-14 | Consolidator実行後のHARDFAILチェック欠如——Consolidatorが生成した記事に新たなHARDFAIL条件が発生しても未検知 | 高 | 中 | **未受容（Phase4修正対象）** | zenn-orchestratorのINSTRUCTIONS.mdに`consolidate`完了後にHARDFAILチェック＋修正ステップを追加する |
| R-15 | ArticleReviewerのJSON出力キー名揺れ（`weighted_average` vs `weighted_average_raw`）によるKeyErrorリスク | 中 | 中 | **未受容（Phase4修正対象）** | orchestratorのスコア読み取りを`review.get('weighted_average', review.get('weighted_average_raw', 0.0))`で防御的に実装、かつreview.json書き込み時のスキーマバリデーションを追加する |
| R-16 | HARDFAILキャップ値（0.55）がMATERIAL_FALLBACK閾値（0.70）より低いため、指標バイアスでHARDFAILが連発するとフォールバックループに落ちる | 高 | 低 | **未受容（Phase4要検討）** | R-09〜R-11の根本修正を優先。修正後もリスクが残る場合は、HARDFAILキャップ値をMATERIAL_FALLBACK閾値より低く保つか、HARDFAIL発動時はMATERIAL_FALLBACKカウント対象外とするかを設計判断する |

---

## 7. v5.0からの変更点サマリー（トレーサビリティ表）

| v5.0 FR番号 | v5.0 機能名 | v5.1 ステータス | v5.1 対応FR / 備考 |
|---|---|---|---|
| FR-01 | トレンド収集フェーズ | **継承** | FR-01（変更なし） |
| FR-02 | 読者ペインポイント抽出フェーズ | **継承** | FR-02（変更なし） |
| FR-03 | 記事論点設計フェーズ | **継承** | FR-03（変更なし） |
| FR-04 | 素材生成PDCAフェーズ（基本動作） | **継承** | FR-04（基本仕様は維持） |
| FR-04b | `check_resource_limits()` 呼び出し | **変更** | FR-04(変更)、Bug #2修正。各イテレーション開始時に呼び出しを追加 |
| FR-05 | 記事生成PDCAフェーズ（基本動作） | **継承** | FR-05（基本仕様は維持） |
| FR-05b | `check_resource_limits()` 呼び出し | **変更** | FR-05(変更)、Bug #2修正。各イテレーション開始時に呼び出しを追加 |
| FR-06 | スタイルガイド更新 | **継承** | FR-06（変更なし） |
| FR-07 | HARDFAILキャップ適用 | **継承** | FR-07（変更なし） |
| FR-08 | フィードバックログ永続化（diffs空問題） | **変更** | FR-08(変更)、Bug #1修正。diffsに算出値を渡すよう修正 |
| FR-08b | `fb_log.json` ランごとリセット | **変更** | FR-08(変更)、Bug #5修正。ラン開始時に初期化を追加 |
| FR-09 | エージェントメモリ管理（review_history） | **変更** | FR-09(変更)、Bug #6修正。PDCAがtupleを返すよう変更 |
| FR-10 | コンソリデーション＆最終化 | **継承** | FR-10（変更なし） |
| FR-10b | ディレクトリリセット処理 | **変更** | FR-10(変更)、Bug #4修正。shutil.rmtree後にmakedirsを実行 |
| FR-11 | 実行レポート出力 | **継承** | FR-11（変更なし） |
| FR-12 | MATERIAL_FALLBACKトリガー | **継承** | FR-12（変更なし） |
| FR-13 | "Review materials"の3ワードプロンプト問題 | **変更** | Bug #3修正。meta_agents.pyの正規プロンプトを使用するよう修正 |
| FR-A1 | Agent Editorによるワークフロー動的編集 | **廃止** | ワークフローをINSTRUCTIONS.mdに固定 |
| FR-A2 | MetaReviewerによる独立メタレビュー | **廃止** | 記事PDCAロジックに統合 |
| FR-A3 | Anthropic SDK直接呼び出し | **廃止** | Claude Code Skillアーキテクチャへ完全移行 |
| FR-A4 | 動的プロンプト文字列テンプレート | **廃止** | INSTRUCTIONS.md固定定義方式へ移行 |
| — | 停滞検出（Stagnation Detection） | **新設** | FR-NEW-01、`stagnation_check.py` |
| — | ギャップアラート生成（Gap Alert） | **新設** | FR-NEW-02、`gap_alert.py` |
| — | チェックポイント管理（Checkpoint） | **新設** | FR-NEW-03、`checkpoint.py`、`next_action` フィールド |
| — | メタエージェント簡素化 | **新設** | FR-NEW-04、Strategist + Eval Designerのみに集約 |

### 変更点サマリー統計

| ステータス | 件数 |
|---|---|
| 継承（変更なし） | 8件 |
| 変更（Bug修正・仕様変更含む） | 7件 |
| 廃止 | 4件 |
| 新設 | 4件 |
| **合計** | **23件** |

---

## 8. Phase 4 未修正バグ一覧（2026-04-20 E2E実行で発見）

> **発見日**: 2026-04-20  
> **発見契機**: `fix/phase1-code-corrections` ブランチでのフルE2E実行  
> **修正ターゲット**: Phase 4（次期修正サイクル）  
> **技術詳細**: `TECH_SPEC.md` セクション 8 を参照

| Bug ID | 対象ファイル | 問題の概要 | 影響 | REQUIREMENTS対応 |
|---|---|---|---|---|
| Bug-A1 | `metrics.py` / `_extract_sentences()` | YAMLfrontmatter・`---`行を文として計上しデス・マス比率を過小算出 | desu_masu HARDFAILが不当に頻発 | R-09 |
| Bug-A2 | `metrics.py` / `_DESU_MASU_RE` | `でしょうか`、`ます（...）。`等のパターンを未検知 | デス・マス文の取りこぼしで比率が低く出る | R-10 |
| Bug-A3 | `metrics.py` / `fix_consecutive_length()` | 行境界で処理するが`_extract_sentences()`は句点境界のため機能しない | consecutive_same_length修正が無効 | R-11 |
| Bug-B1 | `checkpoint.py` / `advance_after_consolidate()` | Consolidator後の再レビュースコアで`best_article_score`を更新しない | `report.json`のスコアが実際より低い値になる | R-12 |
| Bug-C1 | `zenn-article-pdca/INSTRUCTIONS.md` Step 6 | feedbackリストのdict要素に`in`演算子を誤用しdeath_patternsが常に空 | エージェントメモリに死亡パターンが蓄積されない | R-13 |
| Bug-C2 | `zenn-orchestrator/INSTRUCTIONS.md` | Consolidator後のHARDFAILチェックが欠如 | Consolidator生成記事のHARDFAIL見逃し | R-14 |
| Bug-D1 | `agents/article_reviewer.md` | `weighted_average` vs `weighted_average_raw` キー名揺れ | KeyErrorリスク・スコア読み取り失敗 | R-15 |
| Bug-E1 | `metrics.py` + `checkpoint.py` | HARDFAILキャップ(0.55) < MATERIAL_FALLBACK閾値(0.70)の論理矛盾 | Bug-A1-A2存在下で意図しないFALLBACKループ誘発リスク | R-16 |

---

*本ドキュメントはv5.1の実装開始前に確定されたREQUIREMENTSである。変更が生じた場合はバージョン番号をインクリメントし、変更者・変更日・変更理由を末尾に追記すること。*
