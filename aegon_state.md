# Aegon — Current State

*Read this first, every session. The one resume file. Keep it tiny. Update after every completed step.*
*Full history: `aegon_roadmap.md` (read in slices). Map: `aegon_file_index.md`. Design: `aegon_architecture.md`. Flags: `flags.md`.*

---

## Destination

Building Aegon — the new JARVIS. A present, anticipatory partner that monitors, surfaces, and acts with Sir's approval. Not a tool that waits to be used.

Measured against the JARVIS Behavioral Contract: anticipatory, persistent context, invisible infrastructure, judgment, total environment awareness.

---

## Phase Status

**Phases 0–5** ✅ Complete and verified.
**Phase 6.0 (Obsidian)** — built, pending full bidirectional verification (F.7).
**Phase F (Foundation Completion)** — Complete (F.4 deferred/on hold).
**Phase A (JARVIS Layer)** — ✅ Complete (A2 on hold — hardware/UX decision pending).
**Phase B (Deep JARVIS)** — In progress. B1 ✅ B2 ✅ done. B3 rolled back (2026-07-23) — pending redesign. B5 🟡 in progress (first increment built + mocked-tested, live verification pending). B4 deferred (hardware).

**Environment rebuild (2026-08-07)** — machine reset wiped `.venv` and all env vars. Stack rebuilt and re-verified live; STT/TTS/LLM providers all changed (see below).

---

## Environment Rebuild — 2026-08-07 (post machine reset)

Machine reset deleted `.venv` (partially — `Scripts/` gone, stale `site-packages` remained) and **all user env vars**. Rebuilt and verified live.

