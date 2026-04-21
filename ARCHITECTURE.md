# ARCHITECTURE.md — Zenn記事自動生成システム v5.1

> バージョン: 5.1 | 作成日: 2026-04-20 | 方式: Claude Code Skillbase

---

## 1. システム概要

### 目的

Zenn向けの技術記事を、人間の指示から完成原稿まで自動生成するエンドツーエンドシステム。
Claude Code のサブスクリプション内で完結し、別途 API 課金は発生しない。

### v5.0 からの主な変更点

| 項目 | v5.0 | v5.1 |
|------|------|------|
| 実行基盤 | Anthropic API (別課金) | Claude Code Subscription内 |
| 実装形式 | スクリプト群 | Claude Code Skill (3スキル) |
| エージェント数 | 15 | 11（統廃合） |
| Layer 1 構成 | Strategist + EvalDesigner + AgentEditor + MetaReviewer | Strategist + EvalDesigner のみ |
| AgentEditor | ワークフロー動的生成 | 廃止 → INSTRUCTIONS.md に固定 |
| MetaReviewer | 独立エージェント | 廃止 → Article PDCA に統合 |
| セッション管理 | なし | checkpoint.json による状態機械 |
| スタグネーション検知 | なし | stagnation_check.py (3回連続停滞) |
| ギャップアラート | なし | gap_alert.py (閾値差分の明示) |
| Material Fallback | なし | Article PDCA iter3+ でスコア < 0.70 時に逆流 |

---

## 2. ディレクトリ構造

```
/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/
├── ARCHITECTURE.md              ← 本ファイル
├── .claude/
│   ├── skills/
│   │   ├── zenn-orchestrator/
│   │   │   ├── SKILL.md         ← スキル宣言（トリガー条件・概要）
│   │   │   └── INSTRUCTIONS.md  ← Lead の実行手順（チェックポイント読み込み→ディスパッチ）
│   │   ├── zenn-material-pdca/
│   │   │   ├── SKILL.md
│   │   │   └── INSTRUCTIONS.md  ← Material PDCA の実行手順（最大5イテレーション）
│   │   └── zenn-article-pdca/
│   │       ├── SKILL.md
│   │       └── INSTRUCTIONS.md  ← Article PDCA の実行手順（最大10イテレーション）
│   └── scripts/
│       ├── file_registry.py     ← Paths クラス（25パス定数）
│       ├── metrics.py           ← スコア計算・HARD FAIL チェック
│       ├── fb_log.py            ← フィードバックログ読み書き・差分・停滞
│       ├── stagnation_check.py  ← NEW: 3回連続停滞検知
│       ├── gap_alert.py         ← NEW: ギャップ計算・アラートメッセージ生成
│       └── checkpoint.py        ← NEW: チェックポイント読み書き・ルーティング
└── output/                      ← 生成物（下記 §7 参照）
```

---

## 3. スキル構成

### 3.1 zenn-orchestrator（Lead スキル）

**役割**: システム全体の司令塔。`checkpoint.json` を読み込み、`next_action` フィールドに基づいて次フェーズへディスパッチする。

**責務**:
- Layer 1（Strategist + EvalDesigner）を初回のみ実行
- `checkpoint.json` の更新と一貫性保証
- `zenn-material-pdca` / `zenn-article-pdca` の呼び出し判断
- セッション断絶後の再開ルーティング
- 完了時の stdout JSON 出力

**INSTRUCTIONS.md の構成**:
```
1. checkpoint.py で現在状態を読む
2. next_action に応じて分岐
   - run_strategist     → Layer 1 Strategist を起動
   - run_eval_designer  → Layer 1 EvalDesigner を起動（human-bench/ 必読）
   - run_system_analyst → SystemAnalyst を起動（条件付き、requires_system_analysis=true 時のみ）
   - run_material_iter  → zenn-material-pdca を呼ぶ
   - run_article_iter   → zenn-article-pdca を呼ぶ
   - material_fallback  → iterations/ をアーカイブ後 checkpoint を material_pdca に戻す
   - consolidate        → Consolidator → 再 Review（iter >= 3 + 閾値通過 or iter 10 時のみ）
   - finalize           → Finalizer エージェントを呼ぶ
3. 完了後に checkpoint を更新して再ループ
```

### 3.2 zenn-material-pdca（素材収集フェーズ）

**役割**: トレンド調査・読者ペイン抽出・論点設計・素材レビューを PDCA ループで実行。

**責務**:
- Phase 0: TrendResearcher + PainExtractor を並列実行
- Phase 1: ThesisDesigner でテーゼを確定
- Phase 2: MaterialReviewer でスコアリング（閾値 0.85）
- スコア・フィードバックを `fb_log.json` に記録
- 5イテレーション上限でベストスコアを持って次フェーズへ

### 3.3 zenn-article-pdca（記事執筆フェーズ）

**役割**: 記事ドラフト作成・スタイル更新・レビュー・統合・完成を PDCA ループで実行。

