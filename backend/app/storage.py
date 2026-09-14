from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .embeddings import DevelopmentEmbedding, cosine
from .parser import ImportProblem, normalize
from .encoded import encoded_kind, KINDS

SCHEMA = '''
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
 normalized_phone TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, contact_id TEXT NOT NULL REFERENCES contacts(id),
 timezone TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 archive_hash TEXT NOT NULL, transcript_hash TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, added_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS participants(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 alias TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('self','contact')), contact_id TEXT REFERENCES contacts(id),
 UNIQUE(conversation_id, alias));
CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 contact_id TEXT NOT NULL REFERENCES contacts(id), sender_id TEXT REFERENCES participants(id),
 source_order INTEGER NOT NULL, line_start INTEGER NOT NULL, line_end INTEGER NOT NULL,
 original_timestamp TEXT, local_datetime TEXT, timezone TEXT NOT NULL, utc_datetime TEXT,
 type TEXT NOT NULL, original_text TEXT NOT NULL, normalized_text TEXT NOT NULL,
 include_in_rag INTEGER NOT NULL, fingerprint TEXT NOT NULL, occurrence INTEGER NOT NULL,
 import_id TEXT NOT NULL REFERENCES imports(id), UNIQUE(conversation_id,fingerprint,occurrence));
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 contact_id TEXT NOT NULL REFERENCES contacts(id), text TEXT NOT NULL,
 first_message_id TEXT NOT NULL REFERENCES messages(id), last_message_id TEXT NOT NULL REFERENCES messages(id));
CREATE TABLE IF NOT EXISTS chunk_messages(chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
 message_id TEXT NOT NULL REFERENCES messages(id), ordinal INTEGER NOT NULL, PRIMARY KEY(chunk_id,message_id));
CREATE TABLE IF NOT EXISTS embeddings(chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
 provider TEXT NOT NULL, dimensions INTEGER NOT NULL, vector TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS messages_conversation_time ON messages(conversation_id,utc_datetime,source_order);
CREATE INDEX IF NOT EXISTS chunks_scope ON chunks(contact_id,conversation_id);
CREATE INDEX IF NOT EXISTS imports_conversation ON imports(conversation_id);
CREATE TABLE IF NOT EXISTS import_details(import_id TEXT PRIMARY KEY REFERENCES imports(id),
 parsed_count INTEGER NOT NULL, skipped_count INTEGER NOT NULL, warnings_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS messages_page ON messages(conversation_id,utc_datetime,source_order,id);
CREATE INDEX IF NOT EXISTS messages_type_page ON messages(conversation_id,type,utc_datetime,source_order,id);
CREATE INDEX IF NOT EXISTS messages_rag_page ON messages(conversation_id,include_in_rag,utc_datetime,source_order,id);
CREATE INDEX IF NOT EXISTS chunks_conversation ON chunks(conversation_id);
CREATE INDEX IF NOT EXISTS imports_latest ON imports(conversation_id,created_at DESC,id DESC);
INSERT OR IGNORE INTO schema_version VALUES(2);
'''


def get_timezone(value):
    if len(value) > 100:
        raise ImportProblem('timezone', 'Invalid timezone.')
    match = re.fullmatch(r'([+-])(\d{2}):(\d{2})', value)
    if match:
        hours, minutes = int(match[2]), int(match[3])
        if hours > 14 or minutes > 59 or hours == 14 and minutes:
            raise ImportProblem('timezone', 'Offset must be between -14:00 and +14:00.')
        return timezone(timedelta(minutes=(hours*60+minutes)*(1 if match[1]=='+' else -1)))
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ImportProblem('timezone', 'Enter an IANA timezone such as Europe/Berlin or an offset such as +02:00.') from None


def normalize_phone(value):
    if value is None or not value.strip():
        return None
    if len(value) > 100 or not re.fullmatch(r'[+0-9\s().\-]+', value):
        raise ImportProblem('phone', 'Enter a phone number using digits, an optional leading +, spaces, parentheses or hyphens.')
    phone = re.sub(r'[\s().\-]', '', value)
    if not re.fullmatch(r'\+?[0-9]{3,15}', phone):
        raise ImportProblem('phone', 'Enter 3–15 digits with an optional leading + and country code.')
    return phone


