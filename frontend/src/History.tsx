import { useEffect, useRef, useState } from 'react';
import { api, type Conversation, type ConversationDetail, type ChatMessage, type MessagePage } from './api';
import { contactLabel, formatTimestamp } from './format';
import { encodedMediaKind, encodedLabel } from './encoded';

export default function History({ revision, active }: { revision: number; active: boolean }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [items, setItems] = useState<ChatMessage[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [total, setTotal] = useState(0);
  const [type, setType] = useState('');
  const [draftQuery, setDraftQuery] = useState('');
  const [query, setQuery] = useState('');
  const [retry, setRetry] = useState(0);
  const [listBusy, setListBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [listError, setListError] = useState('');
  const [error, setError] = useState('');
  const initialized = useRef(false);
  const generation = useRef(0);

  useEffect(() => {
    if (!active && !initialized.current) return;
    initialized.current = true;
    let cancelled = false;
    setListBusy(true); setListError('');
    api<Conversation[]>('/conversations').then(rows => { if (!cancelled) setConversations(rows); })
      .catch(e => { if (!cancelled) setListError(e.message); })
      .finally(() => { if (!cancelled) setListBusy(false); });
    return () => { cancelled = true; };
  }, [active, revision, retry]);

  function path(offset: number) {
    const params = new URLSearchParams({ offset: String(offset), limit: '50' });
    if (type) params.set('type', type);
    if (query) params.set('q', query);
    return `/conversations/${encodeURIComponent(selected)}/messages?${params}`;
  }
  useEffect(() => {
    const current = ++generation.current;
    if (!selected) { setBusy(false); setError(''); setDetail(null); setItems([]); setNext(null); return; }
    setBusy(true); setError(''); setItems([]); setDetail(null); setNext(null);
    Promise.all([api<ConversationDetail>(`/conversations/${encodeURIComponent(selected)}`), api<MessagePage>(path(0))])
      .then(([info, page]) => {
        if (generation.current !== current) return;
        setDetail(info); setItems(page.items); setNext(page.next_offset); setTotal(page.total);
      }).catch(e => { if (generation.current === current) setError(e.message); })
      .finally(() => { if (generation.current === current) setBusy(false); });
    return () => { generation.current++; };
  }, [selected, type, query, revision, retry]);

  async function more() {
    if (next === null || busy) return;
    const current = generation.current;
    setBusy(true); setError('');
    try {
      const page = await api<MessagePage>(path(next));
      if (current !== generation.current) return;
      setItems(old => [...old, ...page.items]); setNext(page.next_offset); setTotal(page.total);
    } catch (e) { if (current === generation.current) setError((e as Error).message); }
    finally { if (current === generation.current) setBusy(false); }
  }

  return <section aria-labelledby="history-title" className="history">
    <div className="section-heading"><h2 id="history-title">Conversations</h2><button className="secondary" disabled={listBusy || busy} onClick={() => setRetry(n => n + 1)}>Refresh</button></div>
    <p className="intro">Your saved chats. Reply suggestions still use sample history.</p>
    {listBusy && <p role="status">Loading conversations…</p>}
    {listError && <div role="alert"><p className="error">{listError}</p><button className="secondary" onClick={() => setRetry(n => n + 1)}>Retry connection</button></div>}
    {!listBusy && !listError && conversations.length === 0 && <p>No saved conversations yet. Use Import chat to add one.</p>}
    {conversations.length > 0 && <><label htmlFor="history-conversation">Saved conversation</label><select id="history-conversation" value={selected} onChange={e => {setSelected(e.target.value); setType(''); setQuery(''); setDraftQuery('');}}>
      <option value="">Choose a conversation</option>{conversations.map(c => <option key={c.id} value={c.id}>{contactLabel(c)} · {c.message_count} records · {formatTimestamp(c.last_timestamp, { timeZone: c.timezone })}</option>)}
    </select></>}
    {!selected && conversations.length > 0 && <p>Select a saved conversation to see its messages and import information.</p>}
    {selected && <>
      {detail && <><h3>{contactLabel(detail)}</h3><p>{detail.participants.map(p => `${p.role === 'self' ? 'Me' : 'Contact'}: ${p.alias}`).join(' · ')}</p>
        <p className="field-hint">{formatTimestamp(detail.first_timestamp, { timeZone: detail.timezone })} — {formatTimestamp(detail.last_timestamp, { timeZone: detail.timezone })} · {detail.timezone}</p>
        <details className="history-info"><summary>Conversation and import information</summary>
          <p>{detail.message_count} records · {detail.rag_count} eligible for retrieval</p>
          <p>{Object.entries(detail.type_counts).map(([key, n]) => `${key}: ${n}`).join(' · ')}</p>
          <p>{detail.chunk_count} text chunks · {detail.embedding_count} embeddings</p>
          {detail.embedding_providers.map(p => <p key={p.provider}>{p.provider} · {p.dimensions} dimensions · {p.count} chunks</p>)}
          <p className="field-hint">Development lexical search, not semantic AI. Media and system events are excluded from retrieval.</p>
          <h4>Recent imports</h4><p>{detail.import_count} imports total · showing latest {detail.imports.length}</p>
          {detail.imports.map((entry, index) => <div className="import-audit" key={index}>
            <strong>{formatTimestamp(entry.created_at)} · {entry.status}</strong>
            <p>{entry.parsed_count ?? 'Unknown'} parsed · {entry.added_count} added · {entry.skipped_count ?? 'Unknown'} skipped</p>
            {entry.warnings === null ? <p>Detailed parsing information was not saved for this older import.</p> : <ul>{entry.warnings.map(w => <li key={w}>{w}</li>)}</ul>}
          </div>)}
        </details>
        <form className="history-filters" onSubmit={e => {e.preventDefault();setQuery(draftQuery.trim());}}>
          <label htmlFor="history-type">Message type</label><select id="history-type" value={type} onChange={e => setType(e.target.value)}><option value="">All types</option>{Object.keys(detail.type_counts).map(t => <option key={t} value={t}>{t}</option>)}</select>
          <label htmlFor="history-search">Search saved text</label><input id="history-search" type="search" maxLength={200} value={draftQuery} onChange={e => setDraftQuery(e.target.value)}/><button className="secondary" type="submit">Search</button>
        </form>
        <p role="status">Showing {items.length} of {total} matching records · oldest first</p>
        {!busy && items.length === 0 && <p>No messages match these filters.</p>}
        <ol className="timeline" aria-label="Saved messages">{items.map(message => {
          const encoded = message.type.startsWith('encoded_') ? message.type : encodedMediaKind(message.original_text);
          const displayType = encoded || message.type;
          return <li key={message.id} className={`message ${displayType === 'text' ? message.role || 'system' : 'event'}`}>
          <div><strong>{message.role === 'self' ? 'Me' : message.alias || 'System'}</strong> <small>{formatTimestamp(message.local_datetime, { wallClock: true })}</small></div>
          {displayType !== 'text' && <span className="event-label">{encoded ? encodedLabel(encoded) : message.type === 'deleted' ? 'Deleted message' : message.type === 'call' ? 'Call event' : `${message.type} event`} · not used for retrieval</span>}
          {!encoded && <p className="message-text">{message.original_text}</p>}
          <details><summary>Parsing details</summary><p>Type: {displayType.replace('_', ' ')} · {!encoded && message.include_in_rag ? 'Used for retrieval' : 'Excluded from retrieval'}</p><p>Source lines {message.line_start}–{message.line_end} · record {message.source_order + 1} · {message.timezone}</p>{encoded && <p>Original payload retained locally for audit; hidden from history and search.</p>}</details>
        </li>;})}</ol>
        {next !== null && <button className="secondary full" disabled={busy} onClick={more}>Load more messages</button>}
      </>}
      {busy && <p role="status">Loading messages…</p>}
      {error && <div role="alert"><p className="error">{error}</p><button className="secondary" onClick={() => setRetry(n => n + 1)}>Retry messages</button></div>}
    </>}
  </section>;
}
