# ReplyCue Product Report

## 1. Executive summary

ReplyCue is a private relationship-memory and communication assistant for dating and personal conversations. It helps a user re-enter a conversation after time has passed, remember who the other person is and where the relationship stood, decide what they want to communicate, and prepare a reply that sounds like the user rather than generic AI text.

The product is an assistant, not an autonomous messenger. It may recall context, explain uncertainty, suggest alternatives, and place an approved draft into the messaging field. The user remains responsible for editing and sending every message.

The initial product is a personal learning project rather than a commercial service. This allows the first version to prioritize a coherent experience and demonstrate message ingestion, relationship memory, personalized reply generation, privacy-aware design, and integration with a messaging interface.

## 2. The user problem

Dating and personal conversations often restart after days or weeks. When someone returns, the user may have forgotten:

- who the person is and how they met;
- facts the person previously shared;
- plans, promises, boundaries, or shared jokes;
- how the previous conversation ended;
- the current stage or nature of the connection; and
- how the user normally communicates with that person.

Reading a long chat history is inconvenient, particularly when the user wants to reply immediately. A generic AI writer can change tone, but it lacks the relationship context and the user's authentic writing habits. ReplyCue addresses both problems.

## 3. Product promise

> ReplyCue remembers your connections and helps you reply like yourself.

The experience should help the user answer three questions:

1. Who is this person, and what has happened between us?
2. What do I want to communicate now?
3. How would I naturally say it?

## 4. Target use case

The primary use case is dating and early personal relationships, especially when a conversation restarts after a gap or when an incoming message is socially delicate or ambiguous.

Example scenario:

1. A person sends a message after one month of silence.
2. The user opens ReplyCue beside the conversation.
3. ReplyCue shows a concise, evidence-based recap of the person and relationship.
4. The user chooses their present intention, such as reconnecting, moving slowly, clarifying, declining, or setting a boundary.
5. ReplyCue offers several replies grounded in relevant history and written in the user's style.
6. The user approves and optionally edits one suggestion.
7. ReplyCue inserts the draft into the normal message field.
8. The user reviews and sends it themselves.

## 5. Confirmed product functions

### Function 1: Relationship Memory Card

The Relationship Memory Card provides a concise and editable recap so the user does not need to reread the entire conversation.

#### A. What I know

Factual details explicitly supported by messages or confirmed by the user, such as:

- name, work, studies, or location;
- interests and preferences;
- important events or personal details;
- plans already discussed; and
- boundaries or facts worth remembering.

#### B. How they communicate

Careful observations about visible communication behavior, such as:

- short or detailed messages;
- frequent or infrequent initiation;
- humor or directness;
- whether they ask personal questions; and
- whether they prefer concrete plans.

These observations must not be presented as personality diagnoses.

#### C. Our connection

A summary of the shared relationship context, including:

- how the people met;
- how long they have communicated;
- whether they have met in person;
- shared plans or unresolved topics;
- the last meaningful interaction;
- who typically initiates; and
- the apparent stage of the connection, with uncertainty shown when appropriate.

#### Evidence and uncertainty

The card must distinguish among:

- confirmed by the user;
- explicitly found in messages;
- tentative observation; and
- unknown or unsupported.

Every generated detail should be traceable to its supporting message. When the history is too limited, ReplyCue should say so instead of inventing a portrait.

#### User control

The user can add, edit, confirm, reject, or delete details. User-confirmed corrections should not be silently overwritten by later automated updates.

#### Living memory

The card evolves as the conversation continues. It shows when it was last updated. New imports add only unseen messages and should not duplicate old messages.

Stable facts should change rarely. Recent topics, active plans, and the current status of the connection may update more frequently. Old information may be marked as no longer current instead of being silently removed.

### Function 2: Context-Aware Reply Suggestions

ReplyCue generates replies using five inputs:

1. the current incoming message;
2. relevant excerpts from the shared history;
3. the Relationship Memory Card;
4. the user's present communication intention; and
5. examples of the user's natural writing style.

It should retrieve only context relevant to the present message rather than send or summarize the entire conversation every time.

#### Intention before tone

ReplyCue should first establish what the user wants. Possible intentions include:

- reconnect;
- show interest;
- move slowly;
- stay friendly;
- clarify meaning;
- decline politely;
- set a boundary; or
- remain uncertain and ask a question.

Tone is a secondary choice, such as warm, playful, direct, calm, confident, neutral, professional, funny, or flirty.

#### Reply directions

The product should offer meaningfully different options rather than minor rewrites of one sentence. A useful default is:

- safe and natural;
- warmer or more playful; and
- more direct or forward-moving.

#### Personal voice

ReplyCue learns from the user's own sent messages, including:

- typical message length;
- vocabulary and phrasing;
- punctuation and capitalization;
- emoji frequency;
- humor and directness; and
- whether the user sends one message or several short messages.

The user may request shorter, warmer, less polished, or “more like me” alternatives. User edits and rejected suggestions provide valuable feedback about authentic style.

Suggestions must remain editable and should avoid polished phrases the user would never naturally use.

### Function 3: One-Click Reply Insertion

After reviewing a suggestion, the user presses a clear action such as **Use this reply**. ReplyCue inserts the approved text directly into the normal WhatsApp message field.

Requirements:

- no copy-and-paste step in the preferred experience;
- the user can edit the suggestion before or after insertion;
- existing text is never overwritten without confirmation;
- copying remains available as a fallback; and
- ReplyCue never sends a message automatically.

