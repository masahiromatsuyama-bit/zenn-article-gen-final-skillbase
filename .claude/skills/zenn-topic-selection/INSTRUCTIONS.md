# zenn-topic-selection

## 役割（v0.3 — TrendResearcher 実装版）

外部テックメディアのトレンドリサーチを行い、その結果を踏まえて記事トピックを選定する。
出力: `output/knowledge/trends.md`（Material PDCAが参照）+ `output/topic.md`

将来: TopicProposer → TopicEvaluator → TopicFinalizer の 3 エージェント構成に移行予定。

## 入力

- `output/strategy.md`
- `output/knowledge/system_analysis.md`（存在する場合のみ）

---

## 実行手順

### Step 1: TrendResearcher — 外部メディアからトレンドリサーチ

#### 1-0. strategy.md から article_topic を読み取る

```python
import re, pathlib

strategy = pathlib.Path("output/strategy.md").read_text()
# article_topic: フィールドを正規表現で抽出。見つからなければ空文字
m = re.search(r'article_topic\s*:\s*"?(.+?)"?\s*$', strategy, re.MULTILINE)
article_topic = m.group(1).strip() if m else ""
```

`article_topic` が空の場合は strategy.md 全体を要約して代替クエリを生成すること（処理は継続）。

#### 1-1. 調査クエリの生成

`article_topic` を元に以下の **8 クエリ** を生成する（記事化予定テーマを中心に、広め・深めの両方を含める）:

| # | 対象メディア | 言語 | クエリ例（article_topic = "Claude Codeで記事自動生成" の場合） |
|---|------------|------|---------------------------------------------------------------|
| 1 | Zenn | 日本語 | `site:zenn.dev {article_topic} 2025 OR 2026` |
| 2 | Zenn | 日本語 | `site:zenn.dev LLMエージェント 設計 実践` |
| 3 | Qiita | 日本語 | `site:qiita.com {article_topic} 実装` |
| 4 | Anthropic Blog | 英語 | `site:anthropic.com {english_topic} 2026` |
| 5 | dev.to | 英語 | `site:dev.to LLM agent workflow 2026` |
| 6 | Hacker News | 英語 | `site:news.ycombinator.com {english_topic}` |
| 7 | 横断 日本語 | 日本語 | `{article_topic} 記事 LLM エージェント 2025 OR 2026` |
| 8 | 横断 英語 | 英語 | `{english_topic} best practices tutorial 2025 OR 2026` |

`english_topic` は article_topic を英語に意訳したもの（LLM で生成する）。

#### 1-2. genspark search でURL収集

**genspark スクリプトパス**: `~/APAI/.claude/skills/genspark/scripts/genspark`（絶対パスに展開して使用）

```bash
GENSPARK=~/./../APAI/.claude/skills/genspark/scripts/genspark
# または
GENSPARK="$(python3 -c "import pathlib; print(pathlib.Path.home() / 'APAI/.claude/skills/genspark/scripts/genspark')")"
```

8 クエリを **順次** 実行し、URLとタイトルを収集する:

```bash
$GENSPARK search "{クエリ1}" 2>/dev/null
$GENSPARK search "{クエリ2}" 2>/dev/null
...
```

- 各 search の stdout は JSON 形式。`results[].url` と `results[].title` を抽出する。
- URL 重複除去後、**最大 20 件** を候補リストに保持する。
- genspark search が完全失敗（全クエリでエラー）した場合 → **WebSearch フォールバック**（後述）へ。

#### 1-3. genspark crawl で本文取得（上位 10 件）

収集した URL から **読者関心が高そうな上位 10 件** を選定し、本文を取得する:

```bash
$GENSPARK crawl "{url}" 2>/dev/null
```

- crawl の stdout（JSON）から `content` または `text` フィールドを抽出し、**1000 字以内** に要約する。
- crawl 失敗（個別URL）→ タイトル・URLのみ記録、`crawl_failed: true` フラグを立てて継続。
- crawl が 10 件すべて失敗 → search で得たタイトル・URLのみで trends.md を生成して継続。

#### 1-4. WebSearch フォールバック

genspark search が完全失敗した場合、以下の 3 クエリで WebSearch を実行する:

1. `Zenn {article_topic} 人気 記事 2025 2026`
2. `{article_topic} LLM エージェント 実装 実践`
3. `{english_topic} AI agent development tutorial 2026`

WebSearch 結果からタイトル・URL を抽出し、crawl なしで trends.md を生成する。
先頭に `[FALLBACK: genspark_unavailable]` を記録する。

