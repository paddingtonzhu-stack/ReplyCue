import base64
import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import Store
from app.parser import read_export
from app.encoded import encoded_kind, MIN_ENCODED, MAX_ENCODED
from app.embeddings import DevelopmentEmbedding
from test_import import archive


def payload(magic=b'\xff\xd8\xff\xe0'):
    return base64.b64encode(magic+bytes(range(256))*2).decode()


@pytest.mark.parametrize('magic,kind',[
    (b'\xff\xd8\xff\xe0','encoded_image'),(b'\x89PNG\r\n\x1a\n','encoded_image'),
    (b'GIF87a','encoded_image'),(b'GIF89a','encoded_image'),(b'RIFF1234WEBP','encoded_image'),
    (b'RIFF1234WAVE','encoded_audio'),(b'fLaC','encoded_audio'),(b'ID3','encoded_audio'),
    (b'RIFF1234AVI ','encoded_video'),(b'\x00\x00\x00\x18ftypisom','encoded_video'),
    (b'%PDF-1.7','encoded_document'),(b'PK\x03\x04','encoded_binary')])
def test_strict_known_magic(magic,kind):
    value=payload(magic)
    assert encoded_kind(value)==kind
    assert encoded_kind('\n'.join(value[i:i+60] for i in range(0,len(value),60)))==kind
    assert encoded_kind('data:application/octet-stream;base64,'+value)==kind
    assert encoded_kind(value+'!') is None


def test_whatsapp_annotation_after_encoded_media():
    value=payload()
    assert encoded_kind(value+': Live location: 42.4673, -2.4448 - https://maps.google.com/?q=42.4673,-2.4448')=='encoded_image'
    assert encoded_kind(value+': ordinary prose')=='encoded_image'
    assert encoded_kind(value+' ordinary prose') is None


@pytest.mark.parametrize('value',[
    'A'*1000,'Normal long text with words. '*100, 'a'*64, '/9j/4AAQ',
    'https://example.invalid/'+payload(), 'const image = "'+payload()+'";',
    base64.b64encode(b'ordinary words '*100).decode(), 'data:image/jpeg,'+payload(),
    'prefix '+payload(), payload()+' note: ordinary prose', '🙂'*1000])
def test_false_positives(value):
    assert encoded_kind(value) is None


def test_minimum_and_bounds():
    assert encoded_kind(base64.b64encode(b'\xff\xd8\xff'+b'x'*30).decode()) is None
    assert encoded_kind('/9j/'+('A'*MAX_ENCODED)) is None
    assert MIN_ENCODED==256


def test_import_api_redaction_search_and_dedup(tmp_path):
    raw=payload()
    text=f'[3/15/26, 9:00:00 AM] Self: {raw}\n[3/15/26, 9:01:00 AM] Friend: Normal 👩🏽‍💻\nSecond line'
    parsed=read_export(archive(text))
    assert parsed.messages[0].kind=='encoded_image'
    store=Store(tmp_path/'encoded.sqlite3')
    saved=store.import_chat(parsed,'Synthetic','Self','Friend','UTC')
    repeated=store.import_chat(parsed,'Synthetic','Self','Friend','UTC',saved['conversation_id'])
    assert repeated['added_messages']==0 and repeated['duplicate_messages']==2
    with store.connection() as db:
        row=db.execute("SELECT * FROM messages WHERE type='encoded_image'").fetchone()
        assert row['original_text']==raw and row['normalized_text']=='' and row['include_in_rag']==0
        assert raw not in ' '.join(r[0] for r in db.execute('SELECT text FROM chunks'))
    with TestClient(create_app(store.path)) as client:
        route='/conversations/'+saved['conversation_id']
        page=client.get(route+'/messages').json()
        assert page['items'][0]['encoded'] is True
        assert page['items'][0]['original_text']=='encoded image omitted'
        assert '/9j/' not in json.dumps(page)
        assert client.get(route+'/messages',params={'q':'/9j/'}).json()['total']==0
        assert client.get(route+'/messages?type=encoded_image').json()['total']==1
        assert client.get(route).json()['type_counts']['encoded_image']==1
        found=client.post('/retrieve',json=dict(contact_id=saved['contact_id'],conversation_id=saved['conversation_id'],query='normal')).json()
        assert '/9j/' not in json.dumps(found)


