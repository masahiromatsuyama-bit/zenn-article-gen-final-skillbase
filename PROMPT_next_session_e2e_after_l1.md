# 次セッション: L1 修正（Reader-Value Gate 一式）後の E2E 本番ラン

作業ディレクトリ: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`
ブランチ: `feat/experience-authoring-drama-sim`（未 push）
最終コミット: `2398a09`

---

## このセッションの目的

**L1 パッケージ（Step A + B + D-lite + F + E-lite）を本番 E2E で検証する**。

記事を**ゼロから作り直す**。前セッションで「個人ブログすぎて業務文脈ゼロ / ベンチ同等で 0.81 通過 / 抽象比喩混入」だった問題が、L1 で改善されたかを測る。

---

## 入力データ

**このシステム自身のフォルダ** = `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/` を題材にする。

つまり「Zenn 記事自動生成システム自体の設計解説記事」をシステム自身に書かせる再帰的な E2E。`SystemAnalyst` が対象にするパス:

```
.claude/scripts/       ← checkpoint.py, metrics.py, fb_log.py
.claude/skills/        ← zenn-orchestrator / zenn-material-pdca / zenn-article-pdca / zenn-topic-selection
.claude/agents/        ← 全 13 エージェント定義
dry_run_validate.py    ← spec-as-code の実体
ARCHITECTURE.md, REQUIREMENTS.md, TECH_SPEC.md
human-bench/articles/  ← ベンチマーク 8 本（自己参照評価回避用）
rule.md, sense.md      ← 絶対ルール + 良い記事の定義
```

**前回（postiz-agent 題材）とは別題材**。前回の `output/` は `output_prev_20260421_drama_v1_kol/` などに既に退避済み。新たに退避する場合は下記 Step 1 に従う。

---

## L1 で何が変わっているか（検証観点）

直近 5 コミットで入った変更:

| Commit | 変更内容 | 検証すべき挙動 |
|---|---|---|
| `68ae5a6` | article_reviewer.md に Reader-Value Gate (項目 6) + weird phrasing 検出 (項目 7) | review.json の feedback に「明日の読者アクション 1 行抜き出し」判定 / 抽象比喩検出が出る |
| `6ab61df` | strategist.md に `## 調査の業務背景` + `## 読後の読者アクション` 必須化。rule.md は 2b44e57 の 4 バケット化を revert 状態維持 | strategy.md の両セクションが埋まる / 業務文脈が滲むトーン指示が入る |
| `984dd0a` | article_reviewer.md にペルソナ A/B 比較ブロック義務化 | review.json の feedback に「ベンチ XX_XXX.md と比較し、友人に先に薦めるのはどちら」判定が必ず入る |
| `f09fc80` | writer.md に読者置き去り禁止ルール（新概念導入時は同段落で具体例定義 / 抽象動詞直後 20 字補足 / 章冒頭は前章接続 / 抽象比喩禁止） | 「辺縁の足あと」「条件付きで」等が本文に出ない |
| `2398a09` | experience_author.md Phase 1.0 に行動変容語尾必須化 + Fitness Check 拡張 | drama_raw.md の中心学びが「〜にある」の観察型ではなく「〜を決められる / 避けられる / 数えられる / 試せる」で終わる |

---

## セッション開始時の初手

```bash
git branch --show-current     # → feat/experience-authoring-drama-sim
git log --oneline -6          # → 2398a09 が先頭
python3 dry_run_validate.py   # → 64 passed / 0 failed
```

`dry_run_validate.py` が 64/64 通ることを必ず確認してから E2E に進む。

---

## 実行手順

### Step 1: 前回 output/ を退避

前回 run の成果物を比較用に退避し、クリーンな状態で新 run を始める:

```bash
if [ -d output ]; then
  mv output output_prev_$(date +%Y%m%d_%H%M%S)
fi
mkdir -p output
```

### Step 2: orchestrator 起動

`/zenn-orchestrator` を呼び出し、以下のプロンプトで開始:

```
題材: このシステム自身（zenn-article-gen-final-skillbase）

伝えたいこと:
- Claude Code サブスク内で動く Zenn 記事自動生成システムの設計
- ネスト PDCA（Material × Article）、checkpoint.json によるセッション断絶耐性、
  human-bench を参照する外部キャリブレーション、10KB rule、Multi-Agent Drama
  Simulation による経験素材化
- 実装の試行錯誤で見つけた設計判断（HARD FAIL の自動修正方針、major feedback の
  score cap、Consolidator 起動条件の再設計、PainExtractor と Drama Sim の
  フェーズ順序問題など）

読者像:
- Claude Code を使いこなしたい中上級エンジニア
- LLM 駆動開発の設計論に興味がある人
- サブスク内でエージェント基盤を組みたい人

文体: です・ます体 80%+、コードブロック 20% 未満、体験記・一人称視点、4000-6000 字
```

### Step 3: 各ステージの観測

Stage Dispatch に従って以下の順で遷移する:

1. `run_strategist` → `strategy.md` 出力
   - **確認**: 新セクション `## 調査の業務背景` と `## 読後の読者アクション` が両方埋まっているか
   - 業務背景は「自分が記事自動生成システムを業務で使いたかった」等の立ち位置が滲んでいるか
2. `run_eval_designer` → `eval_criteria.md` + `material_eval_criteria.md`
3. `run_system_analyst`（任意）→ `knowledge/system_analysis.md`
4. `run_topic_selector` → `topic.md`
5. `run_experience_author` → `knowledge/experience_log.md` + `knowledge/drama_raw.md`
   - **確認**: `drama_raw.md` 冒頭 Fitness Check の「行動変容語尾チェック」「読者アクション抜き出し」が埋まっているか
   - 中心学びが「〜を決められる / 避けられる / 数えられる / 試せる」で終わっているか
6. `run_material_iter` → `thesis.md`（Material PDCA 内部で PainExtractor → reader_pains.md 生成）
7. `run_article_iter` → `iterations/{N}/article.md` + `review.json`
   - **確認**: review.json の feedback に以下が入っているか
     - 項目 6（Reader-Value Gate）判定
     - 項目 7（weird phrasing）判定  
     - ペルソナ A/B 比較ブロック（ベンチ XX と本記事を比較して勝敗）
8. `consolidate` → 記事統合
9. `finalize` → `final_article.md`

---

## 成果物の評価チェックリスト

E2E 完了後、以下を確認:

### A. strategy.md の新セクション
- [ ] `## 調査の業務背景` が埋まっている（空欄・「TBD」禁止）
- [ ] `## 読後の読者アクション` が 1 行で具体動詞終わり
- [ ] 2b44e57 で廃止した「1-2 箇所手触り」の自由度が無いことを確認（revert 済み）

### B. drama_raw.md の中心学び
- [ ] 中心学びが行動変容語尾で終わる（「〜にある」「〜である」禁止）
- [ ] Fitness Check 7 項目が全て埋まっている
- [ ] `reader_pains.md` 接地の項目が「存在する場合は引用」「存在しない場合は strategy との整合」のいずれかで埋まっている

### C. iterations/{N}/review.json の新 feedback
- [ ] 項目 6 判定: 「明日の読者アクションが 1 行で抜き出せるか」が feedback に含まれる
- [ ] 項目 7 判定: weird phrasing パターン検出結果（該当無しでも OK）
- [ ] ペルソナ A/B 比較ブロック: 「ベンチ `human-bench/articles/XX_*.md` と比較し、`勝者` を先に薦める。理由: ...」が feedback 配列の Gut Check の直前にある
- [ ] 「同等と判断」等の逃げ表現が出ていない

### D. final_article.md の品質（目視）
- [ ] 業務文脈が本文 1 箇所で滲んでいる（AnyMind 社名は任意、立場の手触りは必須）
- [ ] 読者が明日業務で何をするかが末尾 500 字から 1 行で抜き出せる
- [ ] 「辺縁の〜」「〜の足あと」「条件付きで〇〇」「〜に畳まれて」等の抽象比喩が出ていない
- [ ] 新概念（「畳み込み」「凍結領域」等）を導入した段落で、同じ段落に具体例があるか

### E. 前 run (output_prev_20260421_drama_v1_kol) との並べ比較
前 run の `final_article.md` と今回の `final_article.md` を並べ、**読者の友人に薦めるなら今回版のほうを選ぶか**を目視判断。改善が体感できなければ L2 昇格を検討する。

---

## 完了後に報告してほしいこと

