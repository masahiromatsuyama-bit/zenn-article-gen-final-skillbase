# 次セッション: L2 改修（案 2 + 3 + 5）後の E2E 再検証

作業ディレクトリ: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`
ブランチ: `feat/experience-authoring-drama-sim`（push 済み・upstream 設定済み）
最終コミット: `a570169`（この prompt 自身を追加するときに + 1 commit）

---

## このセッションの目的

**L2 パッケージ（案 2 + 3 + 5）が実記事に効くかを E2E で検証する**。

前セッション（2026-04-22 / commit `a570169`）で、自己解説記事を E2E 生成したところ
最終 score 0.81 / L1 checks 全通過だったが、**本文の第 2 章 Q1 で「多くの人は〜。私もそうでした」の一般論→同化テンプレが残り、同記事の第 3 章でそれを AI 臭と批判する自己矛盾を Reviewer が見逃した**。そこで L2 を積んだ。

L2 の 3 改修（全て prompt+metrics 層の非侵襲改修）:

| # | 変更 | ファイル |
|---|---|---|
| 案 2 | `metrics.detect_ai_templates()` を追加（5 パターンの regex） | `.claude/scripts/metrics.py` / `dry_run_validate.py` |
| 案 3 | `article_reviewer.md` 項目 8（detect_ai_templates 呼出）+ 項目 9（self-consistency 照合） | `.claude/agents/article_reviewer.md` |
| 案 5 | A/B 比較を 2 ラウンド化。Round 2 で `trends.md` の注目記事を対戦相手に | `article_reviewer.md` + `zenn-article-pdca/INSTRUCTIONS.md` |

既存 64 checks は無傷、68/68 PASS のまま。今回の E2E で「案 2 の detector が major を付けるか」「項目 9 が自己矛盾を捕まえるか」「Round 2 で trends 記事との対戦が実際に走るか」を実確認する。

---

## アーキテクチャ全体像（前セッションで整理済み・参照用）

```
┌─ Layer 1 (記事戦略の土台) ────────────────────┐
│ ① Strategist       → strategy.md            │
│ ② EvalDesigner     → eval_criteria.md       │
│                     → material_eval_criteria│
│ ③ SystemAnalyst    → system_analysis.md     │
└──────────────────────────────────────────────┘
           ↓
┌─ Topic Selection ────────────────────────────┐
│ ④ TrendResearcher  → trends.md              │
│ ⑤ TopicProposer    → 5 候補                  │
│ ⑥ TopicFinalizer   → topic.md                │
└──────────────────────────────────────────────┘
           ↓
┌─ Experience Authoring ───────────────────────┐
│ ⑦ ExperienceAuthor(Drama Sim)               │
│   → drama_raw.md + experience_log.md        │
└──────────────────────────────────────────────┘
           ↓
┌─ Layer 2: Material PDCA (max 5, thr 0.85) ──┐
│ ⑧ PainExtractor / ⑨ ThesisDesigner / ⑩ MR   │
└──────────────────────────────────────────────┘
           ↓
┌─ Layer 3: Article PDCA (max 10, thr 0.80) ──┐
│ ⑪ Writer / ⑫ HARD FAIL / ⑬ Style / ⑭ AR    │
└──────────────────────────────────────────────┘
           ↓
