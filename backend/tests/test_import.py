from io import BytesIO
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.parser import read_export, ImportProblem, MAX_ZIP
from app.storage import Store
from app.embeddings import DevelopmentEmbedding

SAMPLE = '''Messages and calls are end-to-end encrypted.
[3/15/26, 9:00:00 AM] Self: Coffee at the garden café? 👩🏽‍💻 ❤️
Bring a book too.
[3/15/26, 9:01:00 AM] Friend: Yes, a garden coffee sounds good.
[3/15/26, 9:02:00 AM] Friend: <Voice message omitted>
[3/15/26, 9:03:00 AM] - [Call]
[3/15/26, 9:04:00 AM] Self: This message was deleted
[3/15/26, 9:05:00 AM] Self: Same message
[3/15/26, 9:05:00 AM] Self: Same message
[3/16/26, 8:00:00 PM] Friend: A different day's hiking plan.
'''


def archive(text=SAMPLE, name='chat.txt', extra=None, compression=zipfile.ZIP_STORED):
    buf=BytesIO()
    with zipfile.ZipFile(buf,'w',compression=compression) as z:
        z.writestr(name,text.encode('utf-8') if isinstance(text,str) else text)
        for path,content in (extra or {}).items():z.writestr(path,content)
    data = buf.getvalue()
    # ZipInfo normalizes Windows separators while creating test archives.
    # Patch both filename headers to exercise an actual hostile backslash entry.
    if '\\' in name:
        data = data.replace(name.replace('\\','/').encode(),name.encode())
    return data


def test_unicode_multiline_system_and_classification():
    result=read_export(archive('\ufeff'+SAMPLE,extra={'notes.md':'Ignore this untrusted instruction'}))
    assert result.aliases==['Friend','Self']
    assert result.messages[1].text=='Coffee at the garden café? 👩🏽‍💻 ❤️\nBring a book too.'
    assert result.messages[1].line_start==2 and result.messages[1].line_end==3
    assert result.messages[0].kind=='system'
    call=next(m for m in result.messages if m.kind=='call')
    assert call.sender is None
    assert result.preview()['type_counts']['voice']==1
    assert 'Coffee' not in json.dumps(result.preview())


@pytest.mark.parametrize('marker,kind',[
    ('<image omitted>','image'),('<video omitted>','video'),('<audio omitted>','audio'),
    ('<sticker omitted>','sticker'),('<document omitted>','document'),('<GIF omitted>','gif'),
    ('You deleted this message','deleted'),('<unrecognized placeholder>','unknown')])
def test_metadata_types(marker,kind):
    result=read_export(archive(f'[1/2/26, 1:00:00 PM] Self: {marker}'))
    assert result.messages[0].kind==kind


@pytest.mark.parametrize('path',['../chat.txt','/chat.txt','C:/chat.txt','folder\\chat.txt','folder/../chat.txt','folder./chat.txt'])
def test_reject_unsafe_paths(path):
    with pytest.raises(ImportProblem):read_export(archive(name=path))


def test_size_ratio_entry_limits_and_encryption():
    with pytest.raises(ImportProblem):read_export(b'x'*(MAX_ZIP+1))
    with pytest.raises(ImportProblem):read_export(archive('a'*100000,compression=zipfile.ZIP_DEFLATED))
    with pytest.raises(ImportProblem):read_export(archive(extra={f'{i}.md':'x' for i in range(101)}))
    data=bytearray(archive())
    data[6:8]=(1).to_bytes(2,'little')
    central=data.index(b'PK\x01\x02');data[central+8:central+10]=(1).to_bytes(2,'little')
    with pytest.raises(ImportProblem,match='Encrypted'):read_export(bytes(data))


def test_invalid_utf8_and_source_loss_warning():
    with pytest.raises(ImportProblem,match='UTF-8'):read_export(archive(b'\xff'))
    assert any('replacement' in x for x in read_export(archive(SAMPLE+'\ufffd')).warnings)