**責務**:
- Phase 3a: Writer + StyleGuideUpdater（ドラフト + スタイルガイド更新）
- Phase 3b: ArticleReviewer でスコアリング（閾値 0.80、`apply_hard_fail` + `apply_major_penalty` で cap 適用）
- iter3+ でスコア < 0.70 → MATERIAL_FALLBACK をトリガー
- スコア >= 0.80 かつ iter < 3 → 直接 Finalizer
- スコア >= 0.80 かつ iter >= 3、または iter == 10 → Consolidator 経由 → 再 Review → Finalizer
- Consolidator 起動は orchestrator 側の `consolidate` ステージ（このスキル内で直接 spawn しない）

---

## 4. エージェント一覧（11エージェント）

| # | エージェント | レイヤー/フェーズ | 入力 | 出力 | 並列可否 |
|---|------------|----------------|------|------|---------|
| 1 | Strategist | Layer 1 | ユーザー指示 | `strategy.md`（`requires_system_analysis` frontmatter 必須） | 不可 |
| 2 | EvalDesigner | Layer 1 | `strategy.md` + `human-bench/` | `eval_criteria.md` | 不可（Strategist後） |
| 3 | SystemAnalyst | Layer 1（条件付き） | `strategy.md` + 対象ディレクトリ | `knowledge/system_analysis.md` | 不可。`requires_system_analysis=true` の時のみ EvalDesigner 後に起動 |
| 4 | TrendResearcher | Phase 0 | `strategy.md` | `knowledge/trends.md` | **PainExtractorと並列** |
| 5 | PainExtractor | Phase 0 | `strategy.md` | `knowledge/reader_pains.md` | **TrendResearcherと並列** |
| 6 | ThesisDesigner | Phase 1 | trends.md + reader_pains.md + system_analysis.md（あれば） | `thesis.md` | 不可 |
| 7 | MaterialReviewer | Phase 2 | thesis.md + eval_criteria.md + human-bench | `material_reviews/{iter}/review.json` + スコア | 不可 |
| 8 | Writer | Phase 3a | thesis.md + system_analysis.md（あれば）+ style_guide.md + memory.json | `iterations/{iter}/article.md` | 不可 |
| 9 | StyleGuideUpdater | Phase 3a | article.md + fb_log.json | `style_memory/style_guide.md` | Writerの直後 |
| 10 | ArticleReviewer | Phase 3b | article.md + eval_criteria.md + human-bench | `iterations/{iter}/review.json` + スコア | 不可 |
| 11 | Consolidator | orchestrator の consolidate ステージ | iterations/1..N/article.md + review.json | `iterations/{best_N}/article.md`（統合版で上書き） | 不可 |
| 12 | Finalizer | orchestrator の finalize ステージ | iterations/{best_N}/article.md + style_guide.md | `final_article.md` + `report.json` | 不可 |

起動条件は v5.1 で以下のように変更:
- **SystemAnalyst**: `strategy.md` frontmatter の `requires_system_analysis: true` の場合のみ（FIX-B-1）
- **Consolidator**: `article_iter >= 3 AND (score >= 0.80 OR iter == 10)`（旧 iter==5 固定から変更、FIX-D-3）

> **注**: PDCA 1イテレーション内はすべて逐次実行（write → review → score）。
> 例外として Phase 0 の TrendResearcher + PainExtractor のみ並列実行可。

---

## 5. 実行フロー

### 全体概略図

```
┌─────────────────────────────────────────────────────────┐
│                  zenn-orchestrator                       │
│                 (checkpoint.json 管理)                   │
└──────────────────────┬──────────────────────────────────┘
                       │ next_action = run_strategist
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 1 （初回のみ）                                    │
│  Strategist → strategy.md (requires_system_analysis含む) │
│  EvalDesigner(+ human-bench/) → eval_criteria.md        │
│  [requires_system_analysis=true のみ]                   │
│    SystemAnalyst → knowledge/system_analysis.md         │
└──────────────────────┬──────────────────────────────────┘
                       │ next_action = run_topic_selector
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Topic Selection（初回のみ）                              │
│  TrendResearcher → knowledge/trends.md                  │
│  TopicProposer + TopicFinalizer → topic.md              │
└──────────────────────┬──────────────────────────────────┘
                       │ next_action = run_experience_author
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Experience Authoring（初回のみ・v5.2 NEW）              │
│  ExperienceAuthor → knowledge/experience_log.md         │
│  （著者の生々しい経験ログを一次情報源として記録）        │
└──────────────────────┬──────────────────────────────────┘
                       │ next_action = run_material_iter
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Material PDCA  【zenn-material-pdca】                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Phase 0: TrendResearcher ‖ PainExtractor        │   │
│  │ Phase 1: ThesisDesigner                         │   │
│  │ Phase 2: MaterialReviewer → score               │   │
│  │   score >= 0.85 → PROCEED                       │   │
│  │   iter >= 5     → PROCEED (best score)          │   │
│  │   else          → 次イテレーション              │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │ next_action = run_article_iter
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Article PDCA  【zenn-article-pdca】                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Phase 3a: Writer → iterations/{iter}/article.md │   │
│  │           StyleGuideUpdater → style_guide.md    │   │
│  │ Phase 3b: ArticleReviewer → review.json         │   │
│  │           apply_hard_fail + apply_major_penalty │   │
│  │   score >= 0.80 && iter < 3                     │   │
│  │       → Finalizer → DONE                        │   │
│  │   score >= 0.80 && iter >= 3                    │   │
│  │       → Consolidator → 再 Review → Finalizer    │   │
│  │   iter == 10   → Consolidator → Finalizer       │   │
│  │   iter >= 3 && score < 0.70                     │   │
│  │       → MATERIAL_FALLBACK (最大2回)             │   │
│  │   else → 次イテレーション                       │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
              final_article.md + report.json
              stdout: {"status":"done", ...}
```