def test_migration_preserves_rows_and_rebuilds_only_affected(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    store=Store(path)
    raw=payload()
    parsed=read_export(archive(f'[3/15/26, 9:00:00 AM] Self: {raw}\n[3/15/26, 9:01:00 AM] Friend: clean'))
    parsed.messages[0].kind='text'  # Simulate pre-filter import, including legacy fingerprint/vector.
    first=store.import_chat(parsed,'First','Self','Friend','UTC')
    clean=read_export(archive('[3/15/26, 9:00:00 AM] Self: unaffected\n[3/15/26, 9:01:00 AM] Friend: hello'))
    second=store.import_chat(clean,'Second','Self','Friend','UTC')
    with store.connection() as db:
        before=[tuple(r) for r in db.execute('SELECT id,fingerprint,original_text,import_id FROM messages ORDER BY id')]
        audits=[tuple(r) for r in db.execute('SELECT * FROM imports ORDER BY id')]
        other=[tuple(r) for r in db.execute('SELECT c.id,e.vector FROM chunks c JOIN embeddings e ON e.chunk_id=c.id WHERE c.conversation_id=?',(second['conversation_id'],))]
    class Tracking(DevelopmentEmbedding):
        def __init__(self):self.calls=[]
        def embed(self,text):self.calls.append(text);return super().embed(text)
    provider=Tracking(); migrated=Store(path,provider)
    assert provider.calls and all('/9j/' not in text and 'unaffected' not in text for text in provider.calls)
    with migrated.connection() as db:
        assert before==[tuple(r) for r in db.execute('SELECT id,fingerprint,original_text,import_id FROM messages ORDER BY id')]
        assert audits==[tuple(r) for r in db.execute('SELECT * FROM imports ORDER BY id')]
        assert other==[tuple(r) for r in db.execute('SELECT c.id,e.vector FROM chunks c JOIN embeddings e ON e.chunk_id=c.id WHERE c.conversation_id=?',(second['conversation_id'],))]
        assert db.execute("SELECT COUNT(*) FROM messages WHERE type='encoded_image' AND include_in_rag=0 AND normalized_text=''").fetchone()[0]==1
    count=len(provider.calls);Store(path,provider);assert len(provider.calls)==count
    parsed.messages[0].kind='encoded_image'
    result=migrated.import_chat(parsed,'First','Self','Friend','UTC',first['conversation_id'])
    assert result['added_messages']==0 and result['duplicate_messages']==2


def test_migration_failure_rolls_back(tmp_path):
    store=Store(tmp_path/'rollback.sqlite3')
    parsed=read_export(archive(f'[3/15/26, 9:00:00 AM] Self: {payload()}\n[3/15/26, 9:01:00 AM] Friend: clean'))
    parsed.messages[0].kind='text'
    store.import_chat(parsed,'Synthetic','Self','Friend','UTC')
    class Broken(DevelopmentEmbedding):
        def embed(self,text):raise RuntimeError('Synthetic failure')
    with pytest.raises(RuntimeError):Store(store.path,Broken())
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM messages WHERE type='text' AND include_in_rag=1").fetchone()[0]==2
        assert '/9j/' in db.execute('SELECT text FROM chunks').fetchone()[0]


def test_senderless_encoded_migration_and_reimport(tmp_path):
    store=Store(tmp_path/'senderless.sqlite3')
    text=payload()+'\n[3/15/26, 9:00:00 AM] Self: hi\n[3/15/26, 9:01:00 AM] Friend: hello'
    legacy=read_export(archive(text));legacy.messages[0].kind='unknown'
    saved=store.import_chat(legacy,'Synthetic','Self','Friend','UTC')
    migrated=Store(store.path)
    result=migrated.import_chat(read_export(archive(text)),'Synthetic','Self','Friend','UTC',saved['conversation_id'])
    assert result['added_messages']==0 and result['duplicate_messages']==3
