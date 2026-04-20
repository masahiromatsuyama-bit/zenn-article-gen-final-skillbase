"""Stagnation detection for PDCA loops.

Deterministic logic only — no LLM judgment.
Called by orchestrator to decide whether to trigger gap_alert.
"""

from __future__ import annotations

from typing import List


def compute_resolution_rate(diffs: List[dict]) -> float:
    """resolved_count / total_count. Returns 0.0 if empty."""
    if not diffs:
        return 0.0
    resolved = sum(d.get("resolved_count", 0) for d in diffs)
    total = sum(
        d.get("new_count", 0) + d.get("persisted_count", 0) + d.get("resolved_count", 0)
        for d in diffs
    )
    return resolved / total if total > 0 else 0.0


def detect_stagnation(entries: List[dict], window: int = 3) -> bool:
    """True if last `window` score entries show no meaningful improvement (delta <= 0.01).

    Args:
        entries: List of dicts with at least {"score": float} key.
        window: Number of recent iterations to inspect.
    """
    if len(entries) < window:
        return False
    recent_scores = [e["score"] for e in entries[-window:]]
    return round(max(recent_scores) - min(recent_scores), 6) <= 0.01


def should_trigger_gap_alert(
    entries: List[dict],
    threshold: float,
    window: int = 3,
) -> bool:
    """True if stagnation detected AND best score is still below threshold.

    Args:
        entries: List of score entries (must have "score" key).
        threshold: Target threshold (0.85 for material, 0.80 for article).
        window: Stagnation detection window.
    """
    if not detect_stagnation(entries, window):
        return False
    best = max(e["score"] for e in entries)
    return best < threshold