**Provider swaps (all three, Sir's call):**
- **STT**: local faster-whisper large-v3 → **NVIDIA-hosted whisper-large-v3** (Riva gRPC, `NVIDIA_STT_API_KEY`). `faster-whisper` + `ctranslate2` removed; the torch/ctranslate2 CUDA DLL-path workaround in `aegon_voice.py` deleted with them. silero-vad stays local. **Raw microphone audio now leaves the machine** — new exposure, was fully local before.
- **TTS**: Gemini (Charon) → **NVIDIA Chatterbox-Multilingual** (Riva gRPC, `NVIDIA_TTS_API_KEY`). Same model family that failed locally in June — hosted, so the 4GB-VRAM objection no longer applies. Returns LINEAR_PCM 22050 Hz; existing pyaudio playback path unchanged. `google-genai` removed.
- **LLM**: Groq (llama-3.3-70b) → **OpenRouter** `nvidia/nemotron-3-super-120b-a12b:free` (`OPENROUTER_API_KEY`). Plain REST, no SDK; rate-limit detection is now HTTP 429 instead of Groq's SDK exception. Ollama fallback unchanged. `groq` removed.

**Measured latency (2026-08-07, 3 runs each, median):** STT 0.32s · LLM 1.35s · TTS 1.33s → **~3.0s/turn**. NVIDIA NIM direct was benchmarked as an LLM alternative and is **not** faster (1.38s vs 1.35s — same model, statistically identical); provider swap is not a latency lever. Real lever is streaming (LLM first-sentence → `synthesize_online`), unbuilt.

**Other repairs:**
- `requirements.txt` **created** — none existed before. Reconstructed via AST parse of real imports. Two blind spots found and fixed after: `psycopg2-binary` (codebase mixes psycopg v2 and v3), and `mcp-server-time` (subprocess-spawned, never imported).
- `mcp` pinned `<2.0` — mcp 2.0 renamed `McpError`→`MCPError`, breaking `mcp-server-time` (still broken at its latest, 2026.7.10). Unpin when upstream fixes.
- Stale paths fixed after project move `Desktop\aegon` → `Desktop\AI Projects\aegon`: `file_paths.py` (vault + workspace), `github_search_tool.py`, `discover_github_tools.py`. `tests/resave_model.py` left stale — run-once throwaway.
- Postgres rebuilt: `pgvector/pgvector:pg16`, container `AEGON_MEMORY`, volume `aegon_pg_data`. Schema recreated via `db_init.py`.
- **Data loss (accepted):** `AEGON_TOKEN_KEY` / `AEGON_ENCRYPTION_KEY` were never backed up despite `apps/backup_keys.py` existing for exactly that. 17 encrypted session logs + `gmail.token` + `spotify.token` became permanently unreadable; deleted by Sir for a clean start. New keys generated. **Gmail and Spotify need re-auth on next use.** Back the new keys up.
- Dead packages from the pre-reset venv removed: `chatterbox-tts`, `diffusers`, `accelerate`.

**Verified live:** Postgres ✅ · STT ✅ · TTS ✅ (spoken) · OpenRouter LLM ✅ · vault sync ✅ · clock ✅ (MCP bridge working after `mcp<2.0` pin) · text orchestrator ✅.

**Full-system manual test — PAUSED 2026-08-07 at Section 7.** Script + run log: `TEST_SCRIPT.md` (15 sections, Google tools excluded pending Gmail re-auth). Sections 1–5 pass; Section 6 partial. **Resume at Section 7 (gated tools / Axiom 1)** — it is the most security-relevant section and also regression-tests two fixes that are still unverified live: the `approval_handler` rejection message (needs a "no" to a gated action) and `speak.py` chunking/markdown-stripping (needs a long spoken response). Mid-test fixes landed: identity/capabilities, LLM chain, weather geocoding, TTS chunking. New flags raised: F37–F41.

**Not yet done:** `tests/test_groq.py` and `tests/test_aegon_voice.py` are both stale — the first tests a removed provider, the second mocks the Gemini Live API removed back in F.1. Neither cleaned up.

---

## Done & Verified (Phases 0–6)

- Full LangGraph orchestrator with A2A protocol, governance, decision logger, PostgreSQL checkpointer
- Memory: six forms, pgvector, fact extraction (Sir-turns only, F16 gate confirmed), contradiction detection, behavioral delta detection
- Three sub-agents: memory_agent, summarizer_agent, planner_agent
- Six operating modes (standard, focus, research, morning, night, deep_work)
- Connector framework: BaseConnector, MCPConnector, tool_registry, tool_logger, file_paths
- Connectors built and verified: web_search, file_read, file_write, gmail_read, gmail_send, calendar_read, clock, weather, news, github_search, spotify suite (search/play/playlist/playlists/control), obsidian suite (search/read/create/append)
- Reminders: reminder_set (Google Calendar, durable), timer_set (in-memory, ephemeral), reminder_watcher daemon
- `core/voice/speak.py` — single TTS mouth for all spoken output
- Morning mode runner + morning_trigger.py
- Approval flow: approval_handler.py, pending_approval / requires_approval fields
- F21 governance override: `_own_data_intents` covers memory_query + summarize_request + plan_request (6/6 tests pass)
- F22 clock tool: schema-echo backstop, IP timezone, natural phrasing
- Obsidian skill: vault at `aegon/vault/`. Four connectors built. OBSIDIAN_VAULT constant in file_paths.py.
- Closed flags: F2, F11, F12, F14, F15, F16 (code), F18, F21 (full), F24, F25
- `apps/backup_keys.py` — key backup script
- TTS (2026-06-19): local Chatterbox/Orpheus trialed and **reverted** — 4GB RTX 3050 can't co-host faster-whisper large-v3 + a local TTS model (VRAM exhaustion → 1.5 s/it). Back to **Gemini TTS** (Charon, cloud, `GEMINI_API_KEY` env). torch left on cu124 build (harmless). `speak.py` is the single mouth with `_speak_lock`. Local TTS deferred to Phase C2 / better GPU. Quota risk: free-tier Gemini = 10 req/day (see flag).
- Vault privacy — identity-only sync (2026-06-20): `vault_sync.py` no longer stores note BODY into memory. `_note_to_fact` rewritten + new `_extract_purpose` — default sync stores title + optional frontmatter `purpose:` line only; body never read into a fact. Content persisted ONLY when Sir explicitly says "remember the content of note X" (Part 2 — DONE). 4/4 pass (`test_vault_privacy.py`). Sir's rule: title/purpose OK to remember, content readable on demand but not stored without explicit instruction.
- Vault privacy Part 2 — explicit note-content remember (2026-06-20): new `note_remember` intent. `schemas/intent_schema.py` + classifier prompt (by meaning) + `graph.py` route → `memory_agent`. `memory_agent._handle_note_remember()`: extracts note title (LLM), reads via `ObsidianReadConnector`, stores body as `project` fact `source="explicit"`, capped 2000 chars, dedup-aware. No approval gate (Sir asked; own note). Added to `_NON_EXTRACTABLE_INTENTS`. Tests: `test_note_remember.py` (5, mocked). **Live verified:** "remember the content of note Welcome" → stored → re-ask deduped → "what is the content" recalled it. Closes the vault-privacy loop: default sync = identity-only, this = the one deliberate content path.
- Bug 3 — morning briefing text fallback (2026-06-20): `morning_briefing.py` `deliver_briefing()` spoke only via `speak()` — invisible in text mode and when TTS down. Added `print(f"Aegon (briefing): {text}")` before `speak()`. One-line change; signature unchanged.
- Bug 2 — A4 challenge gate misfire (2026-06-20): `response_synthesizer.py` challenge gate fired on read-only tool turns (obsidian_search etc.) because all `task` intents qualified. Added `used_tool = state.get("tool_result") is not None` guard — challenge now skips any turn where a tool ran (read-only retrievals have nothing to confirm; gated actions already pass the approval gate). Brain-only task/plan turns still challenged. 14/14 pass (`test_a4.py`, +1 new).
- Two-drawer memory: personal vs reference (2026-06-21): Sir's rule — note content saved via "remember the content of note X" is REFERENCE for future use, not a fact about Sir. Vault-sourced facts now tagged `source="vault"` (`vault_sync` + `memory_agent._handle_note_remember`). `memory_agent._handle_read`: broad personal-summary queries ("what do you know about me"/"who am i" — `_is_personal_summary`) return personal facts only, excluding `source=="vault"`; specific topic queries use `search_facts` which INCLUDES reference (so saved notes are retrievable on direct ask). `context_injector._retrieve_relevant` excludes `source=="vault"` from ambient injection (casual chat stays clean). `MEMORY_AGENT_PROMPT` rule 8: never mention the vault/note titles/storage. Part 2 stays alive (it's the reference drawer). Tests: `test_memory_recall.py` (7), `test_note_remember.py` (5), `test_context_relevance.py` (5) — 17/17.
- Relevance-gated context injection (2026-06-21): replaced the "dump all facts every turn" with per-turn semantic retrieval. `context_injector.build_memory_context(query)` + `build_session_context(query)` now call `search_facts(query, top_k=8)` and keep only facts ≥ 0.35 similarity — a greeting pulls nothing (fixes the stale-fact leak into casual chat). `_retrieve_relevant()` helper added. Memory recall decoupled: `memory_agent._handle_read` general path now self-retrieves via `get_all_active_facts()` (broad recall stays intact despite narrow injection — Bug B protected). `aegon_orchestrator` passes `transcribed_text` as the query. Tests: `test_context_relevance.py` (5), `test_memory_recall.py` updated (5), `test_a3.py` TestBuildSessionContext updated to mock `search_facts`. Sir's rule: relevant context every turn is necessary; the whole history for "hello" is not. Scaling note: general recall still loads all facts — cap when the store grows large.
- Bug A — clock connector (2026-06-21): two faults. (1) `mcp_connector.py` spawned bare `"python"` → resolved to system Python (no MCP packages); now resolves `"python"`/`"python3"` to `sys.executable` so MCP stdio servers launch in the venv. (2) `mcp-server-time` installed into the venv. (3) routing: "what time is it" reclassified as live-data TASK → `clock` (intent rule 14 + orchestrator rule 9 add time→clock); was wrongly answered brain-only. Verified: `ClockConnector().execute({})` → real time; `test_what_time_is_it` now TASK.
- Bug B — "what do you know about me" recalled nothing (2026-06-21): `_detect_form` mapped general phrases "about me"/"who am i" to the `user_profile` FORM, so the lookup searched only that form and dead-ended when facts lived under `habit`/`project`. Removed those phrases from `FORM_KEYWORDS`; added empty-form fallback in `_handle_read` (detected-but-empty form → general semantic recall instead of "nothing stored under X"). 5/5 pass (`test_memory_recall.py`).
- Bug 1 — weather/calendar routing (2026-06-20): two faults fixed. **1a:** intent classifier taught weather/news/schedule are live-data TASKS not conversation (rule 14 + counter-example for general knowledge); orchestrator prompt now points weather→`weather`, schedule→`calendar_read`, news→`news` instead of `web_search`. **1b — multi-tool per turn:** orchestrator may emit `tool_calls` array; `A2AMessage.tool_calls` field added; `orchestrator_node` validates/coerces the batch (≥2 known tools else collapses to single); `tool_node` Branch 1b runs each non-gated tool sequentially and joins answers — gated tools in a batch are NEVER auto-run (Axiom 1), flagged for separate approval. Single-tool path untouched. Tests: 4/4 (`test_bug1_multi_tool.py`) + 25/25 (`test_intent_routing_f2.py`). Live verified: "weather and my schedule" → both connectors in one reply.
- Memory delete hardening (2026-06-20): three root causes fixed — (1) delete commands stored as facts (extraction gate: `_NON_EXTRACTABLE_INTENTS` in orchestrator + EXTRACTION_PROMPT rule); (2) delete searched top_k=1 only (now top_k=10, all above threshold parked); (3) similarity threshold too high (0.6 → 0.40). New `memory_delete` intent added to schema, classifier, graph router, memory_agent — classified by meaning. `approval_handler.py` loops all parked fact_ids on "yes". TTS reverted Algenib→Charon. 13/13 tests pass. Live end-to-end verified.