The final Send action always belongs to the user.

## 6. Message import and updating

### Reliable baseline: Export to ReplyCue

The supported initial flow is:

1. The user opens a specific WhatsApp conversation.
2. The user selects Export Chat and excludes media by default.
3. The user chooses ReplyCue from the phone's share menu, or uploads the exported file to a web version.
4. ReplyCue previews what will be imported.
5. The user confirms the person and grants access.
6. ReplyCue processes the conversation and creates or updates the Memory Card.

On subsequent exports, ReplyCue detects messages already stored, ignores duplicates, and imports only new material.

### Desired future flow: Authorized synchronization

Automatic synchronization remains an open investigation. It must not be assumed until a supported interface for personal conversations is verified.

The official WhatsApp business interfaces should not be treated as a guaranteed way to retrieve a consumer user's private chat history. A browser-based integration may be able to work with currently visible WhatsApp Web content, but it can be incomplete and sensitive to interface changes.

The product must remain useful with manual refresh even if live synchronization is unavailable.

## 7. Privacy, safety, and trust principles

Dating conversations may contain intimate information about people who did not install ReplyCue. Privacy is therefore a core product behavior.

ReplyCue should:

- import only conversations explicitly selected by the user;
- preview data before import;
- exclude media by default;
- collect and retain the minimum necessary data;
- encrypt messages in storage and in transit;
- keep encryption secrets separate from stored content;
- send only the minimum relevant context to an external model;
- provide simple per-person and complete deletion;
- never train shared models on private conversations;
- clearly show which history influenced a suggestion; and
- keep message sending under explicit human control.

Encryption alone is insufficient because information must be readable while it is processed. Data minimization, access control, deletion, and transparent use are equally important.

ReplyCue must avoid unsupported or manipulative functions such as:

- personality or mental-health diagnosis;
- compatibility or attractiveness scores;
- lie detection;
- confident claims about another person's motives;
- strategies intended to create dependency or manipulate emotion; and
- autonomous sending.

When interpreting a message, ReplyCue may offer multiple plausible readings but must label them as possibilities rather than facts.

## 8. Known product risks and fallbacks

### Stale conversation history

**Risk:** An exported conversation becomes outdated.

**Fallback:** Show “updated through” status and provide Refresh from Chat. Import only unseen messages.

### Limited history

**Risk:** There may not be enough evidence to describe the person, relationship, or user voice.

**Fallback:** Show unknowns, request optional user input, and avoid strong conclusions.

### Unclear user intention

**Risk:** History cannot determine what the user wants now.

**Fallback:** Ask the user to choose or describe their intention before generating sensitive replies.

### Mobile and desktop discontinuity

**Risk:** Export may begin on a phone, while insertion may be easiest on WhatsApp Web.

**Fallback:** Provide a clear import handoff and make manual copy available on every surface.

### Fragile WhatsApp integration

**Risk:** Interface-dependent insertion or reading may break when WhatsApp changes.

**Fallback:** Preserve manual import, editing, and copying as reliable paths.

### Incorrect or harmful inference

**Risk:** A misleading summary may affect a real relationship.

**Fallback:** Cite sources, express uncertainty, accept corrections, and separate observation from interpretation.

### Generic AI voice

**Risk:** Replies sound polished but unlike the user.

**Fallback:** Learn from the user's sent messages and edits; support “more like me” and deliberately casual output.

## 9. Recommended product phases

### Phase 1: Core personal prototype

- Import one exported text conversation.
- Parse participants and messages.
- Generate an editable Relationship Memory Card.
- Let the user enter the current incoming message.
- Let the user choose an intention and tone.
- Generate three reply directions.
- Let the user edit and copy a reply.
- Show which memories supported the result.
- Store data locally with deletion controls.

### Phase 2: Living memory and personal voice

- Re-import and add only new messages.
- Display last-updated status.
- Protect user-confirmed facts.
- Build an editable personal voice profile.
- Learn preferences from accepted and edited suggestions.
- Improve relevant-history selection.

### Phase 3: Messaging experience

- Add a small popover or side panel beside WhatsApp Web.
- Show the Memory Card on demand.
- Generate replies without leaving the conversation.
- Insert an approved suggestion into the message composer.
- Preserve copy and manual-entry fallbacks.

### Phase 4: Investigate smoother synchronization

- Verify whether an authorized message interface is available and appropriate.
- Evaluate mobile share integration.
- Explore safe incremental synchronization without making it a requirement.
- Document platform constraints and failure behavior.

## 10. Success criteria for the personal project

ReplyCue succeeds when it can demonstrate that:

- the user can import a conversation intentionally and understand what was stored;
- the Memory Card is useful, editable, sourced, and honest about uncertainty;
- retrieved history is relevant to the incoming message;
- replies reflect both the user's intention and their actual writing habits;
- the user remains comfortable editing or rejecting every suggestion;
- no message is sent without explicit user action;
- the system continues working when synchronization or insertion is unavailable; and
- private data can be inspected and deleted easily.

## 11. Final product definition

ReplyCue is a private assistant for remembering personal connections and responding with confidence. It converts an explicitly imported conversation into a living, evidence-based Relationship Memory Card. When a new message arrives, it recalls only the relevant history, asks what the user wants to communicate, and proposes several replies in the user's authentic voice. After the user approves a draft, ReplyCue can place it into the WhatsApp message field, but the user always edits and sends it themselves.

The product's distinctive value is the combination of relationship memory, personal voice, uncertainty-aware assistance, and human control.
