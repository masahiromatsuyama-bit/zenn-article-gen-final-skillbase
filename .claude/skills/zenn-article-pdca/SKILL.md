```yaml
name: zenn-article-pdca
description: Article writing PDCA — one iteration. Invoked by zenn-orchestrator.
triggers:
  - internal (called by zenn-orchestrator only)
capabilities:
  - Run one article PDCA iteration (Writer → StyleGuideUpdater → ArticleReviewer)
  - At iter 5: additionally spawn Consolidator
  - Apply HARD FAIL caps via metrics.py
  - Return {"score": float, "feedback": [...], "iter": int, "hard_fail_applied": bool}
limitations:
  - Does not manage checkpoint.json
  - Does not call Finalizer (orchestrator does)
  - One iteration only
```