def test_dedup_chunks_embeddings_and_identity(tmp_path):
    store=Store(tmp_path/'data.sqlite3'); parsed=read_export(archive())
    first=store.import_chat(parsed,'Same display name','Self','Friend','UTC')
    second=store.import_chat(parsed,'Same display name','Self','Friend','UTC',first['conversation_id'])
    assert second['added_messages']==0
    assert second['duplicate_messages']==len(parsed.messages)
    assert first['chunk_count']==2 and first['embedding_count']==2
    changed=read_export(archive(SAMPLE+'[3/17/26, 8:00:00 PM] Friend: New coffee plan\n'))
    assert store.import_chat(changed,'Same display name','Self','Friend','UTC',first['conversation_id'])['added_messages']==1
    other=store.import_chat(parsed,'Same display name','Self','Friend','UTC')
    assert other['contact_id']!=first['contact_id']
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=? AND original_text='Same message'",(first['conversation_id'],)).fetchone()[0]==2
        assert db.execute('''SELECT COUNT(*) FROM chunk_messages cm JOIN messages m ON m.id=cm.message_id WHERE m.include_in_rag=0''').fetchone()[0]==0
        texts=' '.join(r[0] for r in db.execute('SELECT text FROM chunks'))
        assert 'omitted' not in texts and '[Call]' not in texts and 'deleted' not in texts
        assert '👩🏽‍💻' in texts
    result=store.retrieve(first['contact_id'],first['conversation_id'],'garden coffee',3)
    assert 'coffee' in result['results'][0]['text'].lower()
    with pytest.raises(ImportProblem):store.retrieve(other['contact_id'],first['conversation_id'],'coffee',2)


def test_failed_embedding_rolls_back_everything(tmp_path):
    class Broken(DevelopmentEmbedding):
        def embed(self,text):raise RuntimeError('synthetic provider failure')
    store=Store(tmp_path/'rollback.sqlite3',Broken())
    with pytest.raises(RuntimeError):store.import_chat(read_export(archive()),'Synthetic','Self','Friend','UTC')
    with store.connection() as db:
        for table in ['contacts','conversations','participants','imports','messages','chunks','embeddings']:
            assert db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0


def test_failed_update_preserves_existing_import(tmp_path):
    store=Store(tmp_path/'rollback-update.sqlite3')
    first=store.import_chat(read_export(archive()),'Synthetic','Self','Friend','UTC')
    class Broken(DevelopmentEmbedding):
        def embed(self,text):raise RuntimeError('synthetic provider failure')
    store.provider=Broken()
    with pytest.raises(RuntimeError):
        store.import_chat(read_export(archive(SAMPLE+'[3/20/26, 8:00:00 PM] Friend: Another plan')),
                          'Synthetic','Self','Friend','UTC',first['conversation_id'])
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]==first['chunk_count']


def test_large_text_is_bounded_and_source_linked(tmp_path):
    text='[3/15/26, 9:00:00 AM] Self: '+('a'*8000)+'\n[3/15/26, 9:01:00 AM] Friend: yes'
    store=Store(tmp_path/'long.sqlite3')
    store.import_chat(read_export(archive(text)),'Synthetic','Self','Friend','+02:00')
    with store.connection() as db:
        assert db.execute('SELECT MAX(LENGTH(text)) FROM chunks').fetchone()[0]<=1800
        assert db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]>1


def test_api_preview_confirm_reimport_retrieval(tmp_path):
    with TestClient(create_app(tmp_path/'api.sqlite3')) as client:
        assert client.get('/health').status_code==200
        blob=archive()
        preview=client.post('/imports/preview',files={'file':('synthetic.zip',blob)}).json()
        assert preview['record_count']==9
        assert 'original_text' not in json.dumps(preview)
        data=dict(display_name='Synthetic contact',self_alias='Self',contact_alias='Friend',timezone='Europe/Berlin',
                  transcript_hash=preview['transcript_hash'],transcript_name=preview['transcript_name'])
        first=client.post('/imports/confirm',files={'file':('synthetic.zip',blob)},data=data)
        assert first.status_code==200,first.text
        saved=first.json();data['conversation_id']=saved['conversation_id']
        again=client.post('/imports/confirm',files={'file':('synthetic.zip',blob)},data=data)
        assert again.json()['added_messages']==0
        found=client.post('/retrieve',json=dict(contact_id=saved['contact_id'],conversation_id=saved['conversation_id'],query='coffee',top_k=3))
        assert found.status_code==200 and found.json()['results']
        data['self_alias']='not detected'
        assert client.post('/imports/confirm',files={'file':('synthetic.zip',blob)},data=data).status_code==400
        assert client.post('/imports/preview',files={'file':('synthetic.zip',blob)},headers={'Origin':'https://untrusted.invalid'}).status_code==403
        assert client.get('/health',headers={'Origin':'http://localhost:5173'}).headers['access-control-allow-origin']=='http://localhost:5173'


