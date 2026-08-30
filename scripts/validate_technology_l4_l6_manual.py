import itertools, json, re
from pathlib import Path

TOKEN=re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
BOUNDS={4:(270,330),5:(300,370),6:(330,420)}
EXPECTED={4:(1,2),5:(2,2),6:(2,3)}
def grams(text,n=5):
    words=TOKEN.findall(text.lower());return set(zip(*(words[i:] for i in range(n))))
def maximum(items,field):
    best=(-1,None,None)
    for a,b in itertools.combinations(items,2):
        x,y=grams(field(a)),grams(field(b));score=len(x&y)/max(1,len(x|y))
        if score>best[0]:best=(score,a,b)
    return best

root=Path(__file__).resolve().parents[1]
items=json.loads((root/'seed/review_batches/technology_l4_l6_manual.json').read_text(encoding='utf-8'))
assert len(items)==15
assert {a['difficulty'] for a in items}=={4,5,6}
for level in BOUNDS: assert sum(a['difficulty']==level for a in items)==5
ids=set();urls=set();titles=set();source_ids=set();stems=set();questions=[]
for a in items:
    count=len(TOKEN.findall(a['content'])); assert BOUNDS[a['difficulty']][0]<=count<=BOUNDS[a['difficulty']][1],(a['corpus_id'],count)
    assert a['corpus_id'] not in ids and a['source_url'] not in urls and a['source_title'].casefold() not in titles and a['source_id'] not in source_ids
    ids.add(a['corpus_id']);urls.add(a['source_url']);titles.add(a['source_title'].casefold());source_ids.add(a['source_id'])
    assert len(a['questions'])==5 and len({q['type'] for q in a['questions']})>=4
    inf=sum(q['type']=='inference' for q in a['questions']);lo,hi=EXPECTED[a['difficulty']];assert lo<=inf<=hi
    for q in a['questions']:
        stem=re.sub(r'[^a-z0-9]+',' ',q['question'].casefold()).strip();assert stem and stem not in stems;stems.add(stem)
        assert len(q['options'])==4 and len(set(q['options']))==4 and q['answer'] in 'ABCD'
        assert re.search(r'[\u4e00-\u9fff]',q['explanation']) and a['content'].count(q['evidence_text'])==1
        questions.append(dict(q,article_id=a['corpus_id']))
content=maximum(items,lambda x:x['content']);stem=maximum(questions,lambda x:x['question'])
print(json.dumps({'articles':len(items),'questions':len(questions),'word_ranges':{str(level):[min(len(TOKEN.findall(a['content'])) for a in items if a['difficulty']==level),max(len(TOKEN.findall(a['content'])) for a in items if a['difficulty']==level)] for level in BOUNDS},'unique_urls':len(urls),'unique_source_titles':len(titles),'unique_source_ids':len(source_ids),'unique_corpus_ids':len(ids),'exact_unique_evidence':sum(a['content'].count(q['evidence_text'])==1 for a in items for q in a['questions']),'max_content_5gram_jaccard':[content[0],content[1]['corpus_id'],content[2]['corpus_id']],'max_stem_5gram_jaccard':[stem[0],stem[1]['article_id'],stem[1]['question'],stem[2]['article_id'],stem[2]['question']]},ensure_ascii=False,indent=2))