┌─ Consolidator (iter≥3 & score≥0.80) → Finalizer │
└──────────────────────────────────────────────────┘
```

制御ロジック: `checkpoint.json` / `10KB rule` / `apply_major_penalty (major 1→0.78 cap)` / `HARD FAIL 自動修正` / `human-bench 外部キャリブレーション` / `MATERIAL_FALLBACK 逆流路`

---

## 今どこに不具合が残っていそうか（仮説マップ）

前 E2E で観測した挙動から、**L2 では直しきれていない領域**の仮説を 6 つ並べる。E2E の結果と照合して確定 / 棄却する。

### 仮説 1: 【L2 で直る見込み】 構文テンプレ残存

- 症状: 「多くの人は〜。私もそうでした」型が本文に残る
- L1 時点の原因: Reviewer の weird_phrasing 固定リストが名詞比喩のみで、構文テンプレを捕まえられない
- L2 改修: 案 2 で `detect_ai_templates` 追加、案 3（項目 8）で Reviewer が呼ぶよう義務化
- **検証方法**: iter 1 review.json の feedback に `pattern_label: general_then_assimilate` が major で 1 件以上現れるか確認。出れば次 iter で Writer が修正 → iter 2 で 0 件になるはず

### 仮説 2: 【L2 で直る見込み】 記事内自己矛盾

- 症状: 本文で批判している構造を本文他箇所で使っている
- L1 時点の原因: Reviewer が「本文全体を横断して照合」するタスクを持っていなかった
- L2 改修: 案 3（項目 9）で self-consistency 照合を義務化、常に major（降格不可）
- **検証方法**: iter 1 review.json に `axis: 絶対ルール違反, 項目 9` の major が出るか。出れば次 iter で Writer が修正。ただし LLM の照合精度に依存するので「見逃す」リスクあり

### 仮説 3: 【L2 で部分的に直る】 採点分布の 0.80-0.82 バイアス

- 症状: 前 run（postiz-agent）も今回（自己解説）も score 0.81 で収束
- L1 時点の原因: A/B 対戦相手がベンチ固定 1 本で、Reviewer 兼務のため採点が安全側に張り付く
- L2 改修: 案 5 で Round 2 に trends.md の最新ライバルを追加 → 採点分布が広がる**はず**
- **検証方法**: iter 1 の weighted_average が 0.80-0.82 帯から外れるか。Round 2 で trends ライバル（例: Hightower 記事）に負けて major 付与 → score cap 0.84 / 0.79 に落ちる挙動が出るか
- **リスク**: Round 2 で「trends.md の記事要約だけで A/B 判定する」方式が情報不足で甘い判定を出す → L3 で WebFetch 化が必要になる可能性

### 仮説 4: 【L2 で直らない】 Material PDCA の飽和

- 症状: iter 3 で Reviewer が「残 minor は Writer 実装で確定するまで届かない」と白旗、iter 4 でプレースホルダ（verification block）を追加して形式的に 0.85 通過
- 原因: MaterialReviewer に「素材層で直せない→記事層で直せ」の責任分界を判定する契約がない
- **この仮説は今回も再現する可能性が高い**（直しが入っていない）
- **検証方法**: iter 3 の material review.json の feedback に「Writer 実装で確定すべき」系の白旗が出るか。出たら案 4（MaterialReviewer に `writer_deferred: true` 契約追加）が次の優先度 1

### 仮説 5: 【L2 で直らない】 Drama Sim の情報非対称性が擬似的

- 症状: 1 agent が Human/Claude/Director 3 役を演じ分けるので「驚き」が演出品になる
- 原因: 本物の情報非対称性ではなく、単一 agent の内的 role switching
- **検証方法**: drama_raw.md を読み直して「事件発火時、Human が本当に予測できない罠だったか」を目視判断。同じ文脈で Drama を別シード 2 回走らせて、同じ中心学びに収束するかの再現性テスト（L3 で「3 agent 分離」が必要か判断する材料）

### 仮説 6: 【未検証】 外部リサーチの活用深度

- 症状: trends.md は 7 件の実在記事 + 差別化チャンス + ThesisDesigner への示唆まで豊富に入っている
- 前 E2E で分かったこと: ThesisDesigner は trends.md を読んでいる。ただし Writer / ArticleReviewer への経路が弱かった（L2 案 5 で一部解消）
- **残る課題**: trends.md の「差別化チャンス」「ThesisDesigner への示唆（避けるべきパターン / 刺さる構成）」が記事本文に本当に反映されているか。反映されていなければ ThesisDesigner の活用が形式的
- **検証方法**: iter 1 article.md の本文と trends.md の「刺さる構成パターン」を照合。例えば trends.md が「公式機能との差分で自作理由を説明する」を推奨しているとき、記事で公式 Checkpointing と自作 checkpoint.json の差分が実際に書かれているか

---

## セッション開始時の初手

```bash
git branch --show-current     # → feat/experience-authoring-drama-sim
git log --oneline -7          # → a570169, e7b1473, 965d564, ...
python3 dry_run_validate.py   # → 68 passed / 0 failed
```

dry_run_validate.py が 68/68 通ることを必ず確認してから E2E に進む。

---

## E2E 実行手順

### Step 1: 前回 output/ を退避

```bash
if [ -d output ]; then
  mv output output_prev_$(date +%Y%m%d_%H%M%S)
fi
mkdir -p output
```

### Step 2: orchestrator 起動

題材・ブリーフは前セッションと**完全に同じ**で OK（再帰 E2E の同一条件比較が L2 効果の検証になる）:

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

---

## L2 検証チェックリスト（E2E 完走後に確認）

### A. 案 2 効果（detect_ai_templates が major を付けるか）

- [ ] iter 1 の `review.json` の feedback に `pattern_label` を含む major が 1 件以上ある
- [ ] iter 2 以降で Writer が修正 → `detect_ai_templates(iter=N)` の戻り値が 0 件になる
- [ ] 最終 `final_article.md` に対して `detect_ai_templates` を実行 → 0 件

```bash
python3 -c "import sys; sys.path.insert(0, '.claude/scripts'); import metrics; \
  print(metrics.detect_ai_templates(open('output/final_article.md').read()))"
