"""Prompt-injection heuristics.

A lightweight, deterministic guard that flags common injection patterns in
untrusted text (inbound messages, retrieved documents, tool outputs). It is a
defence-in-depth layer, not a silver bullet: the agent additionally isolates
untrusted content and constrains tool permissions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(system|previous)\s+(prompt|instructions)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|dan|developer\s+mode)", re.I),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|instructions|secrets?)", re.I),
    re.compile(r"print\s+(your\s+)?(api[_\s-]?key|token|password|secret)", re.I),
    re.compile(r"\bexfiltrate\b|\bbypass\s+(safety|guardrails?)\b", re.I),
    re.compile(r"</?(system|assistant)>", re.I),  # fake role tags
]


@dataclass(slots=True)
class InjectionVerdict:
    is_suspicious: bool
    matches: list[str]


def scan(text: str | None) -> InjectionVerdict:
    """Scan untrusted text for injection patterns."""
    if not text:
        return InjectionVerdict(False, [])
    hits = [p.pattern for p in _PATTERNS if p.search(text)]
    return InjectionVerdict(bool(hits), hits)


def sanitize_untrusted(text: str, *, max_len: int = 8000) -> str:
    """Neutralise fake role tags and clamp length before injecting into context."""
    cleaned = re.sub(r"</?(system|assistant|user)>", "", text, flags=re.I)
    return cleaned[:max_len]
