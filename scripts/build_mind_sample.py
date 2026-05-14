from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact MIND sample for local recommendation demos.")
    parser.add_argument("--source", required=True, help="MIND split directory, e.g. E:\\...\\MINDlarge_train")
    parser.add_argument("--output", default="data/sample", help="Output directory for news.tsv and behaviors.tsv")
    parser.add_argument("--max-behaviors", type=int, default=1200)
    parser.add_argument("--max-extra-news", type=int, default=800)
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    news_path = source / "news.tsv"
    behaviors_path = source / "behaviors.tsv"
    if not news_path.exists() or not behaviors_path.exists():
        raise FileNotFoundError(f"Missing news.tsv or behaviors.tsv under {source}")

    output.mkdir(parents=True, exist_ok=True)
    selected_behaviors, selected_news_ids = select_behaviors(behaviors_path, args.max_behaviors)
    news_lines = select_news(news_path, selected_news_ids, args.max_extra_news)

    (output / "behaviors.tsv").write_text("".join(selected_behaviors), encoding="utf-8")
    (output / "news.tsv").write_text("".join(news_lines), encoding="utf-8")

    print(f"Wrote {len(news_lines)} news rows to {output / 'news.tsv'}")
    print(f"Wrote {len(selected_behaviors)} behavior rows to {output / 'behaviors.tsv'}")


def select_behaviors(path: Path, max_behaviors: int) -> tuple[list[str], set[str]]:
    behaviors: list[str] = []
    news_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file):
            if index >= max_behaviors:
                break
            rewritten = rewrite_demo_user(line, index)
            behaviors.append(rewritten)
            parts = rewritten.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            news_ids.update(item for item in parts[3].split() if item)
            for impression in parts[4].split():
                if "-" in impression:
                    news_ids.add(impression.rsplit("-", 1)[0])
    return behaviors, news_ids


def rewrite_demo_user(line: str, index: int) -> str:
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 5:
        return line
    if index == 0:
        parts[0] = "demo-1"
        parts[1] = "U100"
    elif index == 1:
        parts[0] = "demo-2"
        parts[1] = "U200"
    return "\t".join(parts) + "\n"


def select_news(path: Path, selected_ids: set[str], max_extra_news: int) -> list[str]:
    selected_lines: list[str] = []
    extra_lines: list[str] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            news_id = line.split("\t", 1)[0]
            if news_id in selected_ids:
                selected_lines.append(line)
            elif len(extra_lines) < max_extra_news:
                extra_lines.append(line)
    return selected_lines + extra_lines


if __name__ == "__main__":
    main()
