# zenn-topic-selection

## 役割（v0.2 — TrendResearcher統合版）

外部テックメディアのトレンドリサーチを行い、その結果を踏まえて記事トピックを選定する。
出力: `output/knowledge/trends.md`（Material PDCAが参照）+ `output/topic.md`

将来: TopicProposer → TopicEvaluator → TopicFinalizer の 3 エージェント構成に移行予定。

## 入力

- `output/strategy.md`
- `output/knowledge/system_analysis.md`（存在する場合のみ）

## 実行手順

### Step 1: TrendResearcher — 外部メディアからトレンドリサーチ

※ ロジック詳細は次セッションで設計予定。現在は WebSearch フォールバックで動作。

- 入力: `strategy.md`（article_topic を参照）
- 調査対象メディア: 信頼性の高い英語・日本語テックメディア（詳細は次セッションで確定）
- 出力: `output/knowledge/trends.md`
  - 収集した記事タイトル・URL・概要・「なぜ読まれているか」の要因分析
- フォールバック: 取得失敗時は `[FALLBACK: trend_research_failed]` を先頭に記録し継続

### Step 2: TopicProposer — トレンドを踏まえて候補出し

- 入力: `strategy.md`, `output/knowledge/trends.md`
- 候補タイトル 3〜5 案を生成（トレンドと読者ペインの両方に刺さるもの）

### Step 3: TopicFinalizer — 選定・topic.md 出力

- 各候補を以下の観点でスコアリング:
  - 読者の痛みとの整合性（1-5）
  - トレンドとの一致度（1-5）
  - 記事化難易度（1-5、低いほど良い）
  - 差別化度（1-5）
- 最高スコアの候補を選定し `output/topic.md` に書き込む

## 出力フォーマット（output/topic.md）

```yaml
selected_title: "タイトル"
scope: "何についての記事か（1-2文）"
why_this_topic: "選定理由・読者の痛みとの関係（2-3文）"
deep_dive_targets:
  - "深掘り対象1"
  - "深掘り対象2"
```

## 制約

- 各 Step の出力ファイルに書き込んだ後、path + 2-4 文のサマリーのみ返すこと（10KB rule）
- Step 1 が失敗しても Step 2 以降は続行する（trends.md なしで候補出し）
- 全体が失敗した場合は `[FALLBACK: topic_selection_failed]` を先頭に付けた topic.md を書き込み、
  エラーで停止しない（後続の material PDCA は topic.md / trends.md 不在でも動作可能）