#### 1-5. trends.md の生成

収集した情報を統合し、`output/knowledge/trends.md` に書き込む。

**必須フォーマット**:

```markdown
# トレンド分析（TrendResearcher 出力）

分析日: {YYYY-MM-DD}
ソース: {使用したメディア一覧}
収集件数: {n}件（crawl成功: {m}件）

---

## トレンド記事一覧

### 1. {タイトル}
- **URL**: {url}
- **媒体**: {Zenn / Qiita / Anthropic Blog / dev.to / HackerNews / Other}
- **概要**: {100-150字の要約。crawl_failedの場合はタイトルから推測}
- **なぜ読まれているか**: {以下の観点で100-200字で分析}
  - 読者の課題/ペイン: ...
  - 新規性/希少性: ...
  - 実践性/再現性: ...

（以下 10〜15件繰り返し）

---

## トレンドパターン分析

### 読者が今求めているもの（上位3テーマ）
1. ...
2. ...
3. ...

### 差別化チャンス（まだ書かれていない切り口）
- ...
- ...

### ThesisDesignerへの示唆
- **避けるべきパターン**: {既に飽和している角度}
- **刺さる構成パターン**: {読まれている記事に共通する構成の特徴}
- **読者の最大ペイン**: {最も多く言及されていた課題}
```

- **「なぜ読まれているか」分析は必須**。crawl 失敗でもタイトルから推測して記入すること。
- 件数: 最低 5 件（それ以下は `[WARN: insufficient_data]` を先頭に追加）。
- 「トレンドパターン分析」セクションは記事一覧が 1 件以上あれば必ず生成する。

#### 1-6. 失敗時の完全フォールバック

search + WebSearch が両方失敗した場合:

```markdown
[FALLBACK: trend_research_failed]

# トレンド分析（TrendResearcher 出力）

分析日: {YYYY-MM-DD}
ソース: フォールバック（外部取得失敗）

## トレンドパターン分析

### ThesisDesignerへの示唆
- トレンドデータ取得に失敗したため、strategy.md の article_topic と読者ペインを優先して Thesis を設計してください。
```

このファイルを書き込んで **Step 2 に進む**（停止しない）。

---

### Step 2: TopicProposer — トレンドを踏まえて候補出し

- 入力: `output/strategy.md`, `output/knowledge/trends.md`（存在する場合のみ）
- `trends.md` がない / `[FALLBACK]` ヘッダーあり → strategy.md の article_topic と読者セグメントだけで候補生成
- 候補タイトル **3〜5 案** を生成する基準:
  - トレンドパターン分析の「差別化チャンス」に合致するか
  - 読者の最大ペインに刺さるか
  - 記事化難易度が現実的か（著者のテーマ習熟度を考慮）
- 各案に **候補メモ**（なぜこのタイトルか 1-2文）を付ける

### Step 3: TopicFinalizer — 選定・topic.md 出力

各候補を以下の観点でスコアリング:

| 観点 | 説明 | 点数 |
|------|------|------|
| 読者ペイン整合性 | strategy.md の読者ペインとの一致度 | 1-5 |
| トレンド一致度 | trends.md のトレンドパターンとの一致度 | 1-5 |
| 記事化難易度 | 低いほど良い（著者が書ける範囲か） | 1-5（低=良） |
| 差別化度 | 既存記事と被っていないか | 1-5 |

合計スコア最大の候補を選定し `output/topic.md` に書き込む。

---

## 出力フォーマット（output/topic.md）

```yaml
selected_title: "タイトル"
scope: "何についての記事か（1-2文）"
why_this_topic: "選定理由・読者の痛みとの関係（2-3文）"
trend_alignment: "どのトレンドに乗っているか（1文）"
deep_dive_targets:
  - "深掘り対象1"
  - "深掘り対象2"
```

---

## 制約

- 各 Step の出力ファイルに書き込んだ後、path + 2-4 文のサマリーのみ返すこと（10KB rule）
- Step 1 が失敗しても Step 2 以降は続行する（trends.md なしで候補出し）
- 全体が失敗した場合は `[FALLBACK: topic_selection_failed]` を先頭に付けた topic.md を書き込み、
  エラーで停止しない（後続の material PDCA は topic.md / trends.md 不在でも動作可能）
- genspark crawl は 1 URL ずつ順次実行すること（並列実行禁止 — API quota 消費を抑えるため）
