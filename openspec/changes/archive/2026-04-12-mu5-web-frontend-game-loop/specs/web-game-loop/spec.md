# Web Game Loop

## Purpose

Specifies the SSE-driven adventure execution UI: the `gameSession` Svelte store, the `fetchSSE` async generator, and all decision-point components. This capability is the core interaction loop — it wires the MU3 SSE adventure API into the SvelteKit frontend so players can read narrative, make decisions, and progress through adventures in the browser.

---

## Requirements

### Requirement: `gameSession` store manages SSE stream lifecycle

`frontend/src/lib/stores/gameSession.ts` SHALL export a `gameSession` store created with `writable` (not Svelte 5 runes) so it is consumable from `.ts` modules and `+layout.ts` files. The store SHALL maintain `GameSessionState` with fields: `mode`, `narrativeLog`, `pendingEvent`, `completeEvent`, `overworldState`, and `error`.

The store SHALL expose: `init(playState)`, `begin(characterId, adventureRef)`, `advance(characterId, decision)`, and `close()`. Only one SSE stream SHALL be active at a time. When `begin` or `advance` is called while a stream is active, the previous stream's generator SHALL be orphaned (its events discarded) and the new generator SHALL take over.

#### Scenario: begin opens a stream and transitions to loading

- **GIVEN** `gameSession.mode` is `"overworld"`
- **WHEN** `gameSession.begin(characterId, "api-sse-events")` is called
- **THEN** `mode` is immediately set to `"loading"` before the first event arrives
- **AND** `pendingEvent` is cleared to `null`

#### Scenario: narrative events accumulate in the log

- **GIVEN** a stream is active
- **WHEN** three `type: "narrative"` events arrive
- **THEN** `narrativeLog.length` equals 3, each entry has a unique `id` string and a `text` field

#### Scenario: decision event sets pendingEvent and mode

- **GIVEN** a stream emits a `type: "choice"` event
- **WHEN** the store processes it
- **THEN** `mode` is set to `"adventure"`, `pendingEvent.type` is `"choice"`, and `narrativeLog` is unchanged

#### Scenario: adventure_complete transitions to complete mode

- **GIVEN** a stream emits `type: "adventure_complete"`
- **WHEN** the store processes it
- **THEN** `mode` is `"complete"`, `completeEvent` holds the event, `pendingEvent` is unchanged

#### Scenario: stream error transitions to overworld mode

- **GIVEN** a stream emits `type: "error"`
- **WHEN** the store processes it
- **THEN** `mode` is `"overworld"`, `state.error` is set to the event's `message`

---

### Requirement: `fetchSSE` uses `fetch` + `ReadableStream` for POST SSE

`frontend/src/lib/api/play.ts` SHALL export `fetchSSE(url: string, body: object): AsyncGenerator<SSEEvent>` that opens the SSE stream via `fetch` (not `EventSource`, which is GET-only). The function SHALL read the access token from `get(authStore).accessToken`, inject `Authorization: Bearer <token>` when present, POST the body as JSON, and parse the response body as a `ReadableStream` using `parseSSEBuffer`. It SHALL throw `ApiError("Session conflict", 409, "session_conflict")` when the response status is 409 before reading any stream data. It SHALL throw `ApiError` for any other non-2xx status.

#### Scenario: 409 throws before stream is consumed

- **GIVEN** `POST /characters/{id}/play/begin` returns HTTP 409
- **WHEN** `fetchSSE` is awaited (first `next()` call)
- **THEN** an `ApiError` with `status === 409` is thrown
- **AND** no attempt is made to read `response.body`

#### Scenario: parseSSEBuffer splits correctly across chunk boundaries

- **GIVEN** `buffer` is `"event: choice\ndata: {\"a\":1}\n\nevent: narrative\ndata: {\"text\":\"hi\"}"`
- **WHEN** `parseSSEBuffer(buffer)` is called
- **THEN** `events.length` is 1 (first complete block only; second block has no trailing `\n\n`)
- **AND** `remaining` equals `"event: narrative\ndata: {\"text\":\"hi\"}"`

---

### Requirement: Decision components use Svelte 5 callback props

All decision components (`ChoiceMenu`, `AckPrompt`, `CombatHUD`, `TextInputForm`, `SkillMenu`) SHALL declare props via `let { event, on<Action> } = $props()` (Svelte 5 syntax) and call the callback directly. They SHALL NOT use `createEventDispatcher` or `on:eventname`. Each component SHALL disable its interactive elements while a decision is being submitted (to prevent double-submission).

#### Scenario: ChoiceMenu maps number keys 1–9 to choices

- **GIVEN** `ChoiceMenu` is mounted with 3 options
- **WHEN** the user presses the `"2"` key
- **THEN** `onSelect(2)` is called (1-based index matching backend `AdvanceRequest.choice`)
- **AND** the buttons are disabled until the next stream event arrives

#### Scenario: AckPrompt responds to Enter and Space

- **GIVEN** `AckPrompt` is mounted
- **WHEN** the user presses `Enter`
- **THEN** `onAck()` is called once
- **AND** subsequent keypresses are ignored until the button re-enables

---

### Requirement: NarrativeLog fades in new entries without layout shift

`NarrativeLog.svelte` SHALL render each `NarrativeEntry` with a CSS `opacity: 0 → 1` transition (300ms). The animation SHALL apply only `opacity` — no `height`, `margin`, or `padding` animation — so the scroll container height is stable and no layout shift occurs. The container SHALL auto-scroll to the bottom when new entries are added, unless the player has manually scrolled up. A "Scroll to bottom" button SHALL appear when `scrollTop + clientHeight < scrollHeight - threshold`.

#### Scenario: new entry does not shift existing text

- **GIVEN** 5 narrative entries are rendered and the user has read them
- **WHEN** a 6th entry is appended
- **THEN** the first 5 entries do not move (scroll position is maintained or auto-scrolled)
- **AND** the 6th entry fades in from `opacity: 0`
