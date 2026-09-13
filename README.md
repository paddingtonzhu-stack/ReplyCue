# ReplyCue

Remember where you left off and find the words to reply like yourself.

The standalone React interface has Reply and Import chat tabs. Import connects to local FastAPI and SQLite; Reply suggestions and insertion remain sample/demo features.

## Run in two VS Code PowerShell terminals

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

## Reply and retrieval

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
