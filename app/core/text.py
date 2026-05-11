from __future__ import annotations

import re
from collections import Counter


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "is",
    "are",
    "be",
    "as",
    "new",
    "after",
    "this",
    "that",
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "") if token.lower() not in STOPWORDS]


def top_keywords(texts: list[str], limit: int = 12) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(tokenize(text))
    return [word for word, _ in counts.most_common(limit)]