### 5.1 Layer 1（初回のみ）

```
checkpoint.next_action == "run_strategist"
    ↓
Strategist(ユーザー指示) → output/strategy.md
  （先頭 frontmatter に requires_system_analysis: true/false）
    ↓
EvalDesigner(strategy.md + human-bench/) → output/eval_criteria.md
  （## ベンチマーク セクションに参照ベンチ記事 ID を最低3件明記）
    ↓
[requires_system_analysis == true のみ]
SystemAnalyst(strategy.md + 対象ディレクトリ) → output/knowledge/system_analysis.md
    ↓
checkpoint 更新: phase="material_pdca", next_action="run_material_iter"
```

- Strategist は記事テーマ・対象読者・差別化ポイントを `strategy.md` に書き出す。`requires_system_analysis` フラグも必ず出力
- EvalDesigner は `strategy.md` と `human-bench/` のベンチマーク記事 3-4 本を読み、自己参照を避けた評価軸を `eval_criteria.md` に定義（v5.1 FIX-D-1）
- SystemAnalyst は `requires_system_analysis=true` の時のみ起動し、記事対象システムの設計解説を `system_analysis.md` に書き出す。ThesisDesigner / Writer が後続で参照（v5.1 FIX-B-1）

### 5.1.5 Topic Selection（初回のみ）

```
checkpoint.next_action == "run_topic_selector"
    ↓
zenn-topic-selection skill 起動
  Step 1: TrendResearcher → knowledge/trends.md
  Step 2: TopicProposer  → 候補 5 案（中間・非永続化）
  Step 3: TopicFinalizer → topic.md（6 軸採点で選定）
    ↓
checkpoint 更新: phase="experience_authoring", next_action="run_experience_author"
```

### 5.1.8 Experience Authoring（初回のみ・v5.2 NEW）

```
checkpoint.next_action == "run_experience_author"
    ↓
ExperienceAuthor(strategy.md + trends.md + system_analysis.md + topic.md + eval_criteria.md)
  ├─ Phase 1: Director 準備（system_analysis / topic から罠抽出 → 事件 2-3 個選定）
  ├─ Phase 2: Drama 実行（3 役 × 8 ターン → drama_raw.md に逐次追記）
  └─ Phase 3: ログ圧縮（drama_raw.md → experience_log.md）
  → output/knowledge/drama_raw.md        （3 役対話の生ログ）
  → output/knowledge/experience_log.md   （圧縮版・下流入力）
    ↓
checkpoint 更新: phase="material_pdca", next_action="run_material_iter"
```

- **目的**: Material PDCA が LLM 想像による一人称挿話を捏造する病を断つ。著者の生々しい経験を一次情報源として外部化し、ThesisDesigner が必ずこのファイルから引用する運用にする
- **実装方式（v5.2.1 NEW）**: **Multi-Agent Drama Simulation**（Option E）を採用。3 役（Human / Claude / Director）を 1 プロンプト内で演じ分け、情報非対称性（Claude はノーヒント・Director が罠を仕込む・Human はプロエンジニアで題材システム固有の罠は未知）を契約として守らせる。8 ターン目安で事件 2-3 個を発火させ、試行錯誤のログを `drama_raw.md` に蓄積、その圧縮が `experience_log.md`
- **Phase 1 の主題収束機構（v5.2.2 NEW）**: 事件が水平に散って主題が二股に割れる問題への対策。Phase 1.0 で Director が「中心学び 1 文」を先決めし、Phase 1.1 で罠候補に L1（表層） / L2（運用ほつれ） / L3（設計原理の葛藤） の severity を付けて**中心学びに奉仕する罠のみ**を抽出、Phase 1.2 で事件を**表層 → 中層 → 底層の 3 層連鎖**として並べる。ゲート: 最低 1 個は L3、L1 単独事件は却下、中心学びと論点がずれる罠は `## 使わない素材` 行き
- **Topic Selection と 中心学び の階層関係（v5.2.2 NEW）**: 中心学び は独立に発明しない。Topic Selection で既に決まっている `selected_title` / `key_tension` / `deep_dive_targets` から**導出**する契約。
  - `selected_title` = 記事のナラティブフレーム（何について書くか）
  - `key_tension` = 記事が扱う抽象的緊張
  - `deep_dive_targets` = 深掘り対象の具体リスト
  - **中心学び** = 上記を drama で実証する 1 文アサーションに鋳直したもの
  - Fitness Check: Director は `drama_raw.md` 冒頭に「key_tension の解消/精緻化の仕方」「巻き込む deep_dive_target（1-3 個）」「selected_title との整合」を明記する義務あり。埋められない 中心学び は採用不可