---

## Current Work — Phase F (Foundation Completion)

**Rule: all nine Phase F gates must pass before Phase A begins. No exceptions.**

Complete in this exact order:

### Step 1 — F.1: STT Replacement ✅ DONE (2026-06-12)
`apps/voice/aegon_voice.py` replaced: sounddevice stream → silero-vad VADIterator (end-of-speech, 700ms silence) → faster-whisper large-v3 on CUDA float16 (loaded once at startup, ctranslate2 backend, nvidia wheel DLLs prepended to PATH) → session_logger callback (interface unchanged). `session_logger.py` MERGE_WINDOW_SECONDS 6.0 → 1.5. No Gemini Live / pyaudio anywhere. Gate passed — Sir confirmed live test. Note: requires Docker PostgreSQL running, else startup hangs silently (flag F24).

### Step 2 — F.2: Punctuation-Independent Routing ✅ DONE (2026-06-12)
Rule 14 added to `prompts/intent_classifier_prompt.py`: classify by semantic meaning only, punctuation irrelevant. 10 unpunctuated voice examples added. Gate: 20/20 tests passed (`tests/test_intent_routing_f2.py`).

### Step 3 — F.3: Three-Layer Governance ✅ DONE (2026-06-12)
`governance_node.py` rewritten: Layer 1 structural (own-data intents incl. `conversation`, no tool → pass, no LLM), Layer 2 patterns (axiom 3 capitulation + axiom 6 injection → block, no LLM; clean approved actions pass), Layer 3 LLM for ambiguous only, axiom_2 backstop kept. Gates: F21 6/6 + `tests/test_f3_governance_layers.py` 10/10 (LLM-not-called asserted).

