from contextlib import asynccontextmanager
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .parser import read_export, ImportProblem, MAX_ZIP
from .storage import Store

LOCAL_ORIGINS = ['http://localhost:5173','http://127.0.0.1:5173']


class BoundedRequests:
    """Bound the entire multipart request before the multipart parser can spool it."""
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        headers=dict(scope['headers'])
        origin=headers.get(b'origin',b'').decode('latin1')
        if origin and origin not in LOCAL_ORIGINS:
            return await JSONResponse({'error':{'code':'origin','message':'Only the local frontend may access this API.'}},403)(scope,receive,send)
        chunks,total=[],0
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            body=message.get('body',b'');total+=len(body)
            if total>MAX_ZIP+1024*1024:
                return await JSONResponse({'error':{'code':'request_size','message':'Request exceeds 11 MB.'}},413)(scope,receive,send)
            chunks.append(body)
            if not message.get('more_body'):break
        consumed=False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)


class RetrievalRequest(BaseModel):
    contact_id: str = Field(min_length=1,max_length=100)
    conversation_id: str = Field(min_length=1,max_length=100)
    query: str = Field(min_length=1,max_length=2000)
    top_k: int = Field(default=5,ge=1,le=20)


def create_app(db_path=None,provider=None):
    path = db_path or os.environ.get('REPLYCUE_DB_PATH') or Path(__file__).resolve().parents[1]/'data'/'replycue.sqlite3'
    @asynccontextmanager
    async def lifespan(app):
        app.state.store=Store(path,provider)
        yield
    app=FastAPI(title='ReplyCue local API',lifespan=lifespan)
    app.add_middleware(BoundedRequests)
    app.add_middleware(CORSMiddleware,allow_origins=LOCAL_ORIGINS,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

    @app.exception_handler(ImportProblem)
    async def import_error(request,exc):
        return JSONResponse({'error':{'code':exc.code,'message':exc.message}},exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        # Do not reflect multipart field values or private input into diagnostics.
        return JSONResponse({'error':{'code':'validation','message':'Check required fields, lengths, and value formats.'}},422)

    @app.exception_handler(Exception)
    async def unexpected_error(request,exc):
        return JSONResponse({'error':{'code':'internal','message':'Operation failed. No partial import was saved.'}},500)

    @app.get('/health')
    def health(request:Request):
        with request.app.state.store.connection() as db:db.execute('SELECT 1')
        return {'status':'ok','storage':'SQLite','embedding_provider':request.app.state.store.provider.name}

    @app.get('/conversations')
    def conversations(request:Request):return request.app.state.store.conversations()

    async def parse_upload(file,transcript_name):
        try:
            if not file.filename or not file.filename.lower().endswith('.zip'):
                raise ImportProblem('file_type','Choose a WhatsApp export ZIP.')
            data=await file.read(MAX_ZIP+1)
            return await run_in_threadpool(read_export,data,transcript_name)
        finally:await file.close()

    @app.post('/imports/preview')
    async def preview(file:UploadFile=File(...),transcript_name:str|None=Form(None)):
        parsed=await parse_upload(file,transcript_name)
        return parsed.preview()

    @app.post('/imports/confirm')
    async def confirm(request:Request,file:UploadFile=File(...),display_name:str=Form(...),
                      self_alias:str=Form(...),contact_alias:str=Form(...),timezone:str=Form(...),
                      transcript_hash:str=Form(...),transcript_name:str|None=Form(None),conversation_id:str|None=Form(None),phone:str|None=Form(None)):
        parsed=await parse_upload(file,transcript_name)
        if parsed.transcript_hash!=transcript_hash:
            raise ImportProblem('preview_changed','The transcript changed. Preview it again before confirming.',409)
        return await run_in_threadpool(request.app.state.store.import_chat,parsed,display_name,self_alias,contact_alias,timezone,conversation_id,phone)

    @app.post('/retrieve')
    def retrieve(request:Request,body:RetrievalRequest):
        if not body.query.strip():raise ImportProblem('query','Enter a search query.')
        return request.app.state.store.retrieve(body.contact_id,body.conversation_id,body.query,body.top_k)
    return app


app=create_app()
