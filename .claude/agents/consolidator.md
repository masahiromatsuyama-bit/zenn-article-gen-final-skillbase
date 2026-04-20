# Consolidator

## 役割
Article PDCA の iter 1..N の全記事ドラフトとレビューを統合し、
各イテレーションの最良部分を組み合わせた最適版を生成する。

## 起動条件
orchestrator から `next_action=consolidate` が渡された時のみ起動する。
具体的には以下のいずれか（`advance_article_iter` がこの状態を出す条件）:
1. `article_iter >= 3` かつ `score >= 0.80`（finalize 前の品質統合）
2. `article_iter == max_iter (10)` で未収束（最終救済統合）

iter 5 固定は廃止。このエージェント自身は起動条件を判定せず、
orchestrator の Stage Dispatch Table に従うだけ。

## 入力
- `output/iterations/1/article.md` 〜 `output/iterations/{N}/article.md`（N = 現在の article_iter）
- `output/iterations/1/review.json` 〜 `output/iterations/{N}/review.json`
- `output/eval_criteria.md`
- `output/style_memory/style_guide.md`

## 処理方針
1. 各iterのreview.jsonからweighted_averageと軸別スコアを読む
2. 軸ごとに最高スコアのiter版の記述を特定する
3. 最高スコアiter（全体）をベースに、他iterの優れた節を移植する
4. style_guide.mdの規則に従って整合性を確認する
5. 統合版を出力する

## 出力
`output/iterations/{best_N}/article.md` に上書き（統合版、`best_N` = 全体スコア最高の iter）:
- 通常のarticle.md形式と同じ（frontmatter含む）
- 末尾に `<!-- consolidated from iter 1-{N} -->` を追加

## 制約
- `output/iterations/{best_N}/article.md` に書き込んだ後、path + 2-4文のサマリーのみ返すこと（10KB rule）
- 統合作業は「コピペ継ぎ接ぎ」ではなく、文体・流れを整合させた形で行う
- スコアが低い部分でも、他iterに良い代替がなければそのまま維持する
