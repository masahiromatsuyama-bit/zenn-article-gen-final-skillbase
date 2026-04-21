# 次セッション: experience_author.md の中身ロジック設計ディスカッション

作業ディレクトリ: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`
ブランチ: `feat/uniqueness-mapping-eval-axes`（main にマージ前）

---

## ⚠️ 重要: このセッションの進め方

**いきなり実装しないこと**。ユーザーとディスカッションしながら方針を固める。
- 最初に「方針決定ディスカッション」を優先する
- ユーザーが方針を決めてから初めて実装に移る
- 実装を始める前に必ずユーザーの承認を取る

---

## 📌 このセッションの目的

**`.claude/agents/experience_author.md` の「中身のロジック」を設計する**。

インターフェース層（入出力・checkpoint 遷移・Stage Dispatch Table）は前セッションで完了済み。残作業は **experience_author agent が `experience_log.md` を生成する具体的な方法** を決めること。

現在の `experience_author.md` は:
- 入出力 I/F: 確定 ✅
- 出力テンプレート: 確定（厳密な Markdown 構造）✅
- **中身のロジック: スタブ（`<!-- TODO -->` で差し替え予定と明記）** ← ここを埋める

---

## 🎯 ディスカッションの主題

experience_log.md をどう生成するか。3 つの候補が前セッションで出ている:

### Option A: Interactive（対話型）
- エージェントが著者に質問を投げかけ、返答から experience_log を構成する
- 例: 「直近 1 週間で驚いた数値は？」「1 時間以上ハマったのは？」「効くと思って効かなかったのは？」
- **Pro**: 著者の生の声が確実に入る。記事の生々しさ最大化
- **Con**: 著者が毎回 5-15 分の手作業必要。完全自動化から一歩後退

### Option B: Mining（実アーティファクト採掘）
- `git log` / 失敗した PR / issue コメント / Slack スレッド / デバッグログ等から「驚いた瞬間」を自動抽出
- LLM が mining した候補を構造化して experience_log.md に書き出す
- **Pro**: 著者の時間コストゼロ。自動化と親和性が高い
- **Con**: アーティファクトに残っていない「感情」「迷い」は拾えない。mining ソースの設定が必要

### Option C: Synthesis（合成・現スタブ相当）
- LLM が strategy / trends / system_analysis / topic から「著者にありえそうな経験」を生成する
- 現在の experience_author.md にコメントアウトで記載されている暫定モード
- **Pro**: 実装最小。既存入力だけで動く
- **Con**: 著者の生の声ではないので、AI 臭の根本解決にはならない（単に LLM の想像を 1 ファイル増やしただけ）

### Option D: Hybrid（B + A のハイブリッド・前セッションで私が推した案）
- B で candidate 素材を 5-10 個自動発掘（マシン的）
- C で著者にそれぞれ「実際どう感じたか」を 1-2 文問う（人間的・最小対話）
- その融合を experience_log.md に書く
- **Pro**: 自動化の利便性と生の声の強度を両立
- **Con**: 両方の実装コスト

---

## 📖 ディスカッション前に把握しておくべき現在の状態

### 前回セッションで完了したこと

1. **段階1（純加算）**: インターフェース層追加
   - `.claude/agents/experience_author.md` 新規作成（114 行・I/F + テンプレ + スタブ）
   - `.claude/scripts/file_registry.py`: `KB_EXPERIENCE_LOG` 追加、`PHASE_INPUTS` 更新
   - `.claude/agents/thesis_designer.md`: optional 入力 + 制約追加
   - `.claude/skills/zenn-material-pdca/INSTRUCTIONS.md`: optional 入力追加

2. **段階2（遷移変更）**: 新 phase を state machine に組み込み
   - `.claude/scripts/checkpoint.py`:
     - `VALID_TRANSITIONS["experience_authoring"]` 追加
     - `advance_topic_selection(cp)` の遷移先を `experience_authoring` に変更
     - 新関数 `advance_experience_authoring(cp)` 追加
   - `.claude/skills/zenn-orchestrator/INSTRUCTIONS.md`: Stage Dispatch に行追加 + 詳細節追加 + エラー時FB表更新
   - `dry_run_validate.py`: 既存期待値修正 + 新テスト5件追加

3. **段階3（ドキュメント）**: 設計ドキュメント反映
   - `ARCHITECTURE.md`: §5 実行フロー図に新 phase 追加、§6 checkpoint スキーマ enum 追加、§7 ファイルレジストリに experience_log.md 追加
   - `REQUIREMENTS.md`: FR-NEW-08 として Experience Authoring phase の要件追加
   - `TECH_SPEC.md`: checkpoint.json JSON Schema の enum 更新、状態遷移テーブル更新、VALID_TRANSITIONS 更新

4. **dry_run**: **64/64 passed**（既存 59 + 新規 5）

5. **コミット**:
   - `c1b75f5 feat(experience-authoring): Topic Selection と Material PDCA の間に新 phase を追加`
   - 直近コミットにドキュメント更新（未 push の可能性あり・新セッションで `git status` 確認）

### 現在のフロー

```
Layer 1 (Strategist → EvalDesigner → SystemAnalyst*)
    ↓
Topic Selection (TrendResearcher → TopicFinalizer → topic.md)
    ↓
★ Experience Authoring (ExperienceAuthor → experience_log.md) ← ここの中身が未実装
    ↓
