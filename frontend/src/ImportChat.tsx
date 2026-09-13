import { useEffect, useRef, useState } from 'react';
import { Check, FileText, Upload, X } from 'lucide-react';
import { api, type Conversation, type Preview, type SavedImport } from './api';
import { contactLabel, formatTimestamp } from './format';

export default function ImportChat({ onImported }: { onImported: (name: string) => void }) {
  const picker = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [saved, setSaved] = useState<SavedImport | null>(null);
  const [contact, setContact] = useState('');
  const [phone, setPhone] = useState('');
  const [selfAlias, setSelfAlias] = useState('');
  const [otherAlias, setOtherAlias] = useState('');
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [conversationId, setConversationId] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [health, setHealth] = useState<'checking' | 'ok' | 'offline'>('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);

  async function checkBackend() {
    setHealth('checking');
    try {
      await api('/health');
      setConversations(await api<Conversation[]>('/conversations'));
      setHealth('ok');
    } catch { setHealth('offline'); }
  }
  useEffect(() => { void checkBackend(); }, []);

  function choose(selected?: File) {
    if (!selected || busy) return;
    setPreview(null); setSaved(null); setFile(null); setSelfAlias(''); setOtherAlias(''); setError('');
    if (!selected.name.toLowerCase().endsWith('.zip') || selected.size > 10 * 1024 * 1024) {
      setError('Choose a WhatsApp export ZIP no larger than 10 MB.'); return;
    }
    setFile(selected);
  }
  function form() {
    const result = new FormData();
    if (file) result.append('file', file);
    return result;
  }
  async function previewFile() {
    if (!file) return;
    setBusy(true); setError(''); setSaved(null);
    try { setPreview(await api<Preview>('/imports/preview', { method: 'POST', body: form() })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function confirmImport() {
    if (!file || !preview) return;
    setBusy(true); setError(''); setSaved(null);
    const body = form();
    for (const [key, value] of Object.entries({ display_name: contact, self_alias: selfAlias,
      contact_alias: otherAlias, phone, timezone, transcript_name: preview.transcript_name,
      transcript_hash: preview.transcript_hash })) body.append(key, value);
    if (conversationId) body.append('conversation_id', conversationId);
    try {
      const result = await api<SavedImport>('/imports/confirm', { method: 'POST', body });
      setSaved(result); setConversationId(result.conversation_id); setPhone(result.normalized_phone || ''); onImported(contactLabel(result));
      await checkBackend();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section aria-labelledby="import-title">
    <h2 id="import-title">Bring the context with you</h2>
    <p className="intro">Choose a WhatsApp export ZIP, preferably <strong>without media</strong>. Preview its structure, then confirm whose chat to save.</p>
    <div className={`backend-status ${health}`} role="status">
      <span>{health === 'ok' ? 'Local backend connected' : health === 'checking' ? 'Checking local backend…' : 'Backend unavailable. Start it in a second terminal.'}</span>
      <button className="text-button" disabled={busy || health === 'checking'} onClick={checkBackend}>Retry connection</button>
    </div>
    <input ref={picker} type="file" accept=".zip,application/zip" className="file-input" aria-label="Choose chat ZIP file" disabled={busy} onChange={e => choose(e.target.files?.[0])}/>
    <div className={`drop-area ${dragging ? 'dragging' : ''}`} onDragOver={e => {e.preventDefault();if (!busy) setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={e => {e.preventDefault();setDragging(false);choose(e.dataTransfer.files[0]);}}>
      <Upload size={27}/><strong>Drop your chat export here</strong><span>.zip only · up to 10 MB</span>
      <button className="secondary" disabled={busy} onClick={() => picker.current?.click()}>Choose ZIP</button>
    </div>
    {file && <><div className="file-summary"><FileText size={21}/><div><strong>{file.name}</strong><small>{(file.size/1024).toFixed(1)} KB</small></div><button className="icon" disabled={busy} aria-label="Remove selected file" onClick={() => {setFile(null);setPreview(null);setSaved(null);setError('');if (picker.current) picker.current.value='';}}><X size={18}/></button></div>
      <button className="secondary full" disabled={busy || health !== 'ok'} onClick={previewFile}>{busy ? 'Working…' : 'Preview ZIP'}</button></>}
    {error && <p className="error" role="alert">{error}</p>}
    {preview && <><div className="preview"><h3>Import preview</h3><p>{preview.transcript_name} · {preview.record_count} records</p><div><small>Detected aliases</small><span>{preview.aliases.join(' · ') || 'No sender aliases found'}</span></div><div><small>Export dates · {timezone || 'Choose a timezone'}</small><span>{formatTimestamp(preview.first_timestamp, { wallClock: true })} — {formatTimestamp(preview.last_timestamp, { wallClock: true })}</span></div><div><small>Record types</small><span>{Object.entries(preview.type_counts).map(([type,count]) => `${type}: ${count}`).join(' · ')}</span></div></div>
      <ul className="warnings">{preview.warnings.map(w => <li key={w}>{w}</li>)}</ul>
      {preview.aliases.length !== 2 && <p className="error">This version supports exactly two sender aliases. Group chats cannot be imported yet.</p>}
      <label htmlFor="conversation">Save into</label><select id="conversation" disabled={busy} value={conversationId} onChange={e => {setConversationId(e.target.value);setSaved(null);const existing=conversations.find(c => c.id===e.target.value);if(existing){setContact(existing.display_name);setPhone(existing.normalized_phone || '');setTimezone(existing.timezone);}else{setContact('');setPhone('');}}}><option value="">New contact and conversation</option>{conversations.map(c => <option key={c.id} value={c.id}>{contactLabel(c)} · {c.message_count} records</option>)}</select>
      <label htmlFor="contact">Contact display name</label><input id="contact" value={contact} disabled={busy || !!conversationId} maxLength={120} onChange={e => setContact(e.target.value)} placeholder="A name you recognize"/>
      <label htmlFor="phone">Phone number (optional)</label><input id="phone" type="tel" autoComplete="off" value={phone} disabled={busy} maxLength={100} onChange={e => setPhone(e.target.value)} placeholder="+country code and number"/><p className="field-hint">Enter and confirm the number yourself; it is never taken from the ZIP filename. Leaving it blank keeps an existing saved number.</p>
      <label htmlFor="self-alias">Which alias is me?</label><select id="self-alias" disabled={busy} value={selfAlias} onChange={e => setSelfAlias(e.target.value)}><option value="">Select your alias</option>{preview.aliases.map(a => <option key={a}>{a}</option>)}</select>
      <label htmlFor="other-alias">Which alias is the contact?</label><select id="other-alias" disabled={busy} value={otherAlias} onChange={e => setOtherAlias(e.target.value)}><option value="">Select the contact alias</option>{preview.aliases.map(a => <option key={a} disabled={a===selfAlias}>{a}</option>)}</select>
      <label htmlFor="timezone">Export timezone</label><input id="timezone" disabled={busy || !!conversationId} value={timezone} onChange={e => setTimezone(e.target.value)} placeholder="Europe/Berlin or +02:00"/><p className="field-hint">Confirm where the export timestamps were recorded. A name or ZIP filename never establishes identity.</p>
      <button className="primary full" disabled={busy || health !== 'ok' || !contact.trim() || !selfAlias || !otherAlias || selfAlias===otherAlias || !timezone.trim() || preview.aliases.length!==2} onClick={confirmImport}><Check size={18}/>{busy ? 'Saving…' : 'Confirm import / update'}</button>
    </>}
    {saved && <div className="success" role="status"><strong>Chat saved locally</strong><p>{saved.added_messages} added · {saved.duplicate_messages} duplicates skipped</p><p>{saved.chunk_count} text chunks · {saved.embedding_count} development embeddings</p><small>Development lexical search, not semantic AI. Reply suggestions remain sample data.</small>{saved.warnings.filter(w => !preview?.warnings.includes(w)).map(w => <p key={w}>{w}</p>)}</div>}
    <p className="footnote">ZIP bytes go only to your configured backend and are discarded after each request. Confirmed text is stored in local SQLite.</p>
  </section>;
}
