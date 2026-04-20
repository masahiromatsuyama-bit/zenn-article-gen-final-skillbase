"""FB structured log: record, diff, stagnation detection.

Copied from v5.0 with bug fix:
  v5.0 bug: save_fb_log(path, entries, []) always passed empty diffs list,
  losing all diff history. Fixed by: append_fb_diff() is the canonical
  write path; save_fb_log() now auto-computes diffs if passed empty list
  but entries exist (safe fallback).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict


@dataclass
class FBEntry:
    """Single feedback entry."""
    id: str
    iteration: int
    phase: str  # "material" | "article"
    axis: str
    severity: str  # "major" | "minor"
    description: str
    status: str  # "new" | "persisted" | "resolved"
    created_at: int
    resolved_at: int | None = None


@dataclass
class FBDiff:
    """Diff metrics between two iterations."""
    resolution_rate: float
    new_count: int
    persisted_count: int
    major_persisted_count: int
    major_persisted_streak: int


def load_fb_log(path: str) -> list[FBEntry]:
    """Load FB entries from *path*. Returns [] if file missing."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [FBEntry(**e) for e in data.get("entries", [])]


def save_fb_log(
    path: str,
    entries: list[FBEntry],
    diffs: list[dict],
) -> None:
    """Persist entries and diffs to *path*.

    BUG FIX vs v5.0: If diffs is empty but entries exist, auto-compute diffs
    so history is never silently lost. Use append_fb_diff() as the canonical
    write path when possible.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not diffs and entries:
        diffs = _compute_simple_diffs(entries)
    data = {
        "entries": [asdict(e) for e in entries],
        "diffs": diffs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _compute_simple_diffs(entries: list[FBEntry]) -> list[dict]:
    """Compute simple per-iteration diff summary from entries."""
    by_iter: dict[int, list[FBEntry]] = {}
    for e in entries:
        by_iter.setdefault(e.iteration, []).append(e)
    result = []
    for it in sorted(by_iter):
        iter_entries = by_iter[it]
        result.append({
            "iteration": it,
            "new_count": sum(1 for e in iter_entries if e.status == "new"),
            "persisted_count": sum(1 for e in iter_entries if e.status == "persisted"),
            "resolved_count": sum(1 for e in iter_entries if e.status == "resolved"),
            "major_persisted_count": sum(
                1 for e in iter_entries if e.status == "persisted" and e.severity == "major"
            ),
        })
    return result


def record_fb(
    entries: list[FBEntry],
    new_feedbacks: list[dict],
    iteration: int,
    phase: str,
) -> list[FBEntry]:
    """Record new FBs and update statuses of existing entries."""
    prefix = "FB-M-" if phase == "material" else "FB-A-"
    max_seq = 0
    for e in entries:
        if e.id.startswith(prefix):
            try:
                seq = int(e.id[len(prefix):])
                max_seq = max(max_seq, seq)
            except ValueError:
                pass

    matched_fb_indices: set[int] = set()
    updated_entries = list(entries)

    for e in updated_entries:
        if e.phase != phase or e.status == "resolved" or e.resolved_at is not None:
            continue
        if e.status not in ("new", "persisted"):
            continue
        found_match = False
        for i, fb in enumerate(new_feedbacks):
            if i in matched_fb_indices:
                continue
            if fb["axis"] == e.axis and fb["severity"] == e.severity:
                e.status = "persisted"
                e.iteration = iteration
                matched_fb_indices.add(i)
                found_match = True
                break
        if not found_match:
            e.status = "resolved"
            e.resolved_at = iteration

    for i, fb in enumerate(new_feedbacks):
        if i in matched_fb_indices:
            continue
        max_seq += 1
        updated_entries.append(FBEntry(
            id=f"{prefix}{max_seq:03d}",
            iteration=iteration,
            phase=phase,
            axis=fb["axis"],
            severity=fb["severity"],
            description=fb.get("text", ""),
            status="new",
            created_at=iteration,
        ))

    return updated_entries


def compute_fb_diff(
    prev_entries: list[FBEntry],
    curr_entries: list[FBEntry],
) -> FBDiff:
    """Compute diff metrics between previous and current FB states."""
    prev_active = [e for e in prev_entries if e.status in ("new", "persisted")]
    resolved_ids = {e.id for e in curr_entries if e.status == "resolved"}
    resolved_from_prev = sum(1 for e in prev_active if e.id in resolved_ids)
    resolution_rate = resolved_from_prev / len(prev_active) if prev_active else 0.0
    new_count = sum(1 for e in curr_entries if e.status == "new")
    persisted_count = sum(1 for e in curr_entries if e.status == "persisted")
    major_persisted_count = sum(
        1 for e in curr_entries if e.status == "persisted" and e.severity == "major"
    )
    return FBDiff(
        resolution_rate=resolution_rate,
        new_count=new_count,
        persisted_count=persisted_count,
        major_persisted_count=major_persisted_count,
        major_persisted_streak=major_persisted_count,
    )


def append_fb_diff(
    path: str,
    entries: list[FBEntry],
    prev_entries: list[FBEntry],
    iteration: int,
    phase: str,
) -> FBDiff:
    """Compute diff, update streak, append to fb_log, return FBDiff.

    This is the canonical write path — use instead of save_fb_log(..., []).
    """
    diff = compute_fb_diff(prev_entries, entries)

    phase_diffs = _load_diffs(path, phase)
    streak = 0
    for d in reversed(phase_diffs):
        if d.get("major_persisted_count", 0) > 0:
            streak += 1
        else:
            break
    streak = streak + 1 if diff.major_persisted_count > 0 else 0
    diff.major_persisted_streak = streak

    all_diffs: list[dict] = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            all_diffs = json.load(f).get("diffs", [])

    diff_dict = asdict(diff)
    diff_dict["phase"] = phase
    diff_dict["iteration"] = iteration
    all_diffs.append(diff_dict)

    save_fb_log(path, entries, all_diffs)
    return diff


def _load_diffs(fb_log_path: str, phase: str) -> list[dict]:
    if not os.path.isfile(fb_log_path):
        return []
    with open(fb_log_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [d for d in data.get("diffs", []) if d.get("phase") == phase]