Material PDCA (PainExtractor → ThesisDesigner(experience_log を最優先入力) → MaterialReviewer)
    ↓
Article PDCA (Writer → StyleGuideUpdater → ArticleReviewer → Finalizer)
```

### experience_authoring phase 入力（experience_log.md 生成時に参照できるもの）

- `output/strategy.md` — 記事戦略（必須）
- `output/eval_criteria.md` — 評価基準・品質センス参考用（必須）
- `output/knowledge/trends.md` — 外部トレンド分析（存在する場合のみ）
- `output/knowledge/system_analysis.md` — 題材システムの設計解説（存在する場合のみ）
- `output/topic.md` — 選定トピック（存在する場合のみ）

⚠️ **注**: `reader_pains.md` は Material PDCA iter 1 内部で PainExtractor が生成するため、experience_authoring 時点では存在しない。もし experience_author に reader_pains を渡したい場合は PainExtractor の移動が必要（別改修）

### experience_log.md の固定テンプレート（決定済み）

```markdown
# 著者の生々しい経験ログ

## 数値で驚いたこと（必須・1 件以上）
### 1. {タイトル}
- いつ / 何を測ったか / 期待値 / 実測値 / 差分 / 最初の反応 / 原因

## ハマったこと / 詰まったこと（必須・1 件以上）
### 1. {タイトル}
- いつ / 状況 / 痛み / 原因 / 解決 / 所要時間 / そのとき何を感じたか

## 「こう思ったのに違った」体験（推奨・1 件以上）
### 1. {タイトル}
- 仮説 / 結果 / 差分 / 学び

## 未解決の疑問・迷い（任意）

## 既存記事・公式ドキュメントとのズレを感じた箇所（任意）

## 使わない素材（任意・ネガティブリスト）
```

---

## 🔑 ディスカッション初手: 聞いてほしい質問

いきなり実装に走らないこと。最初のターンでは以下を順に確認する:

### Q1. どの Option 方向で進めたいか？

A / B / C / D のどれを推す？ または別案がある？
- 自分の作業スタイル（対話を増やすか自動化を優先か）
- 本システムの用途（個人用か／他人に配るか）
- 既に持っている一次情報（git log / Slack / 個人メモ）へのアクセス性

### Q2. 著者自身が手を動かすコストはどこまで許容できるか？

- 記事 1 本あたり 0 分 / 5 分 / 15 分 / 30 分 のどこが上限か
- 「書き殴りテキストを投げ込む」なら何行まで書ける？
- 「質問に答える」なら何問まで答える？

### Q3. ログの再利用性（一度書いた経験を複数記事で使えるか？）

- 1 記事 1 experience_log か、プール型にして複数記事で共有するか
- プール型なら「この記事にはこの経験群を使う」選別の仕組みが要る

### Q4. 本システムを他人にも使わせるか？

- 自分専用なら Option A / D が効く（対話形式でも負担が許容される）
- 他人に配布するなら Option B / C 寄り（手作業を最小化する必要）

---

## ⚠️ ディスカッション中に避けるべきこと

以下は実装に入ってから考える・ユーザーの明示的な指示があるまで触れないこと:

- **実装の詳細設計**（エージェント内部の prompt 構造、分岐ロジック）
- **プロトタイプコード**（experience_author.md の中身を書き始める）
- **新しいスキル・エージェントの提案**（ExperienceAuthor を複数エージェントに分ける等）
- **既存インターフェースの変更**（I/F は前セッションで凍結済み）

---

## 📂 参考ファイル（ディスカッション中に参照すると有用）

| ファイル | 参照目的 |
|---|---|
| `.claude/agents/experience_author.md` | 現在の I/F と空スタブ |
| `.claude/agents/thesis_designer.md` | experience_log を受け取る側の仕様 |
| `.claude/skills/zenn-orchestrator/INSTRUCTIONS.md` | Stage Dispatch Table に run_experience_author がどう載っているか |
| `human-bench/articles/03_dspy_expert.md` | 「生々しい経験が刺さる記事」の具体例 |
| `human-bench/articles/07_claude_code_memory_mcp.md` | 同上 |
| `output_prev_20260421_170240/final_article.md` | 前回ranで生成された「AI 臭い記事」。これを改善する基準点 |
| `rule.md` / `sense.md` | 記事品質の絶対ルール / 品質センス |
| `ARCHITECTURE.md` §5.1.8 | Experience Authoring phase の設計意図 |
| `REQUIREMENTS.md` FR-NEW-08 | Experience Authoring の要件定義 |

---

## 🚀 このセッションでのゴール

**最低ライン**: どの Option で進めるかを決める（+ 理由の共有）

**理想ライン**:
1. Option 決定
2. 入出力の詳細（著者への問いかけ内容、mining ソース、合成ルール等）を詰める
3. スタブ部分を埋めた `experience_author.md` の最終形のドラフトを作る
4. dry_run 通過確認
5. コミット & プッシュ

**実装に入る前に必ずユーザー承認**を取ること。ディスカッションを急がない。

---

## 📝 セッション開始時の初手

1. `git status` と `git log --oneline -5` で前回の状態を把握
2. `python3 dry_run_validate.py` で 64/64 継続確認
3. 本プロンプトの Q1 からユーザーに順に問いかけて Option を決める
4. Option が決まったら入出力の詳細を一緒に詰める
5. 合意後に初めて `experience_author.md` のスタブ部を書き換える
