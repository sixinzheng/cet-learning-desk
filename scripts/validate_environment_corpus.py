import itertools
import json
import re
from pathlib import Path


def grams(text, size=5):
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())
    return set(zip(*(words[offset:] for offset in range(size))))


def max_pair(items, field):
    best = (-1.0, None, None)
    for left, right in itertools.combinations(items, 2):
        a, b = grams(field(left)), grams(field(right))
        score = len(a & b) / max(1, len(a | b))
        if score > best[0]:
            best = (score, left, right)
    return best


root = Path(__file__).resolve().parents[1]
shards = [json.loads(path.read_text(encoding="utf-8")) for path in (root / "seed" / "reading_corpus").glob("*.json") if path.name != "APPROVED.json"]
environment = next(shard for shard in shards if shard and "environment" in shard[0]["corpus_id"])
all_articles = sum(shards, [])
questions = [dict(question, article_id=article["corpus_id"]) for article in environment for question in article["questions"]]
word_ranges = {}
inferences = {}
for level in range(1, 7):
    cell = [article for article in environment if article["difficulty"] == level]
    counts = [len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", article["content"])) for article in cell]
    word_ranges[str(level)] = [min(counts), max(counts)]
    inferences[str(level)] = [sum(q["type"] == "inference" for q in article["questions"]) for article in cell]

content_best = max_pair(environment, lambda article: article["content"])
stem_best = max_pair(questions, lambda question: question["question"])
all_best = max_pair(all_articles, lambda article: article["content"])
environment_ids = {article["corpus_id"] for article in environment}
cross_pairs = []
for left, right in itertools.combinations(all_articles, 2):
    if left["corpus_id"] not in environment_ids and right["corpus_id"] not in environment_ids:
        continue
    a, b = grams(left["content"]), grams(right["content"])
    cross_pairs.append((len(a & b) / max(1, len(a | b)), left, right))
environment_cross_best = max(cross_pairs, key=lambda item: item[0])
print(json.dumps({
    "articles": len(environment),
    "questions": len(questions),
    "word_ranges": word_ranges,
    "inference_counts": inferences,
    "minimum_question_types": min(len({q["type"] for q in article["questions"]}) for article in environment),
    "unique_urls": len({article["source_url"] for article in environment}),
    "unique_source_titles": len({article["source_title"].casefold() for article in environment}),
    "unique_source_ids": len({article["source_id"] for article in environment}),
    "unique_corpus_ids": len({article["corpus_id"] for article in environment}),
    "evidence_exact_unique": sum(article["content"].count(q["evidence_text"]) == 1 for article in environment for q in article["questions"]),
    "max_content_jaccard_environment": [content_best[0], content_best[1]["corpus_id"], content_best[2]["corpus_id"]],
    "max_stem_jaccard_environment": [stem_best[0], stem_best[1]["article_id"], stem_best[1]["question"], stem_best[2]["article_id"], stem_best[2]["question"]],
    "max_content_jaccard_available_shards": [all_best[0], all_best[1]["corpus_id"], all_best[2]["corpus_id"]],
    "max_content_jaccard_involving_environment": [environment_cross_best[0], environment_cross_best[1]["corpus_id"], environment_cross_best[2]["corpus_id"]],
}, ensure_ascii=False, indent=2))