- **検討された代替案**: Option A（著者対話）/ B（git・PR mining）/ C（単発 Synthesis）/ D（B+A Hybrid）。A/D は著者手作業コスト、B は一次資料アクセス前提、C は AI 臭の温床と判断し、情報非対称で構造化シミュレーションする E を採用
- **入力**: Topic Selection までに生成された全ファイル（reader_pains.md は Material PDCA 内部生成のため含まない）
- **出力**: `knowledge/experience_log.md`（固定テンプレート準拠・下流入力）+ `knowledge/drama_raw.md`（副産物・下流は読まない）
- **失敗時**: 3 回 retry 後スキップし、`experience_log.md` 無しで Material PDCA に進む。ThesisDesigner 側は「存在する場合のみ」扱いなので動作継続可能（`report.json.degraded_mode=true` で記録）
- ThesisDesigner / Writer / MaterialReviewer への直接入力は **ThesisDesigner のみ**（Writer は thesis.md 経由で間接的に受け取る。案A・単一 source of truth 維持）

### 5.2 Material PDCA

```
[iter=1..5]
  Phase 0（並列）:
    TrendResearcher → knowledge/trends.md   （Webサーチ必須）
    PainExtractor   → knowledge/reader_pains.md
  Phase 1:
    ThesisDesigner  → thesis.md   （前回フィードバック反映）
  Phase 2:
    MaterialReviewer → materials/material_review.json
                     → score (0.0~1.0)
  fb_log.py.record(iter, score, feedback)
  if score >= 0.85:
    → PROCEED to Article PDCA
  elif iter >= 5:
    → PROCEED with best_material_score
  else:
    → 次イテレーション（stagnation_check → gap_alert）
```

**停滞時の挙動**: 3回連続でスコアが改善しない場合、`gap_alert.py` が現スコアと閾値のギャップを具体的にフィードバックとして添付し、次イテレーションの Writer に渡す。

### 5.3 Article PDCA

```
[iter=1..10]
  Phase 3a:
    Writer → iterations/{iter}/article.md
             （thesis.md + system_analysis.md（あれば）+ style_guide.md
               + agent_memory/memory.json + 前 iter の article/review.json 参照）
    HARD FAIL check: fix_code_ratio / fix_desu_masu / fix_consecutive_length を適用
    StyleGuideUpdater → style_memory/style_guide.md 更新
  Phase 3b:
    ArticleReviewer(human-bench/ 必読) → iterations/{iter}/review.json
    raw_score = review.weighted_average
    after_hf = apply_hard_fail(raw_score, hard_fail_result)
    final_score = apply_major_penalty(after_hf, major_count)
  fb_log: load_fb_log → record_fb → append_fb_diff
  if final_score >= 0.80 and iter < 3:
    → Finalizer → DONE（Consolidator skip）
  elif final_score >= 0.80 and iter >= 3:
    → Consolidator → ArticleReviewer 再 spawn → Finalizer → DONE
  elif iter == 10:
    → Consolidator → Finalizer (best_N) → DONE
  elif iter >= 3 and final_score < 0.70:
    → MATERIAL_FALLBACK（material_fallback_count < 2 の場合）
  else:
    → 次イテレーション（stagnation_check → gap_alert）
```

### 5.4 MATERIAL_FALLBACK

```
Article PDCA iter >= 3 && score < 0.70 && material_fallback_count < 2
    ↓
orchestrator: output/iterations/ → output/iterations_fallback_{count}/ にアーカイブ
    ↓
trigger_material_fallback(cp):
  phase = "material_pdca"
  next_action = "run_material_iter"
  material_iter = 0
  article_iter = 0           ← リセット（記事側もやり直し）
  best_article_iter = None   ← リセット（古い iter を finalize しないため、FIX-B-2）
  best_article_score = 0.0   ← リセット
  material_fallback_count += 1
    ↓
Material PDCA を再実行（新しいトレンド・ペインから再取得）
    ↓
Article PDCA へ再突入
```

- MATERIAL_FALLBACK は最大 **2回** まで。3回目は無視して Article PDCA を継続。
- フォールバック後は `best_material_score` を更新し、より良い素材を使用。
- フォールバック前の iter は `iterations_fallback_1/`, `iterations_fallback_2/` に保全される（デバッグ用）。

### 5.5 セッション断絶回復

```
セッション開始時（どのスキルでも）:
    ↓
checkpoint.py.read_checkpoint()
    ↓
next_action に基づいてルーティング:
  "run_strategist"     → Layer 1 Strategist から再開
  "run_eval_designer"  → Layer 1 EvalDesigner から再開
  "run_system_analyst" → SystemAnalyst から再開（requires_system_analysis=true の時）
  "run_material_iter"  → Material PDCA の current iter から再開
  "run_article_iter"   → Article PDCA の current iter から再開
  "material_fallback"  → iterations/ アーカイブ + フォールバック処理から再開
  "consolidate"        → Consolidator → 再 Review から再開
  "finalize"           → Finalizer から再開
```

