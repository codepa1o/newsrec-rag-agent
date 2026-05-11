from __future__ import annotations

from pathlib import Path

from app.models import Article, Behavior, Impression


def parse_news_line(line: str) -> Article | None:
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 5 or not parts[0].strip():
        return None

    padded = parts + [""] * (8 - len(parts))
    news_id, category, subcategory, title, abstract, url, title_entities, abstract_entities = padded[:8]
    return Article(
        news_id=news_id.strip(),
        category=category.strip() or "unknown",
        subcategory=subcategory.strip() or "unknown",
        title=title.strip(),
        abstract=abstract.strip(),
        url=url.strip(),
        title_entities=title_entities.strip(),
        abstract_entities=abstract_entities.strip(),
    )


def parse_behavior_line(line: str) -> Behavior | None:
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 5:
        return None

    impression_id, user_id, time, history_raw, impressions_raw = parts[:5]
    history = tuple(item for item in history_raw.split() if item)
    impressions: list[Impression] = []
    for item in impressions_raw.split():
        if "-" not in item:
            continue
        news_id, clicked = item.rsplit("-", 1)
        impressions.append(Impression(news_id=news_id, clicked=clicked == "1"))

    return Behavior(
        impression_id=impression_id,
        user_id=user_id,
        time=time,
        history=history,
        impressions=tuple(impressions),
    )


def load_news(path: str | Path) -> dict[str, Article]:
    articles: dict[str, Article] = {}
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            article = parse_news_line(line)
            if article:
                articles[article.news_id] = article
    return articles


def load_behaviors(path: str | Path) -> list[Behavior]:
    behaviors: list[Behavior] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            behavior = parse_behavior_line(line)
            if behavior:
                behaviors.append(behavior)
    return behaviors
