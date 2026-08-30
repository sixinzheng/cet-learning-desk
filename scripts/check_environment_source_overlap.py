import concurrent.futures
import html
import json
import re
import urllib.request
from pathlib import Path


TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def fetch(article):
    request = urllib.request.Request(article["source_url"], headers={"User-Agent": "Mozilla/5.0 CET corpus verifier"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(4_000_000).decode("utf-8", errors="ignore")
    raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    source_words = TOKEN.findall(text.lower())
    passage_words = TOKEN.findall(article["content"].lower())
    source_runs = set(zip(*(source_words[offset:] for offset in range(8))))
    overlaps = sorted({" ".join(run) for run in zip(*(passage_words[offset:] for offset in range(8))) if run in source_runs})
    return article["corpus_id"], overlaps


root = Path(__file__).resolve().parents[1]
path = next(path for path in (root / "seed" / "reading_corpus").glob("*.json") if "environment" in json.loads(path.read_text(encoding="utf-8"))[0]["corpus_id"])
articles = json.loads(path.read_text(encoding="utf-8"))
results, failures = {}, {}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    futures = {pool.submit(fetch, article): article for article in articles}
    for future in concurrent.futures.as_completed(futures):
        article = futures[future]
        try:
            corpus_id, overlaps = future.result()
            results[corpus_id] = overlaps
        except Exception as exc:
            failures[article["corpus_id"]] = f"{type(exc).__name__}: {exc}"
print(json.dumps({
    "fetched": len(results),
    "failed": failures,
    "articles_with_8_word_overlap": {key: value for key, value in results.items() if value},
    "total_overlap_runs": sum(len(value) for value in results.values()),
}, ensure_ascii=False, indent=2))