- 完了済みのイテレーションは再実行しない
- `material_iter` / `article_iter` が示すイテレーション番号から再開
- 中断したイテレーションは最初から再実行（ファイルが存在しても上書き）

---

## 6. checkpoint.json スキーマ

### ファイルパス

`output/checkpoint.json`

### スキーマ定義

```json
{
  "phase": "layer1 | topic_selection | experience_authoring | material_pdca | article_pdca | done",
  "next_action": "run_strategist | run_eval_designer | run_system_analyst | run_topic_selector | run_experience_author | run_material_iter | run_article_iter | material_fallback | consolidate | finalize | done",
  "material_iter": 0,
  "article_iter": 0,
  "best_material_score": 0.0,
  "best_article_score": 0.0,
  "best_material_iter": null,
  "best_article_iter": null,
  "material_fallback_count": 0,
  "last_updated": "2026-04-20T12:34:56+09:00"
}
```

> v5.2 で `experience_authoring` phase と `run_experience_author` / `run_topic_selector` next_action が VALID_TRANSITIONS に正式追加された（checkpoint.py:28-35）。既存 ran の checkpoint.json（v5.1 まで）は新 phase を踏まないため、中断ランの再開時は手動で next_action を書き換えるか FRESH_STATE から再実行する。

### フィールド説明

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `phase` | string | 現在のフェーズ識別子 |
| `next_action` | string | Lead が次に取るべきアクション |
| `material_iter` | int | Material PDCA の現在イテレーション番号（1始まり） |
| `article_iter` | int | Article PDCA の現在イテレーション番号（1始まり） |
| `best_material_score` | float | Material PDCA 全イテレーション中の最高スコア |
| `best_article_score` | float | Article PDCA 全イテレーション中の最高スコア（MATERIAL_FALLBACK で 0.0 にリセット） |
| `best_material_iter` | int \| null | Material PDCA 最高スコアの iter 番号 |
| `best_article_iter` | int \| null | Article PDCA 最高スコアの iter 番号（MATERIAL_FALLBACK で null にリセット、FIX-B-2） |
| `material_fallback_count` | int | MATERIAL_FALLBACK が発動した累計回数（0〜2） |
| `last_updated` | ISO8601 | 最終更新日時 |

### 状態遷移図

```
初期値 → run_strategist
    ↓
run_eval_designer
    ↓ requires_system_analysis=true の時のみ
run_system_analyst
    ↓
run_topic_selector                          (phase=topic_selection)
    ↓
run_experience_author  (v5.2 NEW)           (phase=experience_authoring)
    ↓
run_material_iter (material_iter++)         (phase=material_pdca)
    ↓ score >= 0.85 or iter >= 5
run_article_iter (article_iter++)
    ↓ iter >= 3 && score < 0.70
material_fallback → run_material_iter
    (material_iter=0, article_iter=0, best_article_*=null, fallback_count++)
    ↓ score >= 0.80 && iter < 3
finalize → phase="done"
    ↑
    ↓ score >= 0.80 && iter >= 3 / または iter >= 10
consolidate (Consolidator + 再 Review) → finalize → phase="done"
```

---

## 7. ファイルレジストリ

### output/ ディレクトリツリー

実際のパスは `.claude/scripts/file_registry.py` の `Paths` クラスが唯一の情報源。

```
output/
├── strategy.md                       # Strategist 出力（requires_system_analysis frontmatter 含む）
├── eval_criteria.md                  # EvalDesigner 出力（## ベンチマーク に human-bench 参照必須）
├── knowledge/
│   ├── trends.md                     # TrendResearcher 出力（Topic Selection）
│   ├── reader_pains.md               # PainExtractor 出力（Material PDCA iter 1 内部生成）
│   ├── experience_log.md             # ExperienceAuthor 出力（v5.2 NEW・著者の生々しい経験・Drama 圧縮版）
│   ├── drama_raw.md                  # ExperienceAuthor 副産物（v5.2.1 NEW・3 役対話の生ログ）
│   └── system_analysis.md            # SystemAnalyst 出力（条件付き生成）
├── topic.md                          # TopicFinalizer 出力（Topic Selection）
├── thesis.md                         # ThesisDesigner 出力（各 iter で上書き）
├── thesis_history/
│   └── {iter}.md                     # 各 iter の thesis.md スナップショット（iter >= 2 から）
├── material_reviews/
│   └── {iter}/review.json            # MaterialReviewer 出力。{axes, weighted_average, feedback}
├── iterations/
│   └── {N}/
│       ├── article.md                # Writer 出力
│       └── review.json               # ArticleReviewer 出力
├── iterations_fallback_{count}/      # MATERIAL_FALLBACK 時のアーカイブ
├── style_memory/
│   └── style_guide.md                # StyleGuideUpdater 累積更新
├── agent_memory/
│   └── memory.json                   # Writer 軸別記憶
├── fb_log.json                       # 全イテレーションの FB ログ（entries + diffs）
├── checkpoint.json                   # 状態機械チェックポイント（§6 参照）
├── final_article.md                  # Finalizer 出力
└── report.json                       # Finalizer 出力（stdout にも出力）
```

