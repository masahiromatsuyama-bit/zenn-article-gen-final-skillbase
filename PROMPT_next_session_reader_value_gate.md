# 次セッション: Reader-Value Gate 実装 + Drama/Strategy/Reviewer 再設計

作業ディレクトリ: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`
ブランチ: `feat/experience-authoring-drama-sim`（未 push）
最終コミット: `e1033b4`（本プロンプト）/ `2b44e57`（ユーザー実装の P1+P5 相当）/ `509e773`（中心学び導出契約）

## ⚡ 重要な前提: P1 と P5 は既にユーザーが実装済み

前セッション中、ユーザーが `2b44e57 feat(rule+strategist): 文長ばらつき数値基準化 + AnyMind 1 エンジニア著者プロフィール固定` を独自にコミット。内容は本計画の P1 と P5 に相当:

- `rule.md`: 短文/中文/長文/超長文の 4 バケット定義、4 連続禁止（従来 5 連続）、段落ごとに長文(61字+) 最低 1 本必須、超長文 8% 以上、中文連続型と述語過去形揃いの明示的禁止
- `strategist.md`: 「著者プロフィール（固定）」セクション追加、著者は AnyMind Group の 1 エンジニア（完全匿名禁止）、本文 1-2 箇所で業務の手触り、strategy.md に配置指定義務

**ただし、この commit は E2E 実走の「後」に行われた**（または E2E の Writer / Reviewer が新 rule.md を参照する前に記事化が終わっていた）ため、`output/final_article.md` の品質問題は新ルールが反映されていない状態で発生した。

→ **次セッションの初手は「P1 + P5 のみ反映された状態で E2E 再実行」**。これで改善幅を測ってから、P2-P6 のどれを追加実装するかを決める。

---

## ⚠️ セッション開始時の最初の一手

1. `git status` と `git log --oneline -5` で前回までの状態を確認
2. `python3 dry_run_validate.py` で 64/64 継続確認
3. `output/final_article.md` を読み、「なぜこの記事が個人ブログすぎるか・学びが無いか・一文が短く AI 臭いか」を自分の目で確認
4. 本プロンプトの改善計画 P1-P6 をユーザーと順に詰める（いきなり実装しない）

---

## このセッションの目的

**直前のセッションで E2E を完走した結果、最終記事の品質が想定を大きく下回ったことへの抜本対策**。

前回 run の結果:
- Material PDCA iter 2 で 0.86 → threshold 突破
- Article PDCA iter 2 で 0.81 → threshold 突破・finalize
- `output/final_article.md` (11,197 chars) が出力された

しかしユーザー目視チェックで以下の問題が判明:

1. **個人ブログすぎて「社内ツール・開発過程」の文脈が記事に無い** — AnyMind のテックブログとして成立していない（strategist.md の公開コンテキストは満たしていたが、strategy.md が「AnyMind を出さない / 1 エンジニアの読解記録として書く」を選んだ結果、業務文脈ゼロになった）
2. **意味不明な言い回し**（「辺縁の足あと」「条件付きで持ち帰れます」「CLI の 900 行を維持するために Skill 側が引き受けた厚みです」）が頻発。読者が「何の話をしているか」を追えない
3. **一文の長さが均一で短い** — rule.md L20-22 が明示的に禁止している「短文連続」が実態は頻発。レビュアーが拾えていない
4. **PDCA が実質機能していない** — 0.81 の数値評価と、実際の読者価値が乖離。ベンチマーク比較形式で書けているだけで 0.80 を通している

---

## 根本原因の診断（前セッションの分析）

### 層ごとの壊れ方

| 層 | 状態 | 何が壊れているか |
|---|---|---|
| Topic Selection | △ | Topic 自体は妥当。だが key_tension が「設計を読み取る」止まりで「読み取った結果読者が業務で何を得るか」まで踏み込んでいない |
| **Drama Sim (Phase 1.0)** | **✗ 最大の問題** | 中心学びが**観察型**（「〜は〇〇にある」）で、reader_pains.md との接地がない。読者が「自分の業務で何をやる」に変換されない |
| ThesisDesigner | △ | drama の中心学びをそのまま移植するため、drama の弱さを継承 |
| Strategy | △ | 「業務文脈を書く」が必須項目化されておらず、strategist 判断次第で「AnyMind を出さない = 業務文脈ゼロ」に倒せる仕様 |
| Writer | △ | 新概念導入時に具体例で定義するルールがなく、抽象比喩（「辺縁の足あと」）を生成しても怒られない |
| **ArticleReviewer** | **✗ 第 2 の問題** | ベンチマーク比較形式の遵守しか見ておらず、「読者が明日何をするか」「weird phrasing」「文長分散」の 3 大 AI 臭チェックが無い。0.80 が読者価値を保証しない |

### 診断結論

**生地のレベルが低い根本原因は Drama Sim 時点で既にダメだった**。中心学びが読者価値に接地していないため、下流全体が「観察記」として完結してしまい、読者の動機形成が起きない。

---

## 改善計画（優先順位付き・6 項目）

### P1: strategist.md に「業務文脈の必須化」を追加

**問題**: strategy.md の必須セクションに業務文脈項目がなく、「AnyMind を出さない」判断を下すと業務文脈が完全に消える

**改訂**:
- strategist.md の固定公開コンテキストに「**テックブログの記事には、著者の業務文脈が透けていることが必須**」を明記
- strategy.md テンプレに以下 2 セクションを**必須**で追加:
  - `## 調査の業務背景` — なぜこの調査が業務で発生したか / どの意思決定のためか / 何を決める必要があったか
  - `## 読後の読者アクション` — 1 行。読者が明日業務で何を決める / 何を試す / 何に気づくか
