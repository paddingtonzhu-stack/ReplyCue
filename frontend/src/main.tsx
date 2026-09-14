import React, { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Leaf,
  ChevronDown,
  RefreshCw,
  Users,
  CalendarDays,
  MoreHorizontal,
  Copy,
  Check,
  ArrowUpRight,
  Upload,
  FileText,
  X,
} from "lucide-react";
import {
  generateReplies,
  initialReplies,
  memories,
  type Intention,
} from "./demoService";
import "./styles.css";
import ImportChat from "./ImportChat";
import History from "./History";

// Import processing is isolated from the sample reply UI.

function App() {
  const tabs = ['reply', 'import', 'history'] as const;
  const [tab, setTab] = useState<typeof tabs[number]>("reply");
  const [historyRevision, setHistoryRevision] = useState(0);
  const [memory, setMemory] = useState(false),
    [more, setMore] = useState(false);
  const [intention, setIntention] = useState<Intention>("Reconnect");
  const [suggestions, setSuggestions] = useState(initialReplies),
    [draft, setDraft] = useState(initialReplies[0]);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [inserted, setInserted] = useState<string | null>(null);
  const [imported, setImported] = useState("");
  const revision = useRef(0);
  async function generate(next: Intention, refresh = false) {
    setIntention(next);
    setMore(false);
    setBusy(true);
    try {
      const list = await generateReplies(
        next,
        refresh ? ++revision.current : 0,
      );
      setSuggestions(list);
      setDraft(list[0]);
      setNotice(refresh ? "Another set of sample replies." : "");
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(draft);
      setNotice("Draft copied.");
    } catch {
      setNotice(
        "Select the draft text and copy it manually. Clipboard access is unavailable.",
      );
    }
  }
  function switchTab(next: typeof tabs[number]) {
    setTab(next);
  }
  return (
    <main className="page">
      <div className="workspace">
        <header className="brand">
          <div>
            <Leaf size={30} />
            <h1>ReplyCue</h1>
          </div>
          <span className="badge">Test space</span>
        </header>
        <div className="tabs" role="tablist" aria-label="ReplyCue tools">
          {tabs.map((value) => (
            <button
              key={value}
              id={`${value}-tab`}
              role="tab"
              aria-selected={tab === value}
              aria-controls={`${value}-panel`}
              tabIndex={tab === value ? 0 : -1}
              onClick={() => switchTab(value)}
              onKeyDown={(e) => {
                if (
                  ["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)
                ) {
                  e.preventDefault();
                  const next = e.key === 'Home' ? tabs[0] : e.key === 'End' ? tabs[2]
                    : tabs[(tabs.indexOf(tab) + (e.key === 'ArrowRight' ? 1 : 2)) % tabs.length];
                  switchTab(next);
                  document.getElementById(`${next}-tab`)?.focus();
                }
              }}
            >
              {value === "reply" ? "Reply" : value === 'import' ? "Import chat" : 'Conversations'}
            </button>
          ))}
        </div>
        <div
          className="content"
          id="reply-panel"
          role="tabpanel"
          aria-labelledby="reply-tab"
          hidden={tab !== "reply"}
        >
          <div className="context-heading">
            <span className="avatar">M</span>
            <div>
              <strong>Maya</strong>
              <small>Sample conversation</small>
            </div>
          </div>
          <p className="incoming">
            “Hey! It’s been a while. How have you been?”
          </p>
          <button
            className="memory-toggle"
            aria-expanded={memory}
            onClick={() => setMemory(!memory)}
          >
            <Leaf size={18} />
            <span>Coffee plans left open</span>
            <small>Memory</small>
            <ChevronDown size={17} />
          </button>
          {memory && (
            <div className="memory">
              <p className="muted">From the sample history</p>
              {memories.map((m) => (
                <details key={m.fact}>
                  <summary>{m.fact}</summary>
                  <p>{m.source}</p>
                </details>
              ))}
            </div>
          )}
          {imported && (
            <p className="import-note">
              Saved contact: {imported}. Replies still use Maya’s sample
              history.
            </p>
          )}
          <h2>What would you like to do?</h2>
          <div className="intentions">
            <button
              disabled={busy}
              aria-pressed={intention === "Reconnect"}
              onClick={() => generate("Reconnect")}
            >
              <Users size={16} />
              Reconnect
            </button>
            <button
              disabled={busy}
              aria-pressed={intention === "Make plans"}
              onClick={() => generate("Make plans")}
            >
              <CalendarDays size={16} />
              Make plans
            </button>
            <button
              disabled={busy}
              aria-expanded={more}
              aria-pressed={["Keep it friendly", "Set a boundary"].includes(
                intention,
              )}
              onClick={() => setMore(!more)}
            >
              <MoreHorizontal size={18} />
              More
            </button>
          </div>
          {more && (
            <div className="more-options">
              {(["Keep it friendly", "Set a boundary"] as Intention[]).map(
                (v) => (
                  <button
                    className="secondary"
                    key={v}
                    onClick={() => generate(v)}
                  >
                    {v}
                  </button>
                ),
              )}
            </div>
          )}
          <div className="section-heading">
            <h2>Reply ideas</h2>
            <button
              className={"icon " + (busy ? "spinning" : "")}
              aria-label="Regenerate sample replies"
              disabled={busy}
              onClick={() => generate(intention, true)}
            >
              <RefreshCw size={18} />
            </button>
          </div>
          <div
            className="suggestions"
            aria-label="Reply suggestions"
            aria-busy={busy}
          >
            {suggestions.map((s) => (
              <button
                key={s}
                aria-pressed={draft === s}
                disabled={busy}
                onClick={() => setDraft(s)}
              >
                <span className="radio">
                  {draft === s && <Check size={11} />}
                </span>
                {s}
              </button>
            ))}
          </div>
          <label htmlFor="draft">Edit draft</label>
          <textarea
            id="draft"
            rows={3}
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="actions">
            <button
              className="primary"
              disabled={busy || !draft.trim()}
              onClick={() => setInserted(draft)}
            >
              <ArrowUpRight size={19} />
              {inserted === null ? "Insert reply" : "Insert reply again"}
            </button>
            <button
              className="secondary copy"
              aria-label="Copy draft"
              disabled={busy || !draft.trim()}
              onClick={copy}
            >
              <Copy size={18} />
            </button>
          </div>
          {inserted !== null && (
            <div className="success" role="status">
              <strong>
                <Check size={16} />
                Draft inserted · demo
              </strong>
              <p>
                {inserted === draft
                  ? "Your draft is still here to edit or insert again."
                  : "You have edited the draft. Insert again to update the demo."}
              </p>
              <small>
                Placeholder only. Nothing was sent or inserted into WhatsApp.
              </small>
            </div>
          )}
          <p className="notice" role="status">
            {notice}
          </p>
          <p className="footnote">Sample replies · You review and send.</p>
        </div>
        <div
          className="content"
          id="import-panel"
          role="tabpanel"
          aria-labelledby="import-tab"
          hidden={tab !== "import"}
        >
          <ImportChat onImported={name => {setImported(name);setHistoryRevision(n => n + 1);}} />
        </div>
        <div className="content" id="history-panel" role="tabpanel" aria-labelledby="history-tab" hidden={tab !== 'history'}>
          <History revision={historyRevision} active={tab === 'history'}/>
        </div>
      </div>
      <p className="page-note">A little context. Your own words.</p>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
