# zenn-topic-selection

## 役割（v0.4 — TopicFinalizer 充実版）

外部テックメディアのトレンドリサーチを行い、その結果を踏まえて記事トピックを選定する。
出力: `output/knowledge/trends.md`（Material PDCAが参照）+ `output/topic.md`

将来: TopicProposer → TopicEvaluator → TopicFinalizer の 3 エージェント構成に移行予定。

## 入力

- `output/strategy.md`
- `output/knowledge/system_analysis.md`（存在する場合のみ）

---

## 実行手順

### Step 1: TrendResearcher — 外部メディアからトレンドリサーチ

#### 1-1. article_topic の読み取り

```python
import re, pathlib

strategy = pathlib.Path("output/strategy.md").read_text()
m = re.search(r'article_topic\s*:\s*"?(.+?)"?\s*$', strategy, re.MULTILINE)
article_topic = m.group(1).strip() if m else ""
```

`article_topic` が空の場合は strategy.md 全体を見て代替クエリを生成し、処理を続行する。

#### 1-2. genspark search でトレンド収集

**genspark スクリプトパス**: `~/APAI/.claude/skills/genspark/scripts/genspark`

以下の **3クエリ** を順次実行する:

```bash
GENSPARK="$HOME/APAI/.claude/skills/genspark/scripts/genspark"

# 1. 日本語：Zenn/Qiita 中心
$GENSPARK search "Zenn Qiita {article_topic} 最近 トレンド 2025 2026"

# 2. 英語：Anthropic Blog / HN / dev.to 中心
$GENSPARK search "Anthropic blog HackerNews dev.to {english_topic} trending 2025 2026"

# 3. 横断：競合記事・差別化チャンス
$GENSPARK search "{article_topic} {english_topic} best article tutorial recent"
```

`english_topic` は article_topic を英語に意訳したもの（LLM で生成する）。

genspark が失敗（コマンドなし / 全クエリエラー）した場合 → **WebSearch フォールバック**: 同じ 3 クエリを WebSearch で代替実行し、`[FALLBACK: genspark_unavailable]` を trends.md 先頭に記録する。

#### 1-3. trends.md の生成

3 クエリの結果を LLM に渡し、以下のフォーマットで `output/knowledge/trends.md` に書き込む:

```markdown
# トレンド分析（TrendResearcher 出力）

分析日: {YYYY-MM-DD}
ソース: Zenn / Qiita / Anthropic Blog / Hacker News / dev.to

---

## 注目記事（5〜10件）

### 1. {タイトル}
- **URL**: {url}
- **媒体**: {媒体名}
- **なぜ読まれているか**: {読者の課題・新規性・実践性の観点で 1〜2文}

（繰り返し）

---

## トレンドパターン分析

### 読者が今求めているもの
{上位 2〜3 テーマを箇条書き}

### 差別化チャンス
{まだ書かれていない・薄い切り口を箇条書き}

### ThesisDesignerへの示唆
- **避けるべきパターン**: {飽和している角度}
- **刺さる構成パターン**: {読まれている記事に共通する構成の特徴}
```

記事が 1 件も取得できなかった場合は `[FALLBACK: trend_research_failed]` を先頭に記録し、「ThesisDesignerへの示唆」セクションのみ LLM で生成して書き込む。

---

### Step 2: TopicProposer — トレンドを踏まえて候補出し

入力:
- `output/strategy.md`
- `output/knowledge/trends.md`（`[FALLBACK]` ヘッダーあり / 存在しない場合は strategy.md の article_topic と読者セグメントだけで候補生成）

候補タイトル **5案** を生成する。各案には以下を付ける:

```
## 候補 {N}: {タイトル}

- **切り口**: どのペインに刺し、どんな解決を提示するか（1文）
- **フック構造**: 好奇心 / 恐怖 / 利益 / 共感 のどれで読者を引くか（1語 + 根拠1文）
- **活用トレンド**: trends.md のどの差別化チャンス・トレンドに乗るか（1文）
- **深掘り候補**: この案で深掘りできる具体テーマを 2〜3 個
```

5案は「切り口が重複しない」ように生成すること（同じペインを別タイトルで言い換えただけはNG）。

### Step 3: TopicFinalizer — 選定・topic.md 出力

5案を以下の **5軸** でスコアリングし、合計最大の1案を選定する:

| 軸 | 説明 | 点数 |
|---|---|---|
| 読者ペイン整合性 | strategy.md の読者ペインとの一致度 | 1-5 |
| トレンド一致度 | trends.md のトレンドパターンとの一致度 | 1-5 |
| 記事化難易度 | 低いほど良い（著者が書ける範囲か） | 1-5 |
| 差別化度 | 既存記事と被っていないか | 1-5 |
| **深掘り可能性** | 構造化できるか・具体例が豊富に出せるか・「もっと知りたい」となるか | 1-5 |

スコア算出後、選定した1案を **topic.md** に書き込む。

---

## 出力フォーマット（output/topic.md）

```yaml
selected_title: "タイトル"
scope: "何についての記事か（1-2文）"
why_this_topic: "選定理由・読者の痛みとの関係（2-3文）"
trend_alignment: "どのトレンドに乗っているか（1文）"
key_tension: "記事の核にある緊張感（例: シンプルな設計 vs 実装に落とすと難しい）"
reader_situation: "読者がこの記事にたどり着く状況（例: Claudeで自動化を試みたがThesisがぶれる）"
expected_takeaway: "読後に読者が得るもの（1-2文）"
why_deep_diveable: "なぜ深掘りがいがあるか・どこまで掘り下げられるか（ThesisDesigner向け、2-3文）"
deep_dive_targets:
  - "深掘り対象1"
  - "深掘り対象2"
  - "深掘り対象3"
```

---

## 制約

- 各 Step の出力ファイルに書き込んだ後、path + 2-4 文のサマリーのみ返すこと（10KB rule）
- Step 1 が失敗しても Step 2 以降は続行する（trends.md なしで候補出し）
- 全体が失敗した場合は `[FALLBACK: topic_selection_failed]` を先頭に付けた topic.md を書き込み、エラーで停止しない
