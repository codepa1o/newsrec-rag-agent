from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.mind import load_behaviors, load_news
from app.services.embedding import HashingEmbeddingProvider
from app.services.vector_store import LocalVectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and preview MIND dataset ingestion.")
    parser.add_argument("--news", required=True, help="Path to MIND news.tsv")
    parser.add_argument("--behaviors", required=True, help="Path to MIND behaviors.tsv")
    parser.add_argument("--preview-out", default="", help="Optional JSON preview output path")
    args = parser.parse_args()

    articles = load_news(args.news)
    behaviors = load_behaviors(args.behaviors)
    vector_store = LocalVectorStore(HashingEmbeddingProvider())
    vector_store.upsert(articles)

    preview = {
        "articles": len(articles),
        "behaviors": len(behaviors),
        "sample_article_ids": list(articles.keys())[:5],
        "sample_user_ids": sorted({behavior.user_id for behavior in behaviors})[:5],
    }
    print(json.dumps(preview, ensure_ascii=False, indent=2))

    if args.preview_out:
        output = Path(args.preview_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