### Step 4 — F.4: Memory Encryption at Rest ❌ OPEN
**Action**: enable full-disk encryption on drive containing Docker PostgreSQL data (Option B — faster)
**Gate**: store encrypted; all memory operations confirmed working post-encryption; both keys backed up

### Step 5 — F.5: Verify F16 Under Real Conditions ✅ DONE (2026-06-12)
Live test `tests/test_f5_live_extraction.py` passed all delta blocks. Root fixes: (1) `fact_extractor.py` Sir-turns-only (was ingesting Aegon replies — echo + external-content leak); (2) `drain_extraction_threads()` added to orchestrator for deterministic timing; (3) per-run nonce in test fixture to defeat dedup masking. Pre-fix DB pollution deferred as flag F25.

[x] 5 tool turns produce zero extracted facts — delta=0 confirmed
[x] 5 memory_query turns produce zero extracted facts — delta=0 confirmed
[x] 5 Sir-statement turns produce correctly scoped facts — delta>0 confirmed
[x] Buffer clears between turns — per-block isolation confirmed
[x] 20-turn mixed session: fact count matches only Sir-statement turns
[x] No external content in Tier-3 — new extractions clean; pre-fix residue cleaned 2026-06-18 (F25 resolved)

### Step 6 — F.6: Wire Morning Briefing ✅ DONE (2026-06-13)
`core/modes/morning_briefing.py` built: `build_briefing()` → sentinel slot (skipped until Phase A1) + calendar (CalendarReadConnector) + active tasks (get_facts_by_form("project"), capped at 5). Opens with "Sir, here is your briefing." Empty sections silently omitted. `start_briefing_async()` daemon thread wired to `start()` in orchestrator and `__main__` in voice app. Both check `_active_mode == "morning"` at session start. Gate passed — Sir confirmed live.
Success criteria:

