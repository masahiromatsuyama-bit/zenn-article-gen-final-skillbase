# 次セッション引き継ぎプロンプト — 最終版

---

## あなたへの指示

このセッションでは**実装はしない**。
以下の手順で既存システムを把握し、最後にユーザーと設計方針を議論する。

---

## Step 1: まず以下のファイルを読め（この順番で）

### 既存システム（v5.0）の設計書
```
/Users/masahiromatsuyama/zenn-article-gen-final/ARCHITECTURE.md
/Users/masahiromatsuyama/zenn-article-gen-final/REQUIREMENTS.md
/Users/masahiromatsuyama/zenn-article-gen-final/CHANGELOG_v5.1.md
```

読むとき特に注目すること:
- フェーズ構成（Layer 1 → Phase 0〜3b）と13エージェントの役割
- **出力契約統一ルール**（全エージェントが stdout JSON + ファイル直書きをする理由）
- **v4.0の4.4pt乖離問題**（なぜこのシステムが必要になったか）
- **停滞判定の一次/二次二重構造**（PDCAがどう止まるか）
- CHANGELOG_v5.1の修正4件（実装とのギャップがどこにあったか）

### 既存システムの実装（バグ確認用）
```
/Users/masahiromatsuyama/zenn-article-gen-final/orchestrator/pdca.py
/Users/masahiromatsuyama/zenn-article-gen-final/orchestrator/metrics.py
/Users/masahiromatsuyama/zenn-article-gen-final/orchestrator/fb_log.py
/Users/masahiromatsuyama/zenn-article-gen-final/orchestrator/file_registry.py
```

### APAIの設計思想（新システムの設計に使うパターン）
```
/Users/masahiromatsuyama/APAI/AGENTS.md
/Users/masahiromatsuyama/APAI/.claude/skills/report-orchestrator/INSTRUCTIONS.md
/Users/masahiromatsuyama/APAI/.claude/skills/quality-gate/INSTRUCTIONS.md
/Users/masahiromatsuyama/APAI/.claude/skills/article/INSTRUCTIONS.md  ← 重要：これが既存のarticleスキル
/Users/masahiromatsuyama/APAI/.claude/rules/subagent-result-size.md
```

---

## Step 2: 読んだら以下を頭に入れろ

### プロジェクトの目的
`/Users/masahiromatsuyama/zenn-article-gen-final/` で動くZenn記事自動生成システムv5.0を、
**Anthropic API直接呼び出し方式（毎run $12-15）** から
**Claude Codeスキル方式（サブスク内、追加コストなし）** に作り直す。

新しい実装先: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/`
GitHub: `masahiromatsuyama-bit/zenn-article-gen-final-skillbase`

### クローンではなく新規実装にする理由（既存コードに埋まっているバグ3件）
1. `fb_log.py`: `save_fb_log(path, entries, [])` と常に`diffs=[]`を渡している → FBDiff未保存 → 停滞判定が壊れている
2. `pdca.py`: `check_resource_limits()`が定義されているのに一度も呼ばれていない → ABORTが事実上未実装
3. `pdca.py`: `meta_agents.py`のプロンプト定数をバイパスして `"Review materials (iter 1)"` という3語で呼ぶ箇所がある → プロンプトが効いていない

### 流用する資産（コピーして使う）
- `orchestrator/file_registry.py`（Paths定数25本・FILE_SCHEMAS・バリデーション）
- `orchestrator/metrics.py`（HARD FAIL判定・テキスト後処理関数）
- `orchestrator/escalation.py`（エスカレーション判定ロジック）
- 13エージェントのプロンプト内容（`orchestrator/meta_agents.py`から抽出）
- `human-bench/`（ベンチマーク記事）

### 設計に使うAPAIパターン（実績あり）
| v5.0の問題 | 使うAPAIパターン |
|-----------|----------------|
| RunState（in-memory、SubAgent間で共有不可） | `checkpoint.json`（phases_done/status/artifacts/abort） |
| PDCAのwhileループ | Fix Loopパターン（max N回 + ESCALATE、自動APPROVE禁止） |
| `call_agent()` → Anthropic API | SubAgent spawn（パスのみ渡す、本文渡さない） |
| stdout JSON受け取り | `handoff.json`（~50tok）+ `report.md`（無制限、LEADは読まない） |
| エージェント間コンテキスト汚染 | 10KBルール（生成物はファイルに書いてpathのみ親に返す） |

### INSTRUCTIONS.md の必須構造（APAIルール）
新スキルを作るとき以下のセクションが必須:
- Stage Dispatch Table（フェーズ・入出力・ゲート条件を表形式）
- Checkpoint スキーマ（全フィールド定義）
- Spawn Templates（SubAgent起動の固定プロンプト）
- Fix Loop 定義（REJECT時のルーティング・最大反復数）

### 重要な閾値（設計判断に必要）
- 素材PDCA: スコア閾値 0.85 / 最大5iter / **2回連続**超えで成功
- 記事PDCA: スコア閾値 0.80 / 最大10iter / **2回連続**超えで成功 / iter=5でConsolidator自動発火
- HARD FAILキャップ: code比率>20%→スコアcap0.60 / desu_masu比率<80%→cap0.55 / 連続4文超→cap0.50
- リソース上限: 500Kトークン/run・$20・120分

---

## Step 3: 把握できたらユーザーと議論する

以下の論点についてユーザーの意見を聞きながら設計方針を決める。
**決まるまで実装には入らない。**

### 論点A: APAIの`article`スキルとの関係
APAIに既存の`article`スキルがある。
- 新システムはこれを拡張するか？ 別スキルとして独立させるか？
- v5.0の13エージェント体制はそのまま踏襲するか？ 簡略化するか？

### 論点B: スキル分割粒度
- フェーズ単位（Layer1 / Phase0-1 / Phase2b / Phase3a-3b）= 4〜5スキル
- エージェント単位 = 13スキル
- どちらが保守しやすいか

### 論点C: Layer 1（MetaAgent）の扱い
v5.0ではStrategist/Agent Editor/Eval Designerがrun前に `workflow.json` と評価基準を動的生成する。
これはSkills方式でも必要か？ 固定化していいか？

### 論点D: run間学習（knowledge/・agent_memory/）の扱い
v5.0最大の独自性。run跨ぎで `style_memory/` `knowledge/` に蓄積して次runに注入する。
Skills方式でもこれを維持するか？

---

## 最後に

把握が完了したら以下のメッセージをユーザーに送って待て：

> 「既存システム（v5.0）の設計・実装・バグ、APAIのスキル設計思想、すべて把握しました。
> 設計の方向性を一緒に決めましょう。まず論点Aから聞かせてください：
> APAIに既存の`article`スキルがありますが、これを拡張して作りますか？
> それとも独立した新スキルとして設計しますか？」