class Store:
    def __init__(self, path, provider=None):
        self.path = Path(path)
        self.provider = provider or DevelopmentEmbedding()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript(SCHEMA)
        self._filter_encoded_history()

    def _filter_encoded_history(self):
        # Re-check text rows to cover imports made by older app versions. Preserve
        # fingerprints/IDs and audits so repeat imports still match their sources.
        with self.connection() as db:
            with db:
                db.execute('BEGIN IMMEDIATE')
                affected={}
                rows=db.execute("SELECT id,conversation_id,contact_id,original_text FROM messages WHERE type IN ('text','unknown') AND length(original_text)>=256")
                for row in rows:
                    kind=encoded_kind(row['original_text'])
                    if kind:
                        db.execute('UPDATE messages SET type=?,normalized_text=?,include_in_rag=0 WHERE id=?',(kind,'',row['id']))
                        affected[row['conversation_id']]=row['contact_id']
                for conversation_id,contact_id in affected.items():
                    self._rebuild_chunks(db,conversation_id,contact_id)
                db.execute('INSERT OR IGNORE INTO schema_version VALUES(3)')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
        finally:
            db.close()

    def conversations(self):
        from .history import summaries
        return summaries(self)

    def import_chat(self, parsed, display_name, self_alias, contact_alias, tz_name, conversation_id=None, phone=None):
        normalized_phone = normalize_phone(phone)
        display_name = display_name.strip()
        if not display_name or len(display_name)>120:
            raise ImportProblem('contact_name', 'Contact display name is required (up to 120 characters).')
        if self_alias == contact_alias or set(parsed.aliases) != {self_alias, contact_alias}:
            raise ImportProblem('alias_mapping', 'Select two distinct detected aliases. Only one-to-one conversations are supported.')
        tz = get_timezone(tz_name)
        warnings = list(parsed.warnings)
        with self.connection() as db:
            # One transaction includes identity, messages, chunks, and embeddings.
            # Any provider/database/validation failure rolls everything back.
            with db:
                db.execute('BEGIN IMMEDIATE')
                if conversation_id:
                    conversation = db.execute('SELECT * FROM conversations WHERE id=?',(conversation_id,)).fetchone()
                    if not conversation:
                        raise ImportProblem('conversation_missing', 'Selected conversation does not exist.',404)
                    contact_id = conversation['contact_id']
                    roles = {r['alias']:r['role'] for r in db.execute('SELECT * FROM participants WHERE conversation_id=?',(conversation_id,))}
                    if roles != {self_alias:'self',contact_alias:'contact'} or conversation['timezone'] != tz_name:
                        raise ImportProblem('mapping_changed', 'Existing conversation alias mapping/timezone differs. Use its original mapping or create a new conversation.')
                    if normalized_phone is not None:
                        db.execute('UPDATE contacts SET normalized_phone=? WHERE id=?',(normalized_phone,contact_id))
                else:
                    contact_id, conversation_id = str(uuid4()), str(uuid4())
                    db.execute('INSERT INTO contacts(id,display_name,normalized_phone) VALUES(?,?,?)',(contact_id,display_name,normalized_phone))
                    db.execute('INSERT INTO conversations(id,contact_id,timezone) VALUES(?,?,?)',(conversation_id,contact_id,tz_name))
                    for alias,role in [(self_alias,'self'),(contact_alias,'contact')]:
                        db.execute('INSERT INTO participants VALUES(?,?,?,?,?)',(str(uuid4()),conversation_id,alias,role,contact_id if role=='contact' else None))
                participant_ids = {r['alias']:r['id'] for r in db.execute('SELECT * FROM participants WHERE conversation_id=?',(conversation_id,))}
                import_id = str(uuid4())
                db.execute('INSERT INTO imports(id,conversation_id,archive_hash,transcript_hash,status) VALUES(?,?,?,?,?)',
                           (import_id,conversation_id,parsed.archive_hash,parsed.transcript_hash,'processing'))
                occurrences, added = Counter(), 0
                for order, msg in enumerate(parsed.messages):
                    utc = None
                    if msg.local_datetime:
                        local = datetime.fromisoformat(msg.local_datetime)
                        aware = local.replace(tzinfo=tz,fold=0)
                        if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != local:
                            raise ImportProblem('nonexistent_time','A timestamp falls in a daylight-saving gap. Confirm the correct export timezone/offset.')
                        if local.replace(tzinfo=tz,fold=1).utcoffset() != aware.utcoffset():
                            warning = 'Ambiguous daylight-saving timestamps use the earlier occurrence (fold=0).'
                            if warning not in warnings: warnings.append(warning)
                        utc = aware.astimezone(timezone.utc).isoformat()
                    normalized = normalize(msg.text)
                    # Encoded files formerly appeared as text. Keep that fingerprint
                    # contract while removing payloads from the search representation.
                    fingerprint_kind = ('text' if msg.sender is not None else 'unknown') if msg.kind in KINDS else msg.kind
                    fingerprint = sha256(json.dumps([msg.sender,msg.timestamp,normalized,fingerprint_kind],ensure_ascii=False).encode()).hexdigest()
                    if msg.kind in KINDS:normalized=''
                    occurrence = occurrences[fingerprint]
                    occurrences[fingerprint] += 1
                    message_id = sha256(f'{conversation_id}:{fingerprint}:{occurrence}'.encode()).hexdigest()
                    result = db.execute('''INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (message_id,conversation_id,contact_id,participant_ids.get(msg.sender),order,msg.line_start,msg.line_end,
                         msg.timestamp,msg.local_datetime,tz_name,utc,msg.kind,msg.text,normalized,int(msg.kind=='text'),fingerprint,occurrence,import_id))
                    added += result.rowcount
                if added:
                    self._rebuild_chunks(db, conversation_id, contact_id)
                db.execute("UPDATE imports SET status='complete',added_count=? WHERE id=?",(added,import_id))
                db.execute('INSERT INTO import_details VALUES(?,?,?,?)',
                           (import_id,len(parsed.messages),len(parsed.messages)-added,json.dumps(warnings)))
                chunks = db.execute('SELECT COUNT(*) FROM chunks WHERE conversation_id=?',(conversation_id,)).fetchone()[0]
                embeddings = db.execute('SELECT COUNT(*) FROM embeddings e JOIN chunks c ON c.id=e.chunk_id WHERE c.conversation_id=?',(conversation_id,)).fetchone()[0]
                contact = db.execute('SELECT display_name,normalized_phone FROM contacts WHERE id=?',(contact_id,)).fetchone()
                return dict(import_id=import_id,conversation_id=conversation_id,contact_id=contact_id,
                            display_name=contact['display_name'],normalized_phone=contact['normalized_phone'],
                            added_messages=added,duplicate_messages=len(parsed.messages)-added,
                            chunk_count=chunks,embedding_count=embeddings,provider=self.provider.name,warnings=warnings)

    def _rebuild_chunks(self,db,conversation_id,contact_id):
        db.execute('DELETE FROM chunks WHERE conversation_id=?',(conversation_id,))
        rows = db.execute('''SELECT m.*,p.role FROM messages m JOIN participants p ON p.id=m.sender_id
            WHERE m.conversation_id=? AND include_in_rag=1 ORDER BY m.utc_datetime,m.source_order,m.id''',(conversation_id,)).fetchall()
        group, chars, last, chunk_number = [], 0, None, 0
        def flush():
            nonlocal chunk_number
            if not group: return
            text = '\n'.join(item[1] for item in group)
            ids = list(dict.fromkeys(item[0] for item in group))
            chunk_id = sha256((conversation_id+'|'+str(chunk_number)+'|'+json.dumps(ids)+'|'+text).encode()).hexdigest()
            chunk_number += 1
            db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',(chunk_id,conversation_id,contact_id,text,ids[0],ids[-1]))
            db.executemany('INSERT INTO chunk_messages VALUES(?,?,?)',[(chunk_id,message_id,n) for n,message_id in enumerate(ids)])
            vector = self.provider.embed(text)
            if len(vector)!=self.provider.dimensions or not all(math.isfinite(v) for v in vector):
                raise ValueError('Embedding provider dimension mismatch')
            db.execute('INSERT INTO embeddings VALUES(?,?,?,?)',(chunk_id,self.provider.name,len(vector),json.dumps(vector)))
        for row in rows:
            moment = datetime.fromisoformat(row['utc_datetime'])
            # Split very long messages without altering stored original text.
            for start in range(0,len(row['original_text']),1200):
                part = f"{row['role']}: {row['original_text'][start:start+1200]}"
                if group and (chars+len(part)+1>1800 or len(group)>=12 or last and moment-last>timedelta(hours=6)):
                    flush();group=[];chars=0
                group.append((row['id'],part));chars+=len(part)+1;last=moment
        flush()

    def retrieve(self,contact_id,conversation_id,query,top_k):
        vector = self.provider.embed(query)
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM conversations WHERE id=? AND contact_id=?',(conversation_id,contact_id)).fetchone():
                raise ImportProblem('scope_missing','Contact/conversation scope not found.',404)
            rows = db.execute('''SELECT c.*,e.vector FROM chunks c JOIN embeddings e ON e.chunk_id=c.id
              WHERE c.contact_id=? AND c.conversation_id=? AND e.provider=? AND e.dimensions=?''',
              (contact_id,conversation_id,self.provider.name,self.provider.dimensions)).fetchall()
            ranked = sorted([(cosine(vector,json.loads(r['vector'])),r) for r in rows],key=lambda x:x[0],reverse=True)[:top_k]
            results=[]
            for score,row in ranked:
                sources=[dict(r) for r in db.execute('''SELECT m.id,m.line_start,m.line_end,m.import_id,m.original_timestamp
                    FROM chunk_messages cm JOIN messages m ON m.id=cm.message_id WHERE cm.chunk_id=? ORDER BY cm.ordinal''',(row['id'],))]
                results.append(dict(chunk_id=row['id'],score=score,text=row['text'],sources=sources))
            return dict(provider=self.provider.name,quality='Development lexical feature hashing; not semantic search.',results=results)