[ ] Morning briefing fires automatically at session start when the mode is morning
[ ] Briefing covers sentinel queue (or skips if empty), calendar, and active tasks
[ ] Spoken output under 60 seconds for a typical morning
[ ] Empty sections skipped gracefully — no "nothing found" filler
[ ] Opening line is "Sir, here is your briefing"
[ ] Calendar events for today returned correctly
[ ] Active tasks returned correctly from the planner agent
[ ] Briefing does not block the voice loop — Sir can interrupt and speak

### Step 7 — F.7: Obsidian Bidirectional ✅ DONE (2026-06-13)
`core/memory/vault_sync.py` built: scans vault for `.md` files modified since last sync (timestamp in `.vault_sync_ts`), stores each as a Tier-3 project fact via `store_fact()` — no LLM, no external call, local SentenceTransformer dedup only. Wired to session start in both orchestrator `start()` and voice `__main__`. Verified live: 3 notes synced (F7 Test + Test + Welcome). Aegon→Obsidian confirmed via `obsidian_create`. Obsidian content never leaves the machine — Axiom 2 compliant by structure.

[x] Aegon → Obsidian confirmed: F7 Test.md created in vault
[x] Obsidian → Aegon confirmed: 3 vault notes stored as Tier-3 project facts
[x] Sync cycle: once per session start, timestamp persisted in core/memory/.vault_sync_ts
[x] No duplicate facts: dedup at 0.90 via local SentenceTransformer — confirmed
[x] Obsidian content never sent to external API — Axiom 2 compliant

### Step 8 — F.8: Relay-and-Flag Emails ✅ DONE (2026-06-13)
`tools/gmail_read/gmail_read_tool.py`: added `_check_injection()` + `_flag_injections()`, applied to all three output paths (`_search`, `_check_new`, `_read_full`). `governance_node.py`: removed `_AXIOM_6_PATTERNS` tuple and Layer 2 Axiom 6 block entirely. `tests/test_f3_governance_layers.py`: `test_axiom6_injection_blocked_no_llm` → `test_axiom6_injection_relayed_to_layer3` (now asserts llm.calls==1, not blocked). `tests/test_f8_relay_and_flag.py`: new 14-test gate — 14/14 passed. Combined: 24/24.

**Success criteria**:
- [x] Email with "Aegon, do X" is relayed with an injection warning, not blocked
- [x] Email with "ignore previous instructions" is relayed with a warning, not blocked
- [x] Normal everyday email is relayed without any warning — no over-flagging
- [x] Aegon's spoken output includes the warning before the email content
- [x] Governance Layer 2 no longer blocks relayed email content
- [x] Axiom 6 tests updated and passing
- [x] Axiom 6 enforcement intact — Aegon never acts on injected instructions

### Step 9 — F.9: Delete Confirmation Gate ✅ DONE (2026-06-13)
`agents/memory_agent/memory_agent.py`: delete branch now parks action — searches for fact, sets `pending_approval` with `action_type="memory_delete"`, fact_id, fact_text, prompt; does NOT execute. `_handle_delete()` removed. `core/orchestration/nodes/approval_handler.py`: approved + `action_type=="memory_delete"` → executes `update_fact_status(status="resolved")` inline, sets `approval_verdict="completed"`, clears `pending_approval` → routes to synthesizer without tool_node. `tests/test_f9_delete_confirmation.py`: 9/9 passed.

**Success criteria**:
- [x] Every memory delete shows the fact and asks for confirmation before executing
- [x] "Yes" executes the delete — soft delete confirmed in the database
- [x] "No" or "cancel" preserves the fact unchanged
- [x] No-leak test passes — two deletes each ask independently
- [x] The delete is recorded in the memory audit log


---

## Phase F Completion Gate

