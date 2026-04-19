# 次セッション引き継ぎプロンプト — zenn-article-gen-final-skillbase

## このセッションの作業ログ
- GitHub repo作成: `masahiromatsuyama-bit/zenn-article-gen-final-skillbase` ✅
- ローカルrepo初期化: `/Users/masahiromatsuyama/zenn-article-gen-final-skillbase/` ✅
- MCPグローバル設定:
  - `~/.claude/mcp.json` に **playwright** + **context7** を追加 ✅
  - `.mcp.json`（このrepo）に **serena** を追加 ✅

---

## 背景

`zenn-article-gen-final`（`masahiromatsuyama-bit/zenn-article-gen-final`）でZenn記事自動生成システムv5.0を実装済みだが、**Anthropic API直接呼び出し方式（毎run $12-15）** から **Claude Code スキル方式（サブスク内、追加コストなし）** に転換するため新repoで作り直す。

---

## v5.0から引き継ぐ資産（参照元: `/Users/masahiromatsuyama/zenn-article-gen-final/`）

| 資産 | ファイル | 用途 |
|------|---------|------|
| アーキテクチャ設計 | `ARCHITECTURE.md` | フェーズ構成、エージェント出力契約 |
| エージェント詳細 | `ARCHITECTURE_appendix_agents.md` | 15エージェント責務、ファイルパスレジストリ |
| 要件・閾値 | `REQUIREMENTS.md` | 閾値一覧（§6）、PDCA要件、エスカレーション |
| 変更ログ | `CHANGELOG_v5.1.md` | v5.0からの修正4件 |
| ペルソナ記事 | `human-bench/` | 品質評価のベンチマーク（8本） |
| Pythonツール候補 | `orchestrator/metrics.py` | fix_desu_masu(), fix_consecutive_length(), HARD FAIL判定 |
| Pythonツール候補 | `orchestrator/fb_log.py` | FB記録・差分計算 |

---

## 次セッションでやること

### Step 1: v5.0の設計を把握する
以下の順で読む（読むだけ、実装しない）:
1. `ARCHITECTURE.md` — 全体像、フェーズ構成（Layer 0〜4）
2. `ARCHITECTURE_appendix_agents.md` — エージェント責務
3. `REQUIREMENTS.md` § 6 — 閾値一覧
4. `CHANGELOG_v5.1.md` — 修正4件の把握

### Step 2: v2のアーキテクチャを設計する
以下の論点を決める:

**A. スキル構成**
- 1スキル = 1エージェント？ or フェーズ（Layer）単位？
- 推奨: Layer単位（Layer0/1/2/3/4 × それぞれ1スキル）+ 親スキル`/generate-article`

**B. PDCAループの実現**
- `/loop`スキル活用 vs スキル内ループ vs 親スキルが判断して再実行
- 推奨: 親スキルがPDCA判定し、必要なLayerを再実行（最大N回）

**C. コンテキスト汚染対策**
- 各Layerの入出力はファイル（`output/`）経由でやり取り
- エージェント間でcontext共有しない（SubAgent-First + File Handoff）
- 詳細: `.claude/rules/subagent-result-size.md`（APAIリポジトリ参照）

**D. Pythonツール（metrics.py等）の呼び出し**
- Bashツールで直接呼び出す（LLMで再実装せず、既存Pythonをそのまま使う）

### Step 3: ガードレール設計
- 入力バリデーション（テーマの長さ、禁止ワード等）
- 出力品質ゲート（HARD FAIL条件）
- コンテキスト膨張対策（各スキルのoutput上限サイズ）
- エスカレーション（N回PDCA失敗時の挙動）

### Step 4: CLAUDE.md作成
このrepo専用の`CLAUDE.md`を作成し、スキル構成・ガードレール・ファイルレイアウトを記述

### Step 5: スキル実装（Layer 1だけ先にテスト）
- `.claude/skills/` にスキルを配置
- Layer 1（テーマ分析・構成設計）だけ実行して動作確認

---

## ディレクトリ構成案（未確定）

```
zenn-article-gen-final-skillbase/
├── .claude/
│   ├── skills/
│   │   ├── generate-article/    # 親スキル（PDCAオーケストレータ）
│   │   ├── layer0-setup/        # テーマ解析・方針決定
│   │   ├── layer1-structure/    # 構成設計
│   │   ├── layer2-draft/        # 本文生成
│   │   ├── layer3-review/       # レビュー・採点
│   │   └── layer4-polish/       # 仕上げ・公開準備
│   └── tools/                   # metrics.py等のPythonツール
├── output/                      # 生成物（gitignore）
├── human-bench/                 # ベンチマーク記事（v5.0から移植）
└── CLAUDE.md
```

---

## 注意事項

- **MCP（serena）**: このrepoで `claude` を起動すると serena が自動接続される。初回は `uvx` がインストールを行うため少し時間がかかる。`uvx`が入っていない場合は `pip install uv` が必要。
- **context7**: どのrepoでも使えるようになっている（`~/.claude/mcp.json`）。ライブラリのドキュメント参照に活用。
- **v5.0設計書**: 読むときは `/Users/masahiromatsuyama/zenn-article-gen-final/` を参照。このv2repoにはコピーしない（参照のみ）。

---

## 参考: v5.0の主要閾値（REQUIREMENTS.md §6 より）

事前に把握しておくと設計が早い:
- Similarity Floor: ≥ 0.72
- Originality Ceiling: ≤ 0.85
- HARD FAIL条件: 連続3文以上の「です・ます」体 / 1文が140文字超
- PDCA最大ループ: 4回
- Layer 3評価軸: 10軸（独自性・構成・具体性 等）
