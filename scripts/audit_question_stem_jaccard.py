import itertools, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOKEN=re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
def grams(text,n=5):
    words=TOKEN.findall(text.casefold());return set(zip(*(words[i:] for i in range(n))))
items=[]
for path in (ROOT/'seed/reading_corpus').glob('*.json'):
    if path.name=='APPROVED.json':continue
    for article in json.loads(path.read_text(encoding='utf-8')):
        for index,q in enumerate(article['questions']):items.append({'topic':article['topic'],'article_id':article['corpus_id'],'title':article['title'],'index':index,'type':q['type'],'question':q['question'],'evidence':q['evidence_text'],'grams':grams(q['question'])})
pairs=[]
for a,b in itertools.combinations(items,2):
    score=len(a['grams']&b['grams'])/max(1,len(a['grams']|b['grams']))
    if score>0.12:pairs.append((score,a,b))
maximum=max(pairs,key=lambda x:x[0]) if pairs else (0,None,None)
targets={}
for score,a,b in pairs:
    for item in (a,b):
        if item['topic'] in {'文化','社会'}:
            key=(item['article_id'],item['index']);clean={k:v for k,v in item.items() if k!='grams'};targets.setdefault(key,dict(clean,collisions=0,max_score=0));targets[key]['collisions']+=1;targets[key]['max_score']=max(targets[key]['max_score'],score)
print(json.dumps({'questions':len(items),'pairs_over_threshold':len(pairs),'maximum':maximum[0],'maximum_pair':None if not pairs else [maximum[1]['article_id'],maximum[1]['question'],maximum[2]['article_id'],maximum[2]['question']],'culture_social_targets':sorted(targets.values(),key=lambda x:(-x['max_score'],-x['collisions'],x['article_id'],x['index']))},ensure_ascii=False,indent=2,default=list))