```

### B. 案 3 効果（self-consistency が自己矛盾を捕まえるか）

- [ ] iter 1 の `review.json` の feedback に `axis: "絶対ルール違反"` かつ「第 X 章で NG と宣言 vs 第 Y 章で同じ構造使用」形式の major がある（ただし今回は実記事に矛盾が無い可能性もあるので、**必ず出る**ではなく**矛盾があれば出る**の検証）
- [ ] 矛盾がなかった場合は feedback にその旨（「self-consistency: 該当なし」）が明記される

### C. 案 5 効果（Round 2 が実際に走るか）

- [ ] iter 1 の `review.json` feedback 配列に A/B Round 1（human-bench 対戦）と Round 2（trends 対戦）が**両方**含まれる
- [ ] Round 2 の対戦相手は trends.md の注目記事から選ばれている（例: Hightower 記事 / Anthropic 公式 Checkpointing docs）
- [ ] Round 2 で**本記事が負けた場合**は major が付き、score cap 0.84 / 0.79 に落ちている
- [ ] Round 2 で**本記事が勝った場合**も「ただし対戦相手が優れているのは〇〇」の付記がある

### D. 採点分布（仮説 3 の検証）

- [ ] iter 1 の weighted_average が **0.80-0.82 以外**に着地する（下振れも上振れも可）
- [ ] 着地が 0.80-0.82 なら「L2 でもバイアス残存」→ L3 で `article_ab_judge.md` 完全分離を検討

### E. Material PDCA 飽和（仮説 4 の再現確認）

- [ ] Material PDCA は何 iter で threshold 0.85 に到達したか（前回: 4 iter）
- [ ] iter 3 以降の material review.json で「Writer 実装で確定すべき」系の白旗 feedback が出るか
- [ ] 出た場合、次の改修優先度 1 は MaterialReviewer の責任分界契約（案 4）

### F. 全体サマリ（前回との同一条件比較）

- [ ] 最終 score（前回: 0.81）
- [ ] iter 数（前回: material 4 / article 1）
- [ ] 最終 final_article.md 冒頭 500 字の定性比較（前回 `output_prev_{timestamp}/final_article.md`）
- [ ] 「友人に薦めるならどっち？」の 3 行所感

---

## 完了後に報告してほしいこと

1. **L2 3 改修の観測結果**（A/B/C/D 各項目 Yes/No + 引用）
2. **前 E2E (commit `a570169` 直前の run) との並べ比較** — score / iter 数 / 定性
3. **検出された major / minor の内訳**（特に pattern_label・自己矛盾・Round 2 敗北）
4. **L3 に上げるべき残課題**の確定リスト（仮説 4 / 5 / 6 のうちどれが再現したか）
5. **実行中に起きた想定外**

---

## トラブルシュート

| 症状 | 対応 |
|---|---|
| iter 1 で major 3 件以上付与 → score 0.70 以下 | ダウングレードルール通りで想定内。iter 2 で Writer が修正できるか見る |
| detect_ai_templates が false positive を出す | 実記事の matched_text を見て、対象パターンを `AI_SYNTACTIC_TEMPLATES` から外すか、前後コンテキスト条件を足す（正規表現を絞る） |
| Round 2 で Reviewer が trends.md を読まずにスキップ | `article_reviewer.md` の A/B ブロックで trends.md 参照を再度強調 → Reviewer を再 spawn |
| self-consistency で false positive（本文が自己矛盾でないのに major） | 項目 9 の「否定宣言抽出の 5 パターン」を厳しめに絞る |
| Material iter 4 でも 0.85 届かない | 案 4 未実装の症状。max_iter=5 まで走らせて `material_fallback_count` で Article に進む |
| 無限ループ（article iter 10 到達） | 前回と同じ強制 finalize 挙動で OK。ただし「L2 でも 0.80 に届かなかった」なら L3 案件 |

---

## このセッションのゴール

**最低ライン**:
- E2E 完走 + チェックリスト A〜F 報告
- L2 の 3 改修がそれぞれ**発火した/しなかった**の確定

**理想ライン**:
- L2 で仮説 1〜3 が概ね解消されたと判断できる
- 仮説 4（Material PDCA 飽和）が再現したら、案 4 実装プロンプトを次々セッション用に書き出す
- 仮説 6（trends.md 活用深度）の判定

**判断に迷ったら実装に入る前にユーザー承認を取る**。E2E 起動は自動でよいが、改修が必要になったら修正前に報告して判断を仰ぐ。

---

## 参考: L2 コミット内容

```
a570169 feat(reviewer): add self-consistency check + A/B round 2 with trends.md
e7b1473 feat(metrics): add detect_ai_templates() for sentence-level AI patterns
```

- `metrics.py` に `AI_SYNTACTIC_TEMPLATES` 定数と `detect_ai_templates()` 関数（60 行）
- `dry_run_validate.py` に `[3b] metrics.py — AI syntactic template detection` セクション追加（4 checks）
- `article_reviewer.md` 項目 8（detect_ai_templates 呼出）+ 項目 9（self-consistency）+ A/B Round 2 追加
- `zenn-article-pdca/INSTRUCTIONS.md` Step 4 に Reviewer 入力の `knowledge/trends.md` を明示

既存関数変更ゼロ / checkpoint スキーマ変更ゼロ / dry_run_validate.py 68/68 PASS。