### 各ファイルの説明

| ファイル | 更新タイミング | 内容 |
|---------|--------------|------|
| `strategy.md` | Layer 1 のみ | 記事の方向性・読者ペルソナ・差別化軸・`requires_system_analysis` flag |
| `eval_criteria.md` | Layer 1 のみ | 軸別評価基準 + `## ベンチマーク` セクション（human-bench 記事 ID 必須） |
| `knowledge/system_analysis.md` | Layer 1（条件付き） | SystemAnalyst が対象ディレクトリを解析した設計解説 |
| `knowledge/trends.md` | Topic Selection + 各フォールバック後 | Webサーチによる最新動向（上書き） |
| `topic.md` | Topic Selection | TopicFinalizer が 6 軸採点で選定した 1 案（selected_title / scope / deep_dive_targets 等） |
| `knowledge/experience_log.md` | Experience Authoring（初回のみ・v5.2 NEW） | 著者の生々しい経験ログ（数値で驚いたこと / ハマったこと等・固定テンプレ）。Drama Simulation の圧縮版。ThesisDesigner の一次情報源。失敗時はスキップ可能 |
| `knowledge/drama_raw.md` | Experience Authoring（初回のみ・v5.2.1 NEW） | Multi-Agent Drama Simulation の 3 役対話生ログ。experience_log.md の出典であり、後日の再圧縮・デバッグ用。下流エージェントは読まない |
| `knowledge/reader_pains.md` | Material PDCA iter 1 + 各フォールバック後 | ペインポイント・よくある疑問（上書き） |
| `thesis.md` | Material PDCA 各 iter Phase 1 | 主張・構成・セクション骨子（上書き） |
| `thesis_history/{iter}.md` | Material PDCA iter >= 2 の spawn 前 | 前 iter の thesis スナップショット |
| `material_reviews/{iter}/review.json` | Material PDCA 各 iter Phase 2 | `{axes, weighted_average, feedback: [{axis, severity, text}]}` |
| `iterations/{N}/article.md` | Article PDCA 各 iter Phase 3a | Writer の出力（HARD FAIL 修正後の最終版） |
| `iterations/{N}/review.json` | Article PDCA 各 iter Phase 3b | `{axes, weighted_average, feedback, death_patterns_detected}` |
| `style_memory/style_guide.md` | Article PDCA 各 iter Phase 3a | 累積スタイル規則（追記更新） |
| `agent_memory/memory.json` | Article PDCA 各 iter（Writer 更新） | `{score_by_axis, death_patterns}` |
| `article_draft.md` | Article PDCA 各 iter Phase 3a / iter5 Consolidator | 現在最良ドラフト（上書き） |
| `article_review.json` | Article PDCA 各 iter Phase 3b | `{score, axis_scores, feedback, iter}` |
| `fb_log.json` | 全 iter 記録（追記） | `[{phase, iter, score, feedback, diff}]` |
| `checkpoint.json` | 各フェーズ完了時 | 状態機械（§6 参照） |
| `final_article.md` | Finalizer のみ | 最終記事（Zenn 投稿可能な Markdown） |
| `report.json` | Finalizer のみ | `{status, score, iterations, output_path}` |

---

## 8. Python スクリプト仕様

### 8.1 file_registry.py

```python
class Paths:
    """25個のパス定数を管理するクラス。v5.0 からコピー。"""
    
    BASE_DIR: Path          # プロジェクトルート
    OUTPUT_DIR: Path        # output/
    STRATEGY: Path          # output/strategy.md
    EVAL_CRITERIA: Path     # output/eval_criteria.md
    TRENDS: Path            # output/knowledge/trends.md
    READER_PAINS: Path      # output/knowledge/reader_pains.md
    THESIS: Path            # output/thesis.md
    MATERIAL_REVIEW: Path   # output/materials/material_review.json
    STYLE_GUIDE: Path       # output/style_memory/style_guide.md
    AGENT_MEMORY: Path      # output/agent_memory/memory.json
    ARTICLE_DRAFT: Path     # output/article_draft.md
    ARTICLE_REVIEW: Path    # output/article_review.json
    FB_LOG: Path            # output/fb_log.json
    CHECKPOINT: Path        # output/checkpoint.json
    FINAL_ARTICLE: Path     # output/final_article.md
    REPORT: Path            # output/report.json
    # ... （合計25定数）
    
    @classmethod
    def ensure_dirs(cls) -> None:
        """必要なディレクトリをすべて作成する"""
```

### 8.2 metrics.py

