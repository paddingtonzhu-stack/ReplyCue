"""Read projections: bounded message pages, no fingerprints or vector payloads."""
import json
from .parser import ImportProblem


SUMMARY = '''SELECT v.id,v.contact_id,c.display_name,c.normalized_phone,v.timezone,
 (SELECT COUNT(*) FROM messages WHERE conversation_id=v.id) AS message_count,
 (SELECT COUNT(*) FROM messages WHERE conversation_id=v.id AND include_in_rag=1) AS rag_count,
 (SELECT MIN(utc_datetime) FROM messages WHERE conversation_id=v.id) AS first_timestamp,
 (SELECT MAX(utc_datetime) FROM messages WHERE conversation_id=v.id) AS last_timestamp,
 (SELECT COUNT(*) FROM chunks WHERE conversation_id=v.id) AS chunk_count,
 (SELECT COUNT(*) FROM embeddings e JOIN chunks k ON k.id=e.chunk_id WHERE k.conversation_id=v.id) AS embedding_count,
 (SELECT strftime('%Y-%m-%dT%H:%M:%SZ',created_at) FROM imports WHERE conversation_id=v.id ORDER BY created_at DESC,rowid DESC LIMIT 1) AS latest_import_time,
 (SELECT status FROM imports WHERE conversation_id=v.id ORDER BY created_at DESC,rowid DESC LIMIT 1) AS latest_import_status
 FROM conversations v JOIN contacts c ON c.id=v.contact_id'''


def require_conversation(db, conversation_id):
    if not db.execute('SELECT 1 FROM conversations WHERE id=?',(conversation_id,)).fetchone():
        raise ImportProblem('conversation_missing','Conversation not found.',404)


def summaries(store):
    with store.connection() as db:
        return [dict(row) for row in db.execute(SUMMARY+' ORDER BY v.created_at DESC,v.id')]


def detail(store, conversation_id):
    with store.connection() as db:
        require_conversation(db,conversation_id)
        result=dict(db.execute(SUMMARY+' WHERE v.id=?',(conversation_id,)).fetchone())
        result['participants']=[dict(r) for r in db.execute(
            'SELECT alias,role FROM participants WHERE conversation_id=? ORDER BY role,alias',(conversation_id,))]
        result['type_counts']={r['type']:r['n'] for r in db.execute(
            'SELECT type,COUNT(*) n FROM messages WHERE conversation_id=? GROUP BY type',(conversation_id,))}
        result['import_count']=db.execute('SELECT COUNT(*) FROM imports WHERE conversation_id=?',(conversation_id,)).fetchone()[0]
        # Legacy imports have unknown parsed/skipped counts and warnings, never guessed zeros.
        imports=[]
        for row in db.execute('''SELECT strftime('%Y-%m-%dT%H:%M:%SZ',i.created_at) created_at,
            i.status,i.added_count,d.parsed_count,d.skipped_count,d.warnings_json
            FROM imports i LEFT JOIN import_details d ON d.import_id=i.id
            WHERE i.conversation_id=? ORDER BY i.created_at DESC,i.rowid DESC LIMIT 50''',(conversation_id,)):
            item=dict(row)
            raw=item.pop('warnings_json')
            item['warnings']=json.loads(raw) if raw is not None else None
            imports.append(item)
        result['imports']=imports
        result['embedding_providers']=[dict(r) for r in db.execute('''SELECT e.provider,e.dimensions,COUNT(*) count
            FROM embeddings e JOIN chunks c ON c.id=e.chunk_id WHERE c.conversation_id=? GROUP BY e.provider,e.dimensions''',(conversation_id,))]
        return result


def messages(store, conversation_id, offset=0, limit=50, order='asc', message_type=None, rag=None, query=None):
    conditions=['m.conversation_id=?']; values=[conversation_id]
    if message_type is not None:
        conditions.append('m.type=?');values.append(message_type)
    if rag is not None:
        conditions.append('m.include_in_rag=?');values.append(int(rag))
    if query:
        # Literal substring search: %, _ and quotes have no SQL meaning here.
        conditions.append('instr(lower(m.original_text),lower(?))>0');values.append(query)
        conditions.append("m.type NOT LIKE 'encoded_%'")
    where=' AND '.join(conditions)
    direction='DESC' if order=='desc' else 'ASC'
    with store.connection() as db:
        db.execute('BEGIN')  # Count and page use the same read snapshot.
        require_conversation(db,conversation_id)
        total=db.execute('SELECT COUNT(*) FROM messages m WHERE '+where,values).fetchone()[0]
        rows=db.execute('''SELECT m.id,
            CASE WHEN m.type LIKE 'encoded_%' THEN replace(m.type,'_',' ') || ' omitted' ELSE m.original_text END AS original_text,
            m.type LIKE 'encoded_%' AS encoded,m.original_timestamp,m.local_datetime,m.utc_datetime,
            m.timezone,m.type,m.include_in_rag,m.line_start,m.line_end,m.source_order,p.alias,p.role
            FROM messages m LEFT JOIN participants p ON p.id=m.sender_id WHERE '''+where+
            f' ORDER BY m.utc_datetime {direction},m.source_order {direction},m.id {direction} LIMIT ? OFFSET ?',
            values+[limit,offset]).fetchall()
        items=[dict(r) for r in rows]
        for item in items:
            item['include_in_rag']=bool(item['include_in_rag'])
            item['encoded']=bool(item['encoded'])
        return dict(items=items,total=total,offset=offset,limit=limit,
                    next_offset=offset+len(items) if offset+len(items)<total else None)