- 「AnyMind 社名は本文に出さなくてよいが、**業務の立場（マーケ系 SaaS 基盤を作るエンジニア 等）は本文で示唆する**」を明文化

**影響範囲**: `.claude/agents/strategist.md` のみ

---

### P2: Drama Sim Phase 1.0 の「中心学び」を**行動型**に拡張

**問題**: 現状の中心学びは観察型（「〜は〇〇にある」）で、reader_pains.md との接地がない

**改訂**:
- Phase 1.0 の導出規約に以下を追加:
  - 中心学びは**`reader_pains.md` の痛点を 1 つ選んで名指し**で解消する形で書く
  - 観察形式は禁止。**行動変容型**（「読者は〇〇を**決められるようになる** / **避けられるようになる** / **行動できるようになる**」）で書く
  - Fitness Check に「解消する reader_pain の引用」を追加
- 現状の「設計原理の葛藤 / 見えない凍結領域 / 想定と現実のズレ / トレードオフの発見」は維持するが、**すべて行動変容語尾で終わる**ことを必須化

**影響範囲**: `.claude/agents/experience_author.md` のみ

**注意**: reader_pains.md は Material PDCA 内部で PainExtractor が生成する。Experience Authoring 時点では存在しない。→ **PainExtractor を Experience Authoring の前に移動する必要がある**（別改修・P2 の前提作業）

---

### P3: ArticleReviewer に Reader-Value Gate を追加

**問題**: ベンチマーク比較形式の遵守しか見ておらず、実質的な読者価値を測れていない

**改訂**:
- 以下を **hard gate** として追加:
  - **明日の読者アクションが 1 行で書けるか** — 書けなければ weighted_average に関係なく major 2 件扱い
  - **AI 特有の weird phrasing 検出** — 「辺縁の〇〇」「〇〇の足あと」「物理的に〇〇」「条件付きで〇〇」等の抽象比喩パターンリストを用意し、検出したら major 指摘
  - **文長分散 σ < 15** なら HARD FAIL 扱い
- 既存の `## ベンチマーク` 比較は維持

**影響範囲**: `.claude/agents/article_reviewer.md` + `metrics.py` に `sentence_length_std_dev` 関数追加

---

### P4: Writer に「読者置き去り禁止」ルール追加

**問題**: 新概念・新用語を導入しても具体例で定義しない

**改訂**:
- writer.md に以下を新規ルールとして追加:
  - 新概念・新用語（「辺縁の足あと」「畳み込み」等）を導入したら、**同一段落内で 1 つの具体例とともに定義**する
  - 「条件付きで」「辻褄を合わせる」のような抽象動詞は、**直後 20 字以内で主語と具体対象を補足**する
  - 章冒頭は**前章との接続**で始める。「〇〇という話です。」のような突然始まる文は禁止

**影響範囲**: `.claude/agents/writer.md` のみ

---

### P5: metrics.py に `sentence_length_variance` を追加し HARD FAIL 化

**問題**: 現状の `consecutive_same_length` は「連続して同じ長さ」だけチェックし、全体の文長分散は測っていない

**改訂**:
- `metrics.py` に `sentence_length_std_dev(text)` を追加
- `check_hard_fail()` に `sentence_length_std_dev < 15` を追加
- `fix_*` 系の自動修正関数として `fix_sentence_length_variance` は **追加しない**（自動修正ではなく Writer に戻す方針）
- HARD FAIL 理由として reviewer に渡し、次 iter で Writer が修正する

**影響範囲**: `.claude/scripts/metrics.py` + `.claude/skills/zenn-article-pdca/INSTRUCTIONS.md` Step 2

---

### P6: PDCA 収束条件に **ペルソナ A/B 判定** を追加

**問題**: 0.80 を越えても実質的な読者価値が低い記事が通ってしまう

**改訂**:
- article_pdca の finalize 前に新ゲート:
  - ベンチマーク記事 1 本を選び、「**この記事と本記事、読者が友人にどちらを薦めるか**」を LLM に判定させる
  - ベンチマーク側が勝ったらスコア cap（例: 0.75 以下 = threshold 未達 = 次 iter）
- 具体的な実装: 専用の小エージェント `article_ab_judge.md` を新設。入力 = bench 記事 1 本 + 本記事。出力 = `{"winner": "bench|ours", "reason": "..."}`
- max_iter=10 到達時は強制 finalize（無限ループ回避）