```python
def compute_article_metrics(draft_path: Path) -> dict:
    """
    記事ドラフトを解析し、各ハードフェイル指標を計算する。
    
    Returns:
        {
            "code_ratio": float,          # コードブロック文字数 / 総文字数
            "desu_masu_ratio": float,     # です・ます調の割合
            "max_consecutive_same_len": int  # 連続する同一長文の最大連続数
        }
    """

def check_hard_fail(metrics: dict) -> list[str]:
    """
    HARD FAIL 条件を検査する。
    
    Returns:
        triggered: list[str]  # 発動した HARD FAIL のリスト（空なら正常）
    
    Rules:
        code_ratio > 0.20 → "CODE_RATIO_EXCEEDED"
        desu_masu_ratio < 0.80 → "DESU_MASU_INSUFFICIENT"
        max_consecutive_same_len > 4 → "CONSECUTIVE_SAME_LENGTH"
    """

def apply_hard_fail(score: float, triggered: list[str]) -> float:
    """
    HARD FAIL が発動した場合にスコアにキャップを適用する。
    
    Rules:
        CODE_RATIO_EXCEEDED        → min(score, 0.60)
        DESU_MASU_INSUFFICIENT     → min(score, 0.55)
        CONSECUTIVE_SAME_LENGTH    → min(score, 0.50)
        複数発動時は最も厳しいキャップを適用
    
    Returns:
        capped_score: float
    """
```

### 8.3 fb_log.py

```python
def read_fb_log(path: Path) -> list[dict]:
    """fb_log.json を読み込む。ファイルがなければ空リストを返す。"""

def write_fb_log(path: Path, log: list[dict]) -> None:
    """fb_log.json に書き込む。"""

def record_feedback(path: Path, phase: str, iter: int, score: float, feedback: str) -> None:
    """
    1イテレーション分のフィードバックを追記する。
    
    Args:
        phase: "material_pdca" | "article_pdca"
        iter: イテレーション番号
        score: 今回のスコア
        feedback: レビュアーからのフィードバック文字列
    
    Note:
        diffs フィールドは前イテレーションのフィードバックとの差分（文字列リスト）。
        v5.0 のバグ修正: diffs が常に [] になっていた問題を修正済み。
        → 前エントリの feedback と現エントリの feedback を比較して生成する。
    """

def compute_diff(prev_feedback: str, curr_feedback: str) -> list[str]:
    """
    2つのフィードバック文字列の差分を行単位で計算する。
    
    Returns:
        diffs: list[str]  # 追加された行（+）と削除された行（-）
    
    Bugfix (v5.1):
        v5.0 では prev_feedback の参照ミスにより diffs が常に [] だった。
        本関数で正しく difflib.unified_diff を使用する。
    """

def check_stagnation(log: list[dict], phase: str, window: int = 3) -> bool:
    """
    直近 window イテレーションでスコアが改善していないか判定する。
    
    Returns:
        True if stagnating (score not improved in last `window` iters)
    """
```

### 8.4 stagnation_check.py（NEW）

```python
def count_resolution_rate(log: list[dict], phase: str) -> float:
    """
    フィードバックの「解決率」を計算する。
    前イテレーションで指摘された問題が次イテレーションで解消されたかを測定。
    
    Returns:
        resolution_rate: float (0.0~1.0)
    """

def detect_stagnation_triggers(log: list[dict], phase: str) -> dict:
    """
    停滞の3トリガーを検知する。
    
    Returns:
        {
            "score_stagnation": bool,       # 3回連続スコア改善なし
            "low_resolution_rate": bool,    # resolution_rate < 0.3
            "feedback_repetition": bool,    # 同一フィードバックが3回以上
            "should_gap_alert": bool        # いずれか1つが True なら gap_alert 発動
        }
    """

def run_stagnation_check(log_path: Path, phase: str) -> dict:
    """
    fb_log.json を読み込み、停滞状態を判定して結果を返す。
    gap_alert が必要な場合は gap_alert.py を呼び出す。
    
    Returns:
        {
            "stagnating": bool,
            "gap_alert_message": str | None
        }
    """
```

### 8.5 gap_alert.py（NEW）

```python
def compute_gap(current_score: float, threshold: float, axis_scores: dict) -> dict:
    """
    現スコアと閾値のギャップを計算する。
    
    Args:
        current_score: 現在の総合スコア
        threshold: 閾値（Material: 0.85, Article: 0.80）
        axis_scores: 軸別スコア {"coherence": 0.7, "value": 0.6, ...}
    
    Returns:
        {
            "total_gap": float,           # threshold - current_score
            "weakest_axis": str,          # 最もスコアが低い軸
            "weakest_axis_gap": float,    # weakest_axis の不足量
            "axis_gaps": dict             # 全軸のギャップ
        }
    """

def format_gap_alert(gap: dict, phase: str) -> str:
    """
    エージェントへの具体的なギャップアラートメッセージを生成する。
    
    Returns:
        alert_message: str
        
    Example output:
        "【ギャップアラート】現スコア 0.72、閾値まで 0.08 不足。
         最弱軸: value (0.58 / 目標 0.80)。
         次イテレーションでは「読者への具体的価値提示」を最優先してください。"
    """

def generate_gap_alert(log_path: Path, threshold: float, phase: str) -> str:
    """
    fb_log.json の最新エントリからギャップアラートを生成する。
    """
```