1. **L1 効果の観測**:
   - strategy.md 新セクションが機能したか (Yes/No + 具体引用)
   - drama_raw.md の中心学びが行動変容語尾で終わったか (Yes/No + 本文引用)
   - review.json のペルソナ A/B 比較が実際に勝敗付きで出たか (Yes/No + winner/reason 引用)
   - weird phrasing が final_article.md から消えたか（前 run と検索比較）

2. **`output/final_article.md` の冒頭 500 字**（前 run の冒頭と並べて比較）

3. **`output/report.json` 全体**

4. **Material / Article PDCA のスコア推移**（iter ごとの `weighted_average` を表形式で / major_count も併記）

5. **A/B 比較の勝敗分布**（全 iter 分 / 勝者がベンチの iter は何件か）

6. **前 run との並べ比較の定性評価**（1-3 段落）:
   - 個人ブログ化は解消されたか
   - 業務文脈の滲みは出たか
   - 読者アクションが明示されたか
   - ベンチ比較で勝てているか

7. **実行中に発生した未知のエラー・想定外の挙動**（あれば）

---

## トラブルシュート用メモ

| 症状 | 対応 |
|---|---|
| `strategy.md` に新セクションが無い | strategist.md の「業務文脈の必須化」節が LLM に無視されている。プロンプトで再強調して再実行 |
| Drama の中心学びが観察型で終わっている | experience_author.md 導出規約 5 が機能していない。Fitness Check 欄を手で埋め直させて Phase 2 を再実行 |
| review.json に A/B 比較が無い | article_reviewer.md のペルソナ A/B 比較ブロックが飛ばされている。Reviewer を再 spawn |
| 「同等と判断」が混入 | A/B 比較ブロックの禁止表現が守られていない。Reviewer 出力を拒否して再生成 |
| iter 1 で 0.80 超え即 finalize | eval_criteria.md が自己参照のまま。`## ベンチマーク` に `human-bench/articles/` の ID 3 件以上あるか確認 |
| checkpoint 壊れ | `rm output/checkpoint.json` → FRESH_STATE から再開 |
| 無限ループ（iter 10 到達） | A/B で毎回ベンチ勝利なら素材制約の可能性。iter 10 強制 finalize の挙動は checkpoint.py 側にある |

---

## L1 で直らない問題（次セッションで L2/L3 検討）

以下は L1（プロンプト層）で直せないので、E2E 後の定性評価で顕在化したら次セッションで判断:

- **PainExtractor が Drama Sim の後**: reader_pains.md が Drama 実行時点で存在しない → L3 で PainExtractor を前倒しする必要あり
- **A/B 比較が Reviewer 兼務**: 採点と A/B を同じエージェントでやっているので、判定が甘くなる可能性 → L2 で `article_ab_judge.md` 分離
- **weird phrasing リストが固定**: 新しい AI 臭パターンが出たら都度追加が必要 → L2 で metrics.py 側に降ろす

**L1 で改善幅が小さければ L2、それでも不十分なら L3**。いきなり L3 に行かない。

---

## 参考ファイル

| ファイル | 参照目的 |
|---|---|
| `.claude/agents/article_reviewer.md` | Reader-Value Gate + weird phrasing + A/B 比較の実装 |
| `.claude/agents/strategist.md` | 業務背景 + 読後アクション 2 セクション必須化 |
| `.claude/agents/writer.md` | 読者置き去り禁止 4 ルール |
| `.claude/agents/experience_author.md` | Phase 1.0 行動変容語尾必須化 |
| `human-bench/articles/07_claude_code_memory_mcp.md` | 「3 秒 → 0.33 秒」級の比較基準 |
| `output_prev_20260421_drama_v1_kol/final_article.md` | 前 run の問題事例（個人ブログ化・業務文脈ゼロ） |
| `PROMPT_next_session_reader_value_gate.md` | L1 改修計画の原典（診断と全 P1-P6 計画） |

---

## このセッションのゴール

**最低ライン**: E2E 完走 + 上記チェックリスト A-D を埋めて報告

**理想ライン**:
1. L1 改修の効果が定性的に確認できる（前 run と比べて業務文脈が透け、A/B でベンチに勝てる）
2. 確認できたら現ブランチを push → PR 作成
3. 確認できなかったら L2 昇格（`article_ab_judge.md` 分離 + Python 側 score cap）の実装プロンプトを次々セッション用に書き出す

**実装に入る前に必ずユーザー承認**を取ること。E2E 起動は自動でよいが、問題が出たら修正前に報告して判断を仰ぐ。
