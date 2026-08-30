import os, tempfile, database
tmp = tempfile.mkdtemp()
database.DB_PATH = os.path.join(tmp, 'test.db')
from app import create_app
app = create_app(); app.testing = True
c = app.test_client()
r = c.post('/api/notes/categories', json={'parent_id':0,'name':'单词'}); print('cat', r.status_code, r.get_json())
cat = r.get_json()['id']
print('subcat', c.post('/api/notes/categories', json={'parent_id':cat,'name':'四级核心词'}).status_code)
rn = c.post('/api/notes/notes', json={'category_id':cat,'title':'记忆法','content':'用例句记','note_date':'2026-08-22','color':'red'}); print('note', rn.status_code, rn.get_json())
nid = rn.get_json()['id']
print('list cat', [x['title'] for x in c.get(f'/api/notes/notes?category_id={cat}').get_json()['notes']])
print('detail', c.get(f'/api/notes/notes/{nid}').get_json()['title'], c.get(f'/api/notes/notes/{nid}').get_json()['color'])
print('update', c.put(f'/api/notes/notes/{nid}', json={'content':'更新','color':'blue'}).get_json())
print('delete', c.delete(f'/api/notes/notes/{nid}').get_json())
print('cats', c.get('/api/notes/categories').get_json()['categories'][0]['name'])