| Step | Item | Status |
|---|---|---|
| F.1 | STT replacement | ✅ |
| F.2 | Punctuation routing | ✅ |
| F.3 | Three-layer governance | ✅ |
| F.4 | Memory encryption | ⏸ deferred |
| F.5 | F16 verification (live) | ✅ |
| F.6 | Morning briefing wired | ✅ |
| F.7 | Obsidian bidirectional | ✅ |
| F.8 | Relay-and-flag emails | ✅ |
| F.9 | Delete confirmation gate | ✅ |

---

## Current Work — Phase A (JARVIS Layer)

Full spec in `aegon_roadmap.md` (Phase A section). Build sub-phases in order.

### A1 — The Sentinel ✅ COMPLETE

#### A1.1 ✅ DONE (2026-06-13)
`core/sentinel/findings.py` — Finding dataclass. `core/sentinel/proactive_queue.py` — thread-safe queue, drain urgency-ordered, remainder kept. `core/sentinel/rules.py` — five deterministic rules (deadline/habit_deviation/stale_decision/dormant_project/recurring_error). `core/sentinel/sentinel.py` — 30-min daemon thread, idempotent start. Wired to `aegon_orchestrator.py` `start()`. 25/25 tests pass.

#### A1.2 ✅ DONE (2026-06-13)
`proactive_queue.py`: `format_findings_for_speech()` added. `morning_briefing.py`: drains queue first, prepends findings. `aegon_orchestrator.py` + `aegon_voice.py`: sentinel starts at session start; non-morning drains and speaks; morning handled by briefing. 30/30 tests pass.

#### A1.3 ✅ DONE (2026-06-13)
`sentinel.py`: `on_fact_stored()` spawns background thread → `run_all_rules()` → `_dispatch()`; `_dispatch()` routes immediate findings to `_surface_immediate()` (speak now) and session_start findings to proactive queue. `_check_calendar_approaching()` polls Google Calendar API every 5 min, surfaces events within 15 min via `_surface_immediate()`, deduped by `_surfaced_event_ids`. `_calendar_poll_loop()` daemon thread started in `start()`. `fact_extractor.py`: calls `sentinel.on_fact_stored()` after each stored fact. 36/36 tests pass.

#### A1.4 ✅ DONE (2026-06-13)
`core/feedback/feedback_store.py`: `log_finding()` logs every surfaced immediate finding (UUID, type, content, urgency, surfaced_at); `record_response()` writes "useful"/"not_relevant" verdict; `get_hit_rate()` returns (rate, count) over N days; `should_suppress()` demotes types below 30% with ≥5 samples; `get_weekly_report()` returns spoken summary. `sentinel.py`: `_surface_immediate()` calls `log_finding()`, stores ID in `_last_surfaced_id`; `_dispatch()` filters suppressed types; `get_last_surfaced_id()` exposed. `schemas/intent_schema.py`: `FINDING_FEEDBACK` added. `prompts/intent_classifier_prompt.py`: `finding_feedback` intent + rule 15 + examples. `graph.py`: `feedback_node` added — reads raw input, calls `record_response()`, routes directly to synthesizer. 17/17 tests pass.

**A2** ⏸ ON HOLD — Voice auth (`core/security/voice_auth.py`) + access control + `apps/enroll_owner.py` — deferred, hardware/UX decision pending
**A3** ✅ DONE (2026-06-13) — `context_injector.py`: `build_session_context()` added (pure formatting, no LLM — projects, decisions, emotional signals, inferences → paragraph injected into every Groq call). `core/memory/inference_engine.py`: weekly LLM pass over non-inference facts, stores conclusions as `form="inference"`, `source="inference_engine"`, timestamp-gated. Both wired to session start in orchestrator. 19/19 tests pass. Live behavioral gates deferred — see A3-OBS-1, A3-OBS-2 in `flags.md`.
**A4** ✅ DONE (2026-06-13) — `_challenge_check()` added to `response_synthesizer.py`: semantic search over top-5 memory facts, LLM conflict detection, one-sentence gate ending "Still confirm?", fires only for `task`/`plan_request` intents when governance passes. Multi-sentence and missing-keyword responses rejected. `challenge_fired` logged in decision_log. 13/13 tests pass (`tests/test_a4.py`).
**A5** ✅ DONE (2026-06-13) — `core/modes/mode_detector.py` built: `infer_mode_from_context()` checks time (06–09→morning, 22–04→night), then calendar (event within 30min→focus), then last-hour memory facts (coding signals→deep_work, research signals→research), then standard. `get_recent_facts(minutes)` added to `memory_store.py`. Wired silently to session start in orchestrator `start()` and voice app `__main__`. Manual switches via `mode_switch_node` still announce themselves. 18/18 tests pass (`tests/test_a5.py`).
**A6** ✅ DONE (2026-06-13) — `apps/weekly_review.py` built: four terminal sections (memory health, sentinel performance, session summary, interactive quality check). `get_memory_health_stats()` added to `memory_store.py`. `get_session_stats(days)` added to `decision_logger.py`. Quality check: y=keep, n=soft-delete, c=correct+store. 12/12 tests pass (`tests/test_a6.py`). Run: `python -m apps.weekly_review`.

