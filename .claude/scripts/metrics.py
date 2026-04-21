"""Article metrics, HARD FAIL checks, and post-processing fixes.

Copied from v5.0 orchestrator/metrics.py — no changes needed (pure computation).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ArticleMetrics:
    """Computed article quality metrics."""
    code_ratio: float
    desu_masu_ratio: float
    max_consecutive_same_length: int


@dataclass
class HardFailResult:
    """HARD FAIL check result."""
    applied: bool
    cap: float | None
    reasons: list[str] = field(default_factory=list)


# v5.1 default thresholds (no external config file needed)
DEFAULT_HARD_FAIL = {
    "code_ratio_limit": 0.20,
    "code_ratio_cap": 0.60,
    "desu_masu_min": 0.80,
    "desu_masu_cap": 0.55,
    "consecutive_length_max": 4,
    "consecutive_length_cap": 0.50,
}

_DESU_MASU_RE = re.compile(
    r"(です|ます|でした|ました|ません|でしょう|でしょうか)"
    r"[^。！？\!\?]*"
    r"[。！？\!\?]?\s*$"
)


def compute_article_metrics(article_text: str) -> ArticleMetrics:
    """Compute code ratio, desu-masu ratio, and consecutive length."""
    lines = article_text.split("\n")
    in_code = False
    code_lines = 0
    total_lines = len(lines)
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            code_lines += 1
    code_ratio = code_lines / total_lines if total_lines > 0 else 0.0
    sentences = _extract_sentences(article_text)
    desu_masu_count = sum(1 for s in sentences if _DESU_MASU_RE.search(s))
    total_sentences = len(sentences)
    desu_masu_ratio = desu_masu_count / total_sentences if total_sentences > 0 else 1.0
    max_consec = _max_consecutive_same_length(sentences)
    return ArticleMetrics(
        code_ratio=code_ratio,
        desu_masu_ratio=desu_masu_ratio,
        max_consecutive_same_length=max_consec,
    )


def _extract_sentences(text: str) -> list[str]:
    """Split text into sentences, excluding code blocks/headings/quotes/frontmatter/tables."""
    lines = text.split("\n")
    in_code = False
    in_frontmatter = False
    sentences: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # YAML frontmatter: only when "---" is the very first line
        if i == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if (in_code or stripped.startswith("#") or not stripped
                or stripped.startswith(">") or stripped.startswith("|")):
            continue
        parts = re.split(r"(?<=[。！？\!\?])", stripped)
        for p in parts:
            p = p.strip()
            if p:
                sentences.append(p)
    return sentences


def _max_consecutive_same_length(sentences: list[str]) -> int:
    """Find longest run of sentences within ±10 chars of each other."""
    if not sentences:
        return 0
    lengths = [len(s) for s in sentences]
    max_run = 1
    current_run = 1
    for i in range(1, len(lengths)):
        if abs(lengths[i] - lengths[i - 1]) <= 10:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    return max_run


def check_hard_fail(
    metrics: ArticleMetrics,
    hf: dict | None = None,
) -> HardFailResult:
    """Check HARD FAIL conditions. Returns lowest cap if multiple apply.

    Args:
        metrics: Computed article metrics.
        hf: Hard fail thresholds dict. Defaults to DEFAULT_HARD_FAIL.
    """
    if hf is None:
        hf = DEFAULT_HARD_FAIL
    reasons: list[str] = []
    caps: list[float] = []
    if metrics.code_ratio > hf["code_ratio_limit"]:
        reasons.append(f"code_ratio {metrics.code_ratio:.2f} > {hf['code_ratio_limit']}")
        caps.append(hf["code_ratio_cap"])
    if metrics.desu_masu_ratio < hf["desu_masu_min"]:
        reasons.append(f"desu_masu_ratio {metrics.desu_masu_ratio:.2f} < {hf['desu_masu_min']}")
        caps.append(hf["desu_masu_cap"])
    if metrics.max_consecutive_same_length > hf["consecutive_length_max"]:
        reasons.append(
            f"consecutive_same_length {metrics.max_consecutive_same_length} "
            f"> {hf['consecutive_length_max']}"
        )
        caps.append(hf["consecutive_length_cap"])
    if caps:
        return HardFailResult(applied=True, cap=min(caps), reasons=reasons)
    return HardFailResult(applied=False, cap=None, reasons=[])


def apply_hard_fail(review_score: float, hard_fail: HardFailResult) -> float:
    """Apply HARD FAIL cap: min(review_score, cap)."""
    if not hard_fail.applied or hard_fail.cap is None:
        return review_score
    return min(review_score, hard_fail.cap)


def apply_major_penalty(score: float, major_count: int) -> float:
    """Cap score based on number of unresolved major feedback items.

    Aligned with the downstream thresholds in checkpoint.py:
      - 3+ major: cap to 0.70 (triggers MATERIAL_FALLBACK if article_iter >= 3)
      - 2 major:  cap to 0.79 (below article threshold 0.80)
      - 1 major:  cap to 0.78 (below article threshold 0.80 and material threshold 0.85)
      - 0 major:  no change
    """
    if major_count >= 3:
        return min(score, 0.70)
    if major_count >= 2:
        return min(score, 0.79)
    if major_count >= 1:
        return min(score, 0.78)
    return score


_DA_ENDINGS = [
    (re.compile(r"ものだ([。]?\s*)$"), r"ものです\1"),
    (re.compile(r"ことだ([。]?\s*)$"), r"ことです\1"),
    (re.compile(r"([^い])だ([。]?\s*)$"), r"\1です\2"),
    (re.compile(r"である([。]?\s*)$"), r"です\1"),
    (re.compile(r"ないだろう([。]?\s*)$"), r"ないでしょう\1"),
]


def fix_desu_masu(article_text: str, target_ratio: float = 0.85) -> str:
    """Mechanically fix desu-masu ratio to reach *target_ratio*."""
    result_lines = article_text.split("\n")
    for _ in range(3):
        text = "\n".join(result_lines)
        m = compute_article_metrics(text)
        if m.desu_masu_ratio >= target_ratio:
            break
        result_lines = _apply_da_fixes(result_lines)
    return "\n".join(result_lines)


def _apply_da_fixes(lines: list[str]) -> list[str]:
    in_code = False
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            result.append(line)
            continue
        if in_code or stripped.startswith("#") or stripped.startswith(">"):
            result.append(line)
            continue
        modified = line
        for pattern, replacement in _DA_ENDINGS:
            modified = pattern.sub(replacement, modified)
        result.append(modified)
    return result


def fix_code_ratio(article_text: str, target_ratio: float = 0.18) -> str:
    """Reduce code_ratio by removing blank lines and comment-only lines inside
    fenced code blocks. Never removes substantive code (identifier/keyword lines).

    Safe operations only:
      - Drop empty lines inside ``` ... ``` blocks
      - Drop lines whose only non-whitespace content starts with
        '#' (Python/shell) or '//' (JS/TS/Go/Rust/C)

    Iterates up to 3 times; returns early once code_ratio <= target_ratio.
    """
    result_lines = article_text.split("\n")
    for _ in range(3):
        text = "\n".join(result_lines)
        m = compute_article_metrics(text)
        if m.code_ratio <= target_ratio:
            break
        result_lines = _strip_code_noise(result_lines)
    return "\n".join(result_lines)


def _strip_code_noise(lines: list[str]) -> list[str]:
    in_code = False
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            result.append(line)
            continue
        if in_code:
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
        result.append(line)
    return result


def fix_consecutive_length(article_text: str, max_consecutive: int = 4) -> str:
    """Break up consecutive same-length sentence runs by merging pairs."""
    result_lines = article_text.split("\n")
    for _ in range(3):
        text = "\n".join(result_lines)
        m = compute_article_metrics(text)
        if m.max_consecutive_same_length <= max_consecutive:
            break
        result_lines = _merge_adjacent_lines(result_lines)
    return "\n".join(result_lines)


def _representative_sentence_length(line_str: str) -> int:
    """Return the length of the first sentence in a line (for run-length comparison)."""
    parts = re.split(r"(?<=[。！？\!\?])", line_str.strip())
    sentences = [p.strip() for p in parts if p.strip()]
    if not sentences:
        return len(line_str.strip())
    return len(sentences[0])


def _merge_adjacent_lines(lines: list[str]) -> list[str]:
    in_code = False
    content_indices: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or stripped.startswith("#") or not stripped or stripped.startswith(">"):
            continue
        content_indices.append(i)
    if len(content_indices) < 5:
        return lines
    lengths = [(idx, _representative_sentence_length(lines[idx])) for idx in content_indices]
    result = list(lines)
    merged: set[int] = set()
    run_start = 0
    for j in range(1, len(lengths) + 1):
        extends = (
            j < len(lengths)
            and abs(lengths[j][1] - lengths[j - 1][1]) <= 10
        )
        if not extends:
            run_len = j - run_start
            if run_len >= 5:
                k = run_start + 1
                while k < j:
                    prev_idx = lengths[k - 1][0]
                    curr_idx = lengths[k][0]
                    if prev_idx not in merged and curr_idx not in merged:
                        prev = result[prev_idx].rstrip()
                        if prev.endswith("。"):
                            prev = prev[:-1] + "、"
                        result[prev_idx] = prev + result[curr_idx].strip()
                        result[curr_idx] = ""
                        merged.add(curr_idx)
                    k += 2
            run_start = j
    return [line for i, line in enumerate(result) if i not in merged]
