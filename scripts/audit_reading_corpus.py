"""Report every deterministic gate for the reviewed 180-article corpus."""

from __future__ import annotations

from collections import Counter
import itertools
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seed.reading_catalog import TOPICS  # noqa: E402
from seed.reading_corpus_loader import (  # noqa: E402
    CORPUS_DIR,
    _word_count,
    validate_reading_corpus,
)


def _grams(text, size=5):
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.casefold())
    return set(zip(*(words[offset:] for offset in range(size))))


def _similarity_report(items):
    pairs = []
    maximum = (0.0, None, None)
    for (left_id, left), (right_id, right) in itertools.combinations(items, 2):
        score = len(left & right) / max(1, len(left | right))
        if score > maximum[0]:
            maximum = (score, left_id, right_id)
        if score > 0.12:
            pairs.append((score, left_id, right_id))
    return {
        "threshold": 0.12,
        "pairs_over_threshold": len(pairs),
        "maximum": maximum[0],
        "maximum_pair": maximum[1:],
    }


def main():
    articles = []
    missing = []
    for topic in TOPICS:
        path = CORPUS_DIR / f"{topic}.json"
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        articles.extend(json.loads(path.read_text(encoding="utf-8")))

    if missing:
        print(json.dumps({"approved": False, "missing_shards": missing}, ensure_ascii=False, indent=2))
        return 1

    gram_sets = [(item["corpus_id"], _grams(item["content"])) for item in articles]
    question_gram_sets = [
        (f'{item["corpus_id"]}:Q{index}', _grams(question["question"]))
        for item in articles
        for index, question in enumerate(item["questions"], start=1)
    ]

    result = {
        "articles": len(articles),
        "matrix": {
            f"{topic}-L{difficulty}": count
            for (topic, difficulty), count in sorted(
                Counter((item["topic"], int(item["difficulty"])) for item in articles).items()
            )
        },
        "unique_corpus_ids": len({item["corpus_id"] for item in articles}),
        "unique_titles": len({item["title"].casefold() for item in articles}),
        "unique_source_urls": len({item["source_url"] for item in articles}),
        "unique_source_titles": len({item["source_title"].casefold() for item in articles}),
        "word_range": [min(map(_word_count, (item["content"] for item in articles))),
                       max(map(_word_count, (item["content"] for item in articles)))],
        "five_gram": _similarity_report(gram_sets),
        "question_five_gram": _similarity_report(question_gram_sets),
        "source_distribution": dict(Counter(item["source_name"] for item in articles)),
    }
    try:
        validate_reading_corpus(articles, TOPICS)
    except ValueError as error:
        result["approved"] = False
        result["first_error"] = str(error)
    else:
        result["approved"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