**影響範囲**: 新規 `.claude/agents/article_ab_judge.md` + `.claude/skills/zenn-article-pdca/INSTRUCTIONS.md` 末尾 + orchestrator Stage Dispatch

---

## 優先順位の再確認

**最小パッケージ**（まずこれだけ実装して再 E2E）:
- **P1** (strategy 業務文脈必須化) — 独立・最速で効く
- **P3** (Reviewer Reader-Value Gate) — 独立・即効
- **P5** (sentence_length_variance HARD FAIL) — 独立・最速

**次のパッケージ**（P1-P3 の効果確認後に追加）:
- **P4** (Writer 読者置き去り禁止) — P3 でレビュアーが指摘した事例をテンプレ化できた段階で追加
- **P2** (Drama 中心学び行動型) — PainExtractor の移動が前提作業として必要

**保留**（効果見てから判断）:
- **P6** (ペルソナ A/B 判定) — 実装コスト高く、P1-P5 で改善しなければ採用

---

## 前セッションまでの変更履歴（引き継ぎ用）

直近 3 コミット:
- `509e773` feat(experience-authoring): 中心学び を topic.md から導出する契約に明示化
- `44f31b3` feat(experience-authoring): Phase 1 に 中心学び先出し + severity ゲート追加
- `083431a` feat(experience-authoring): Multi-Agent Drama Simulation (Option E) を実装

既存の I/F 層コミット（main マージ済みまたは同ブランチ内）:
- `7746fb1` docs(experience-authoring): ARCHITECTURE/REQUIREMENTS/TECH_SPEC に新 phase 反映
- `c1b75f5` feat(experience-authoring): Topic Selection と Material PDCA の間に新 phase を追加
- `3c0643d` feat(prompts): AI臭の低減と独自性ゲートの強化

---

## 前セッションで生成された検証データ（参考）

`output/` に残っている:
- `strategy.md` — 今回の strategy（L60 に「業務の手触り込み」L69 に「AnyMind を出さない」という自己矛盾的記述）
- `knowledge/system_analysis.md` — postiz-agent の詳細解析（再生成不要）
- `knowledge/drama_raw.md` — Drama Sim の生ログ（中心学び: 「2 行の設計判断に物理的に畳まれている」という観察型）
- `knowledge/experience_log.md` — 圧縮版
- `thesis.md` / `iterations/{1,2}/` — Material と Article の iter 記録
- `final_article.md` — 最終記事（問題事例）

前々回（kol-content-design）の出力: `output_prev_20260421_drama_v1_kol/`

---

## このセッションのゴール

**最低ライン**: P1 + P3 + P5 を実装し、dry_run 通過 + コミット

**理想ライン**:
1. P1 + P3 + P5 実装 + コミット
2. 同じ postiz-agent で E2E 再実行
3. 改善前後の記事を並べて比較し、実質的な品質向上を確認
4. 確認できたら P2 + P4 を実装 + コミット
5. 再 E2E で検証

**実装に入る前に必ずユーザー承認**を取ること。いきなり実装しない。

---

## ⚠️ ディスカッション中に避けるべきこと

- **「PDCA の数値評価を廃止しよう」という極端な提案**（数値評価は必要。ゲートを足す方向で改善する）
- **Drama Sim 自体の全面書き直し**（Phase 1.0 改訂はまだ評価途上。追加調整で済ませる）
- **実際の記事本文の手動書き直し**（システムが自動で生成できる品質を目指す）
- **strategy の「AnyMind を出す/出さない」を二項対立にする**（「業務文脈を透かす」が正解で、社名明示は任意）

---

## 参考ファイル

| ファイル | 参照目的 |
|---|---|
| `.claude/agents/strategist.md` | P1 改訂対象 |
| `.claude/agents/experience_author.md` | P2 改訂対象（Phase 1.0 節） |
| `.claude/agents/article_reviewer.md` | P3 改訂対象 |
| `.claude/agents/writer.md` | P4 改訂対象 |
| `.claude/scripts/metrics.py` | P5 改訂対象 |
| `.claude/skills/zenn-article-pdca/INSTRUCTIONS.md` | P5 / P6 で参照 |
| `rule.md` / `sense.md` | 絶対ルールの原典。Reviewer が実質機能していない問題の起点 |
| `output/final_article.md` | 問題事例の原文 |
| `output/knowledge/drama_raw.md` | Drama Sim の中心学びが観察型になっている事例 |
| `human-bench/articles/07_claude_code_memory_mcp.md` | ペルソナ比較基準（「3 秒 → 0.33 秒」が読者動機を作っている例） |

---

## セッション開始時の初手（繰り返し）

1. `git status` と `git log --oneline -5`
2. `python3 dry_run_validate.py`（64/64 確認）
3. `output/final_article.md` を読んで問題事例を目視
4. 本プロンプトの診断と P1-P6 計画を確認
5. ユーザーと P1 / P3 / P5 の優先順を確認
6. 合意後に実装開始
