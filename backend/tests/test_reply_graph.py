from dataclasses import replace

from fastapi.testclient import TestClient

from app.config import Settings
from app.embeddings import DevelopmentEmbedding
from app.main import create_app
from app.parser import read_export
from app.storage import Store
from test_import import SAMPLE, archive


BASE_SETTINGS = Settings(
    openai_api_key=None,
    chat_model='test-model',
    embedding_model='test-embedding',
    embedding_dimensions=128,
    rag_message_threshold=10,
    rag_character_threshold=10000,
    direct_context_messages=10,
    rag_recent_messages=4,
    rag_top_k=3,
)


class FakeGenerator:
    configured = True

    def __init__(self):
        self.calls=[]

    def generate(self,context,incoming_message,intent):
        self.calls.append((context,incoming_message,intent))
        return ['First reply','Second reply','Third reply']


def test_short_chat_uses_direct_context_but_is_still_vectored(tmp_path):
    generator=FakeGenerator()
    with TestClient(create_app(tmp_path/'short.sqlite3',DevelopmentEmbedding(),BASE_SETTINGS,generator)) as client:
        blob=archive()
        preview=client.post('/imports/preview',files={'file':('chat.zip',blob)}).json()
        saved=client.post('/imports/confirm',files={'file':('chat.zip',blob)},data={
            'display_name':'Friend','self_alias':'Self','contact_alias':'Friend','timezone':'UTC',
            'transcript_hash':preview['transcript_hash'],
        }).json()
        assert saved['embedding_count'] > 0
        response=client.post(f"/conversations/{saved['conversation_id']}/reply-suggestions",json={
            'contact_id':saved['contact_id'],'incoming_message':'Are you free tomorrow?','intent':'Make a plan',
        })
        assert response.status_code==200,response.text
        body=response.json()
        assert body['route']=='direct' and body['sources']==[]
        assert body['suggestions']==['First reply','Second reply','Third reply']
        assert 'garden café' in generator.calls[0][0]


def test_long_chat_uses_rag_and_returns_sources(tmp_path):
    generator=FakeGenerator()
    settings=replace(BASE_SETTINGS,rag_message_threshold=5)
    store=Store(tmp_path/'long.sqlite3',DevelopmentEmbedding(),settings.rag_message_threshold,settings.rag_character_threshold)
    saved=store.import_chat(read_export(archive(SAMPLE)),'Friend','Self','Friend','UTC')
    with TestClient(create_app(store.path,DevelopmentEmbedding(),settings,generator)) as client:
        response=client.post(f"/conversations/{saved['conversation_id']}/reply-suggestions",json={
            'contact_id':saved['contact_id'],'incoming_message':'Want to get coffee at the garden café?'
        })
        assert response.status_code==200,response.text
        body=response.json()
        assert body['route']=='rag'
        assert body['sources'] and body['sources'][0]['message_ids']
        assert 'Relevant older messages:' in generator.calls[0][0]


def test_reply_endpoint_requires_openai_configuration(tmp_path):
    from app.ai import OpenAIReplyGenerator
    store=Store(tmp_path/'missing-key.sqlite3')
    saved=store.import_chat(read_export(archive()),'Friend','Self','Friend','UTC')
    with TestClient(create_app(store.path,DevelopmentEmbedding(),BASE_SETTINGS,OpenAIReplyGenerator(None,'test'))) as client:
        response=client.post(f"/conversations/{saved['conversation_id']}/reply-suggestions",json={
            'contact_id':saved['contact_id'],'incoming_message':'Hello'
        })
        assert response.status_code==503
        assert response.json()['error']['code']=='openai_not_configured'