### 8.6 checkpoint.py（NEW）

```python
DEFAULT_CHECKPOINT = {
    "phase": "layer1",
    "next_action": "run_strategist",
    "material_iter": 0,
    "article_iter": 0,
    "best_material_score": 0.0,
    "best_article_score": 0.0,
    "material_fallback_count": 0,
    "last_updated": ""
}

def read_checkpoint(path: Path) -> dict:
    """
    checkpoint.json を読み込む。
    ファイルが存在しない場合は DEFAULT_CHECKPOINT を返す。
    JSON 破損時は DEFAULT_CHECKPOINT を返してログに警告を出す。
    """

def write_checkpoint(path: Path, state: dict) -> None:
    """
    checkpoint.json に書き込む。
    last_updated を現在時刻（ISO8601）に自動セットする。
    """

def route_next_action(state: dict) -> str:
    """
    現在の state から次のアクションを決定する。
    
    Logic:
        phase == "layer1"          → "run_strategist"
        phase == "material_pdca"   → "run_material_iter"
        phase == "article_pdca"
            next_action == "material_fallback"  → "material_fallback"
            else                                → "run_article_iter"
        phase == "done"            → "finalize"（完了後は変化なし）
    
    Returns:
        next_action: str
    """

def advance_checkpoint(path: Path, completed_action: str, score: float = None) -> dict:
    """
    アクション完了後にチェックポイントを進める。
    スコアが指定された場合は best_*_score を更新する。
    
    Returns:
        updated_state: dict
    """
```

---

## 9. HARD FAIL / Stagnation ルール

### HARD FAIL キャップ（metrics.py で強制適用）

| 条件 | スコアキャップ | 趣旨 |
|------|-------------|------|
| `code_ratio > 20%` | **0.60** | コードが多すぎる記事は Zenn 的に価値が低い |
| `desu_masu_ratio < 80%` | **0.55** | 口調一貫性がない記事は品質が低い |
| `consecutive_same_length > 4` | **0.50** | 文長の単調さは読みにくさの指標 |

- HARD FAIL は LLM 判断によらず Python で機械的に判定・適用する
- 複数の HARD FAIL が同時に発動した場合、**最も低いキャップ**を適用する
- HARD FAIL が発動した場合、フィードバックにその旨を明記し、次イテレーションの Writer に伝える

### Stagnation Detection（stagnation_check.py）

**発動条件（3トリガーのいずれか1つ）**:
1. スコアが3回連続で改善しない
2. フィードバック解決率 < 30%（指摘されても直っていない）
3. 同一内容のフィードバックが3回以上繰り返される

**発動時の挙動**:
1. `gap_alert.py` が呼ばれる
2. 最弱軸・ギャップ量・具体的改善指示が生成される
3. 次イテレーションのエージェント（Writer / ThesisDesigner）へのプロンプトに追記される

### MATERIAL_FALLBACK トリガー

```
Article PDCA において:
    iter >= 3
    AND score < 0.70
    AND material_fallback_count < 2
→ MATERIAL_FALLBACK 発動
```

- フォールバック発動後はイテレーションカウンタをリセット
- 3回目（`material_fallback_count >= 2`）は無視して継続

---

## 10. 設計原則

### 原則 1: 決定論的ロジックは Python へ

LLM にスコア計算・ルーティング・ファイルパス解決を委ねない。
すべての分岐条件（HARD FAIL / 閾値比較 / フォールバック判定）は Python スクリプトで実装する。

**悪い例**: "スコアを評価して次の行動を決めてください"
**良い例**: `checkpoint.py.route_next_action(state)` が文字列を返し、Lead がそれに従う

### 原則 2: SubAgent は「書いて要約」のみ

すべてのエージェントはファイルに書き込み、**パス + 2〜4文のサマリー**のみを返す。
10KB ルール: エージェントの返答が 10KB を超えてはならない。
大量データの受け渡しはファイル経由で行う。

### 原則 3: セッション断絶への耐性

`checkpoint.json` により、どのタイミングでセッションが切れても再開できる。
「完了済みの作業はやり直さない」を保証するため、イテレーション番号を正確に管理する。

### 原則 4: 1イテレーション内は逐次実行

PDCA の1サイクル内では並列実行しない（Phase 0 の TrendResearcher + PainExtractor を除く）。
レビュー結果を次のエージェントが参照するため、write → review → score の順序を守る。

### 原則 5: コスト意識（Skillbase 前提）

Claude Code Subscription 内で完結するため、API コストの最小化ではなくトークン効率を意識する。
エージェントへの入力はファイルパス参照に留め、全文埋め込みを避ける。
不要な並列実行を抑制し、1セッションのコンテキスト長を管理可能な範囲に保つ。

---

*このドキュメントは v5.1 の設計仕様を記述したものです。実装時は各スキルの INSTRUCTIONS.md を参照してください。*
