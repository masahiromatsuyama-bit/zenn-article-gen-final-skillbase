```yaml
name: zenn-material-pdca
description: Material gathering PDCA — one iteration. Invoked by zenn-orchestrator.
triggers:
  - internal (called by zenn-orchestrator only)
capabilities:
  - Run one material PDCA iteration (TrendResearcher → PainExtractor → ThesisDesigner → MaterialReviewer)
  - Return {"score": float, "feedback": [...], "iter": int}
limitations:
  - Does not manage checkpoint.json (orchestrator does)
  - Does not loop — one iteration only
```
