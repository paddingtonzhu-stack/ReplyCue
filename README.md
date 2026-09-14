# ReplyCue

Remember where you left off and find the words to reply like yourself.

The standalone React interface has Reply, Import chat and Conversations tabs. Import and Conversations connect to local FastAPI and SQLite; Reply suggestions and insertion remain sample/demo features.

## Run in two VS Code PowerShell terminals

After installing the dependencies below, restart both servers from the project root in a VS Code PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart-dev.ps1
```

To stop them only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart-dev.ps1 -StopOnly
```

The script verifies checkout ownership before stopping processes, including stale Vite servers. It refuses to stop an unrelated or unverifiable listener on ports 8000/5173; stop such a server in its original terminal first. It installs nothing and leaves chat data intact. Startup waits up to 30 seconds per server (`-TimeoutSeconds 60` to extend). Logs are in ignored `.dev-runtime/`. Fixed ports match the local API's origin restrictions.

Requires Node.js 20.19+ or 22.12+ and Python 3.11+. **No SQLite installation or server is needed**: Python includes sqlite3.

Terminal 1 — backend:

```powershell
cd D:\research\project\ReplyCue\backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The virtual environment is already prepared on this machine; only the last command is needed. If py has no interpreter, see the bundled Python fallback in [backend instructions](backend/README.md).

Terminal 2 — frontend:

```powershell
cd D:\research\project\ReplyCue\frontend
npm install
npm run dev -- --port 5173 --strictPort
```

Frontend: http://127.0.0.1:5173. Backend health: http://127.0.0.1:8000/health. API documentation: http://127.0.0.1:8000/docs.

Copy frontend/.env.example to frontend/.env to change VITE_API_BASE_URL (default http://127.0.0.1:8000), then restart Vite. These values are public client configuration, never secrets.

## Import a chat

1. Select/drop a WhatsApp export ZIP without media, then Preview ZIP.
2. Review aliases, record types/counts, date range and warnings. Preview saves nothing and returns no message bodies.
3. Enter a contact name and optional phone number, explicitly choose your alias and the contact alias, and confirm the export timezone. Dates display in a readable local form; preview wall-clock times stay in the selected export timezone.
4. Confirm to save Unicode messages, timeline metadata, text chunks and development vectors locally.
5. For full-history reimports, select the existing contact label to skip known records. Labels show the name and phone when provided, never internal IDs. A matching display name never merges contacts automatically.
6. The result reports added/skipped messages and chunk/embedding counts. Backend failures expose a retry path.

Only two-alias direct chats in the supported timestamp format are accepted. ZIPs are bounded, read without extraction and discarded after requests. No private exports are part of this project.

## Browse saved conversations

Open **Conversations**, select a saved name, and read the chronological timeline. Names use an explicitly saved phone when available, with date/count metadata to distinguish conversations. Search saved text or filter by message type; **Load more messages** fetches the next 50 records. Tab switching keeps the current selection and pages. **Refresh** reloads saved information, and successful imports refresh the view automatically.

Expand **Conversation and import information** for confirmed aliases, timezone, record/type counts, retrieval eligibility, chunk/embedding counts and the latest 50 import audit summaries. Expand a message's **Parsing details** for source lines and classification. Original multiline text and emojis are preserved; media omissions, calls, deleted messages and system records are labelled as events. Vectors and internal fingerprints are never sent to this view.

Old databases upgrade automatically with additive tables/indexes; no SQLite installation is required. Older imports show unknown parsed/skipped counts and unavailable warnings because those fields were not originally saved. The database remains local and Git-ignored. Reply suggestions still use the separate sample history.

Recognized long Base64 files and Base64 data URIs are shown as compact **Encoded image/audio/video/document/binary omitted** events. Strict decoding plus known file signatures prevents ordinary long text or short tokens from being treated as media. Original payload text stays in local SQLite for audit, but is excluded from search, chunks, embeddings and normal message API responses. Startup cleanup also reclassifies older matching text records and rebuilds only affected conversations transactionally; it does not delete the original text or import audits.

Read APIs (also available in the local `/docs`):

- `GET /conversations`: saved summaries, dates, counts and latest import status.
- `GET /conversations/{conversation_id}`: aliases, type/retrieval counts, embedding metadata and recent import audits.
- `GET /conversations/{conversation_id}/messages?offset=0&limit=50`: original message page; optional `order=asc|desc`, `type`, `rag=true|false`, and literal substring `q` (up to 200 characters). Limit is at most 200. Unknown conversations return 404; invalid filters return 422. IDs are API routing values, not display labels.

Pages use deterministic time/source-order/ID ordering, with undated events first in ascending order. Offset pages reflect current storage; refresh from the first page after imports in another window to avoid shifts. Substring search scans matching conversation text in SQLite; only the requested page is loaded into Python. Counts cover metadata records as well as substantive messages.

## Reply and retrieval behavior

Reply retains fictional sample memory, intentions, regeneration, editing, copy and persistent insertion confirmation. Imports do not yet generate replies or replace the sample memory card. Insert reply neither sends nor inserts into WhatsApp.

POST /retrieve searches by explicit contact and conversation IDs and returns source-linked chunks. The deterministic feature-hash vectors are a lexical development substitute, not semantic AI. No keys or external model calls are used.

## Validate

```powershell
cd D:\research\project\ReplyCue\backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

Tests create synthetic ZIPs and temporary databases only. The frontend build includes TypeScript validation. Use npm's lockfile; do not mix pnpm into its node_modules.

## Structure and local data

- frontend/src/ImportChat.tsx and api.ts: two-step import client.
- frontend/src/main.tsx and demoService.ts: standalone UI and sample reply behavior.
- backend/app/parser.py: bounded ZIP/transcript parsing and record classification.
- backend/app/storage.py: sqlite3 schema, transactional deduplication, chunks and scoped retrieval.
- backend/app/embeddings.py: swappable interface and deterministic development provider.
- backend/app/main.py: FastAPI endpoints, structured errors and local-origin restrictions.
- backend/tests/: synthetic safety/import/retrieval tests.
- PRODUCT_REPORT.md: product plan.

Runtime SQLite files live under ignored backend/data and contain private plaintext chat data: do not publish them. Keep the single-user unauthenticated API bound to 127.0.0.1. See [backend details](backend/README.md) for limits, schema, timezone behavior and deduplication constraints.
