from __future__ import annotations

import argparse
import json

from app.config import get_settings
from app.dependencies import ServiceContainer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline recommendation metrics.")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()

    container = ServiceContainer(get_settings())
    result = container.evaluator.evaluate(k=args.k)
    print(json.dumps({"k": args.k, **result.to_dict()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
