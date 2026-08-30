import concurrent.futures, html, json, re, urllib.request
from pathlib import Path
TOKEN=re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
def fetch(article):
    request=urllib.request.Request(article['source_url'],headers={'User-Agent':'Mozilla/5.0 CET corpus verifier'})
    with urllib.request.urlopen(request,timeout=20) as response: raw=response.read(4_000_000).decode('utf-8',errors='ignore')
    raw=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',raw);text=html.unescape(re.sub(r'(?s)<[^>]+>',' ',raw))
    source=TOKEN.findall(text.lower());passage=TOKEN.findall(article['content'].lower());runs=set(zip(*(source[i:] for i in range(8))))
    return article['corpus_id'],sorted({' '.join(run) for run in zip(*(passage[i:] for i in range(8))) if run in runs})
root=Path(__file__).resolve().parents[1];items=json.loads((root/'seed/review_batches/technology_l4_l6_manual.json').read_text(encoding='utf-8'))
results={};failures={}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    futures={pool.submit(fetch,a):a for a in items}
    for future in concurrent.futures.as_completed(futures):
        article=futures[future]
        try:key,value=future.result();results[key]=value
        except Exception as exc:failures[article['corpus_id']]=f'{type(exc).__name__}: {exc}'
print(json.dumps({'fetched':len(results),'failed':failures,'articles_with_8_word_overlap':{k:v for k,v in results.items() if v},'total_overlap_runs':sum(map(len,results.values()))},ensure_ascii=False,indent=2))