---

---

## Current Work — Phase B (Deep JARVIS)

**B1 — Domain Understanding Layer** ✅ DONE (2026-06-13)
`core/memory/project_model_store.py`: CRUD for `project_models` table (name UNIQUE, domain, current_state, next_decision, blockers, confidence, last_updated). `core/memory/project_model_updater.py`: keyword-gate → LLM extraction → `upsert_project_model()`; spawned as daemon thread post-turn in orchestrator. `core/sentinel/rules.py`: `rule_stale_blocker()` added — fires medium-urgency finding when a project has blockers unchanged ≥7 days; `run_all_rules()` updated to call it. `agents/planner_agent/planner_agent.py`: review/prioritize modes now prepend project model summaries before memory context. `apps/weekly_review.py`: `stale_blocker` added to sentinel hit-rate report. `core/memory/db_init.py`: `project_models` table added. 23/23 tests pass (`tests/test_b1.py`).

**B2 — Proactive Intelligence Upgrade** ✅ DONE (2026-06-13)
`core/sentinel/rules.py`: `rule_topic_frequency(recent_facts, project_models)` added — low-urgency finding when a word appears in 3+ recent facts with no matching project model. `run_all_rules()` updated: each rule now guarded by `should_suppress()` (skip if hit-rate < 0.30 with ≥5 samples); fetches 7-day recent facts; calls `rule_topic_frequency`. `core/sentinel/sentinel.py`: `_check_deep_work_gap()` added — fires low-urgency `session_start` finding when a 2h+ gap exists today between 09:00–17:00; deduped per calendar day; called from `_calendar_poll_loop()`. `apps/weekly_review.py`: `topic_frequency` and `deep_work_gap` added to sentinel hit-rate report. 16/16 tests pass (`tests/test_b2.py`).