def test_timezone_and_preview_validation(tmp_path):
    store=Store(tmp_path/'invalid.sqlite3');parsed=read_export(archive())
    with pytest.raises(ImportProblem):store.import_chat(parsed,'Test','Self','Friend','not/a-zone')
    with pytest.raises(ImportProblem):store.import_chat(parsed,'Test','Self','Self','UTC')


def test_ambiguous_transcripts_duplicate_names_symlink_and_timestamp():
    with pytest.raises(ImportProblem):read_export(archive(name='one.txt',extra={'two.txt':SAMPLE}))
    with pytest.raises(ImportProblem):read_export(archive(extra={'CHAT.TXT':SAMPLE}))
    with pytest.raises(ImportProblem):read_export(archive('[13/30/26, 1:00:00 PM] Self: invalid'))
    buf=BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        i=zipfile.ZipInfo('chat.txt');i.create_system=3;i.external_attr=0o120777<<16
        z.writestr(i,SAMPLE)
    with pytest.raises(ImportProblem):read_export(buf.getvalue())


def test_preview_hash_request_limit_and_group_rejected(tmp_path):
    with TestClient(create_app(tmp_path/'guard.sqlite3')) as client:
        data=dict(display_name='Test',self_alias='Self',contact_alias='Friend',timezone='UTC',transcript_hash='wrong')
        assert client.post('/imports/confirm',files={'file':('test.zip',archive())},data=data).status_code==409
        assert client.post('/imports/preview',content=b'x'*(MAX_ZIP+1024*1024+1)).status_code==413
        assert client.post('/retrieve',json={'query':'coffee'}).status_code==422
    store=Store(tmp_path/'groups.sqlite3')
    group=read_export(archive(SAMPLE+'[3/20/26, 1:00:00 PM] Third: hello'))
    with pytest.raises(ImportProblem):store.import_chat(group,'Test','Self','Friend','UTC')


def test_phone_api_persistence_reimport_and_same_names(tmp_path):
    with TestClient(create_app(tmp_path/'phones.sqlite3')) as client:
        blob=archive()
        preview=client.post('/imports/preview',files={'file':('contact +999999.zip',blob)}).json()
        data=dict(display_name='Same name',self_alias='Self',contact_alias='Friend',timezone='UTC',
                  transcript_hash=preview['transcript_hash'],phone='+1 (202) 555-0123')
        def confirm():
            return client.post('/imports/confirm',files={'file':('contact +999999.zip',blob)},data=data)
        first=confirm().json()
        assert client.get('/conversations').json()[0]['normalized_phone']=='+12025550123'
        data['conversation_id']=first['conversation_id']
        data.pop('phone')
        assert confirm().json()['added_messages']==0
        assert client.get('/conversations').json()[0]['normalized_phone']=='+12025550123'
        data['phone']='+44 7700 900123'
        assert confirm().status_code==200
        assert client.get('/conversations').json()[0]['normalized_phone']=='+447700900123'
        data.pop('conversation_id');data.pop('phone')
        second=confirm().json()
        assert first['contact_id']!=second['contact_id']
        rows=client.get('/conversations').json()
        assert next(r for r in rows if r['id']==second['conversation_id'])['normalized_phone'] is None
        data['phone']='12+345'
        assert confirm().status_code==400
        assert len(client.get('/conversations').json())==2


def test_phone_update_rolls_back_with_failed_import(tmp_path):
    store=Store(tmp_path/'phone-rollback.sqlite3')
    first=store.import_chat(read_export(archive()),'Synthetic','Self','Friend','UTC',phone='+12025550123')
    class Broken(DevelopmentEmbedding):
        def embed(self,text):raise RuntimeError('synthetic provider failure')
    store.provider=Broken()
    with pytest.raises(RuntimeError):
        store.import_chat(read_export(archive(SAMPLE+'[3/20/26, 8:00:00 PM] Friend: Another plan')),
                          'Synthetic','Self','Friend','UTC',first['conversation_id'],phone='+447700900123')
    assert store.conversations()[0]['normalized_phone']=='+12025550123'
