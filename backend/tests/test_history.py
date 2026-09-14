import json
import sqlite3
from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import Store
from app.parser import read_export
from test_import import archive, SAMPLE


def test_history_pages_filters_scope_and_restart(tmp_path):
    path=tmp_path/'history.sqlite3'
    store=Store(path)
    first=store.import_chat(read_export(archive()),'Same name','Self','Friend','Europe/Berlin',phone='+12025550123')
    other=store.import_chat(read_export(archive('[3/18/26, 9:00:00 AM] Self: private-other\n[3/18/26, 9:01:00 AM] Friend: yes')),
                            'Same name','Self','Friend','UTC')
    store.import_chat(read_export(archive()),'Same name','Self','Friend','Europe/Berlin',first['conversation_id'])
    route='/conversations/'+first['conversation_id']
    for _ in range(2):
        with TestClient(create_app(path)) as client:
            summaries=client.get('/conversations').json()
            assert len(summaries)==2 and len({c['id'] for c in summaries})==2
            summary=next(c for c in summaries if c['id']==first['conversation_id'])
            assert summary['message_count']==9 and summary['rag_count']==5
            assert summary['chunk_count']==summary['embedding_count']==2
            assert summary['normalized_phone']=='+12025550123'
            detail=client.get(route).json()
            assert detail['participants']==[{'alias':'Friend','role':'contact'},{'alias':'Self','role':'self'}]
            assert detail['type_counts']['voice']==1
            assert detail['imports'][0]['added_count']==0 and detail['imports'][0]['skipped_count']==9
            assert detail['imports'][0]['parsed_count']==9 and detail['imports'][0]['warnings']
            assert detail['imports'][0]['created_at'].endswith('Z')
            assert detail['embedding_providers'][0]['dimensions']==128
            pages=[]; offset=0
            while offset is not None:
                page=client.get(route+'/messages',params={'limit':2,'offset':offset}).json()
                pages+=page['items'];offset=page['next_offset']
            assert len(pages)==len({m['id'] for m in pages})==9
            assert pages[0]['role'] is None and pages[0]['type']=='system'
            assert pages[1]['original_text']=='Coffee at the garden café? 👩🏽‍💻 ❤️\nBring a book too.'
            reverse=client.get(route+'/messages?order=desc').json()['items']
            assert [m['id'] for m in reverse]==[m['id'] for m in reversed(pages)]
            assert client.get(route+'/messages?rag=true').json()['total']==5
            assert client.get(route+'/messages?type=voice').json()['items'][0]['include_in_rag'] is False
            assert client.get(route+'/messages',params={'q':'👩🏽‍💻'}).json()['total']==1
            assert client.get(route+'/messages',params={'q':"%' OR 1=1 --"}).json()['total']==0
            assert client.get(route+'/messages?q=private-other').json()['total']==0
            assert client.get(route+'/messages?offset=999').json()['next_offset'] is None
            payload=json.dumps([detail,pages])
            assert 'vector' not in payload and 'fingerprint' not in payload and 'archive_hash' not in payload
            assert other['conversation_id'] not in payload
            for suffix in ['', '/messages']:
                assert client.get('/conversations/missing'+suffix).status_code==404
            for params in [{'limit':201},{'offset':-1},{'order':'invalid'},{'type':'bad'},{'rag':'bad'},{'q':'x'*201}]:
                assert client.get(route+'/messages',params=params).status_code==422


def test_legacy_schema_upgrade_and_empty_history(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    store=Store(path)
    with TestClient(create_app(path)) as client:assert client.get('/conversations').json()==[]
    saved=store.import_chat(read_export(archive()),'Legacy','Self','Friend','UTC')
    with sqlite3.connect(path) as db:
        db.execute('DROP TABLE import_details')
        db.execute('DELETE FROM schema_version WHERE version=2')
    with TestClient(create_app(path)) as client:
        detail=client.get('/conversations/'+saved['conversation_id']).json()
        assert detail['message_count']==9
        assert detail['imports'][0]['parsed_count'] is None
        assert detail['imports'][0]['skipped_count'] is None
        assert detail['imports'][0]['warnings'] is None


def test_large_page_is_bounded_and_indexed(tmp_path):
    store=Store(tmp_path/'large.sqlite3')
    text='\n'.join(f'[3/15/26, 9:00:00 AM] {"Self" if n%2 else "Friend"}: Message {n}' for n in range(240))
    saved=store.import_chat(read_export(archive(text)),'Large','Self','Friend','UTC')
    with TestClient(create_app(store.path)) as client:
        page=client.get('/conversations/'+saved['conversation_id']+'/messages?limit=50').json()
        assert len(page['items'])==50 and page['total']==240 and page['next_offset']==50
    with store.connection() as db:
        plan=' '.join(str(tuple(r)) for r in db.execute('EXPLAIN QUERY PLAN SELECT id FROM messages WHERE conversation_id=? ORDER BY utc_datetime,source_order,id LIMIT 50',(saved['conversation_id'],)))
        assert 'messages_page' in plan and 'TEMP B-TREE' not in plan