**B3 — Screen and System Awareness** ⏸ ROLLED BACK (2026-07-23)
Built 2026-06-13, then fully removed 2026-07-23 pending redesign. Live testing exposed two problems: (1) the IDE classifier missed common apps (WebStorm and other JetBrains IDEs weren't in the regex — silent blind spot, no error); (2) the design cached a 5-minute-stale category/title for mode inference, but there was no live "what app am I in right now" path — the two needs (slow-moving mode signal vs. an honest real-time answer) were conflated in one cache. Removed entirely: `core/awareness/` (`app_monitor.py`, `screen_monitor.py`), `tests/test_b3.py`, and all call sites (`context_injector.py`, `mode_detector.py`, `aegon_orchestrator.py` ×2, `aegon_voice.py`). No references remain (verified via grep). Full prior file content is recoverable from session history if needed. Redesign should separate the two concerns before rebuilding: a live-query path for direct questions, and (if still wanted) a slow-poll signal for mode inference only — not one cache serving both.

**B4 — Continuous Presence** — deferred (hardware required)

**B5 — Working Memory as a Referent Store** 🟡 **IN PROGRESS** — raised 2026-08-07 during full-system testing. `orchestrator_node` cannot resolve referents ("weather **there**" after "time in Tunisia" → returned Montreal) because the memory-to-tool firewall deliberately starves it of context. Affects every tool ("that repo", "that note", "them"). All three obvious fixes rejected as Axiom 2 / injection risks — see `aegon_roadmap.md` Phase B5 for the rejected options and why. Design: replace the transcript-vs-firewall binary with a **typed, provenance-tagged referent store** (the brain's working memory holds bound referents, not a transcript; disclosure is gated by source monitoring, not starvation). Orchestrator receives the referent set, never the transcript; policy gates by provenance so `memory`-sourced referents structurally cannot reach a tool query.

**First increment — done (mocked), 2026-08-17**: Steps 1+2+5 of 6, `tool_result` provenance only (Step 3 sir_utterance extraction and Step 4 full policy layer deliberately deferred). `core/orchestration/referent_store.py` — new file, bounded (4 slots, 30-min TTL) per-session store, `latest()` provenance-gated to `("tool_result",)` by default. `prompts/orchestrator_prompt.py` rule 11 — the *existing* orchestrator LLM call (same trust boundary, no new call, no widened firewall) may emit an optional `referents` array using Sir's own words, never a converted form (e.g. "Tunisia" not "Africa/Tunis" — found and fixed a representation-mismatch gap in the original roadmap plan before building). `orchestrator_node.py` — stores referents only once a valid tool manifest is confirmed; resolves bare backreference words in `tool_input` against the store before the tool call goes out; leaves the word unresolved when nothing matches (no regression). `tests/test_f33_referent_store.py`: 11/11 pass (mocked LLM, mocked registry).

**Live-verified 2026-08-17**: "what time is it in tunisia" → "what's the weather there" correctly resolved to Tunisia (previously fell back to Montreal/IP). Flagship bug closed. Surfaced a separate pre-existing bug in the process — `weather_tool.py` geocoding a country-level name duplicated it ("Tunisia, Tunisia"); fixed same day (`dict.fromkeys()` dedup in `_geocode()`), re-verified live.

**Not yet done**: "that repo"/"that note"/"them" untested live. `sir_utterance` provenance (Step 3), full provenance policy layer (Step 4) not built — only `tool_result` provenance exists today.

---

## Open Flags Summary

See `flags.md` for full detail. Live open items:

| ID | Description | Severity | Blocks |
|---|---|---|---|
| F33 🟡 | Orchestrator can't resolve referents ("weather **there**") — flagship case fixed + live-verified; "that repo"/"that note"/"them" + fuller provenance policy still open | Medium | **Phase B5 — in progress** |
| F40 | `what are my playlists` returns a non-answer — misreads its own tool output | Medium | Open |
| F41 | Persistent hedging ("you may want to verify...") against the persona | Low–Medium | Open |
| F36 | Ollama fallback non-functional (cloud model, 401) — chain has no local floor | Medium | Open |
| F34 | "what do you know about X" dead-ends for non-personal topics | Medium | After Phase B5 (Sir's call) |
| F35 | No provenance marking (memory vs knowledge vs web) | Medium | Open |
| F.4 | Memory not encrypted at rest | Medium | Deferred — on hold |
| F5 | Poisoned-memory residual | Low (real) | Phase C2 |
| F6 | MCP client re-spawns per call | Medium | Phase B |
| F10 | House security + sleep mode | Deferred | Hardware needed |
| F27 | Raw voice audio leaves the machine (NVIDIA STT) | Medium (accepted) | Phase C2 |
| F28 | Key backup discipline failed — caused real data loss | Medium | Open |
| F29 | Two test files test removed systems | Low | Open |
| F30 | `requirements.txt` unpinned — rebuild not reproducible | Medium | Open |
| F31 | `mcp` pinned <2.0 for one lagging subprocess | Low | Open |
| A3-OBS-1 | A3 fact reference — live observation pending | Low | Phase A3 |
| A3-OBS-2 | A3 inference accuracy — live observation pending | Low | Phase A3 |

---

## Accepted Tradeoffs (active)

- OpenRouter sends text off-machine, and NVIDIA Riva receives raw voice audio (STT) + spoken output (TTS) — resolves Phase C2
- Session model (not continuous presence) — resolves Phase B4 when dedicated hardware available
- Axiom 3 behavioral only — resolves Phase C2 (Agent-C)
- Governance non-determinism mitigated by three-layer structure — Layer 3 for ambiguous only
- Spotify OS-launch Windows-only (`spotify:` URIs only, always-gated, Axiom 4 approved)
- timer_set `enabled:true` — Axiom 4 audit pending Sir's call
