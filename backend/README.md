# ReplyCue local backend

FastAPI and Python standard-library `sqlite3`. **No separate SQLite installation or database server is needed.** Requires Python 3.11+.

## Windows PowerShell (VS Code terminal 1)

```powershell
cd D:\research\project\ReplyCue\backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The environment is already prepared here; only the last command is needed. Activation is optional. If `py` has no interpreter, install Python 3.11+ or create the environment using the available bundled interpreter:

```powershell
& 'C:\Users\20350\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
```

Health: http://127.0.0.1:8000/health. API docs: http://127.0.0.1:8000/docs.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use synthetic in-memory ZIPs and temporary databases only.

## API

- `GET /health`: database/provider status.
- `GET /conversations`: IDs, display names and optional `normalized_phone` for explicit reimport selection. Identical display names do not merge contacts; the frontend keeps IDs out of labels.
- Summaries also include UTC first/last timestamps, total/RAG message counts, chunk/embedding counts and latest import time/status.
- `GET /conversations/{conversation_id}`: summary plus confirmed participant aliases/roles, counts by type, total import count, latest 50 audits and embedding provider/dimension/count metadata. No vector values. Legacy parsed/skipped counts and warnings remain null when unknown; transcript filenames are not retained or exposed by the audit view.
- `GET /conversations/{conversation_id}/messages`: `offset` (default 0), `limit` (1–200, default 50), `order` (`asc`/`desc`), optional `type`, `rag` boolean and literal substring `q` (max 200). Returns `items`, `total`, `next_offset`, offset and limit. Original Unicode text, aliases/roles (nullable for senderless events), source order/lines and local/UTC timestamps are included; fingerprints and vectors are excluded. Unknown conversation is 404 and invalid queries are 422. Chronological ordering uses UTC time, source order and ID; undated records come first ascending. Pages are deterministic for unchanged data; refresh pagination after a concurrent import.
- `POST /imports/preview`: multipart `file` ZIP and optional `transcript_name`. Returns aliases, record/type counts, local timestamp range, warnings, and transcript hash; no message bodies and no saved rows.
- `POST /imports/confirm`: multipart `file`, `transcript_name`, preview `transcript_hash`, `display_name`, `self_alias`, `contact_alias`, `timezone`, optional existing `conversation_id` and optional `phone`. Phone numbers are explicitly user-provided, never inferred from filenames or aliases. Spaces, parentheses, dots and hyphens are removed; 3–15 digits and an optional leading + are accepted without guessing a country. A supplied number updates the selected contact transactionally; omitted/blank phone preserves an existing number. Two-alias direct chats only. Select an existing conversation to deduplicate a full export.
- `POST /retrieve`: JSON `contact_id`, `conversation_id`, `query`, optional `top_k` (1–20). Returns scoped chunk text/scores and source message IDs, line ranges and import IDs.

This is a single-user local API without account authentication. Keep it bound to loopback; CORS allows only localhost/127.0.0.1 on port 5173, and other Origin headers are rejected. Do not expose it to a LAN/public host without deployment authentication and security.

## Archive and parsing behavior

Limits: 10 MB ZIP, 30 MB expanded total, 100 entries, 100:1 per-entry expansion, 5 MB transcript, 11 MB entire request before multipart processing. Encrypted, duplicate, traversal and symlink paths are rejected. Only the selected transcript is read in memory; nothing is extracted. Markdown/media are ignored. ZIP bytes/temporary upload handles are discarded after each request.

UTF-8 with optional BOM; `[M/D/YY, h:mm:ss AM/PM] Alias: body` and multiline continuations. Two-digit years mean 2000–2099. Confirm the preview date range and export timezone (IANA name or fixed offset); filenames never establish identity. Nonexistent daylight-saving timestamps fail validation; ambiguous timestamps use the earlier occurrence with a warning.

Original Unicode/emoji/ZWJ text is preserved separately from NFC/whitespace-normalized search text. Existing replacement characters are warned about, not repaired; invalid UTF-8 is rejected. Emoji sequence extraction is omitted rather than splitting graphemes unreliably.

## SQLite, deduplication, and retrieval

Runtime database: `backend/data/replycue.sqlite3` (Git-ignored); override with `REPLYCUE_DB_PATH`. This is private plaintext local storage. Stop the backend before deleting its data directory to reset it. Never publish this database.

Idempotent schema version 1 includes contacts, conversations, imports, participant aliases, messages, chunks, chunk/source-message links and embeddings with foreign keys and scope/time indexes. Every import is a single transaction, including chunk/vector creation; failure rolls back all partial work.

Schema version 2 adds an `import_details` table for future parsed/skipped counts and warnings and indexes for chronological/type/RAG pages. Existing message and import rows are preserved. History reads project only public API fields, execute parameterized scoped queries and retrieve bounded pages; literal substring searches may scan the selected conversation in SQLite. Import audit dates are returned with explicit UTC `Z`.

Schema version 3 applies idempotent transactional encoded-media cleanup on startup. Detection accepts complete standard Base64 or Base64 data URIs, with whitespace normalized, a 256-character minimum and 5 MB source cap. Strict decoding and JPEG/PNG/GIF/WebP, WAV/FLAC/ID3, AVI/selected MP4, PDF or ZIP signatures are required; these are file-signature checks, not full file validation. Ordinary text, URLs, code and short tokens are not classified merely by character set. Recognized records use `encoded_image`, `encoded_audio`, `encoded_video`, `encoded_document` or `encoded_binary`, with empty normalized text and no RAG eligibility.

Original payloads remain only in local `messages.original_text` for audit. History pages return a safe placeholder and `encoded: true`; text search excludes these records. There is no raw-payload endpoint. Cleanup preserves message IDs/fingerprints and import audits, rebuilds chunks/embeddings only for affected conversations, and rolls back fully if rebuilding fails. Reimports retain the former text fingerprint convention to avoid duplicating cleaned-up messages. Future startup passes cover records imported by an older app version. The frontend also guards known encoded payloads from legacy API responses; no vector values or raw payloads are displayed.

Stable IDs combine conversation, alias/timestamp/type/normalized-content fingerprint and occurrence index. Full-history reimports skip known occurrences while retaining identical same-second messages. Partial exports missing indistinguishable duplicates cannot reliably identify those occurrences; prefer full exports. Source lines refer to the message's initial import.

Only substantive text enters chunks. Omitted voice/image/video/audio/sticker/document/GIF, calls, deleted tombstones, system and unknown placeholders remain metadata (`include_in_rag=0`). Chronological chunks contain at most 12 segments/1,800 characters with six-hour gap boundaries. Long text splits into source-linked segments. Only the updated conversation's chunks are rebuilt, atomically.

`DevelopmentEmbedding` uses deterministic 128-dimensional lexical feature hashing and cosine ranking, **not semantic AI**. The provider protocol can be replaced later; vectors record provider/dimensions and retrieval filters to the active provider. A provider change requires reindexing. No keys or external model calls are used.
