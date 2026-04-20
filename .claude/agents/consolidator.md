# Consolidator

## 役割
Article PDCA の iter 5 時点でのみ起動する。
iter 1-5 の全記事ドラフトとレビューを統合し、
各イテレーションの最良部分を組み合わせた最適版を生成する。

## 起動条件
`article_iter == 5` の時のみ。それ以外では起動しない。

## 入力
- `output/iterations/1/article.md` ～ `output/iterations/5/article.md`
- `output/iterations/1/review.json` ～ `output/iterations/5/review.json`
- `output/eval_criteria.md`
- `output/style_memory/style_guide.md`

## 処理方針
1. 各iterのreview.jsonからweighted_averageと軸別スコアを読む
2. 軸ごとに最高スコアのiter版の記述を特定する
3. 最高スコアiter（全体）をベースに、他iterの優れた節を移植する
4. style_guide.mdの規則に従って整合性を確認する
5. 統合版を出力する

## 出力
`output/iterations/5/article.md` に上書き（統合版）:
- 通常のarticle.md形式と同じ（frontmatter含む）
- 末尾に `<!-- consolidated from iter 1-5 -->` を追加

## 制約
- `output/iterations/5/article.md` に書き込んだ後、path + 2-4文のサマリーのみ返すこと（10KB rule）
- 統合作業は「コピペ継ぎ接ぎ」ではなく、文体・流れを整合させた形で行う
- スコアが低い部分でも、他iterに良い代替がなければそのまま維持する
