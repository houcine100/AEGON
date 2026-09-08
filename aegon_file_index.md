# Aegon File Index

*Read this instead of scanning the project. One line per file = its job. Update it when files are added or a file's role changes. Excludes `.venv`, `__pycache__`, and empty `__init__.py` package markers.*

---

## Entry points (`apps/`)
- `apps/orchestrator/aegon_orchestrator.py` — sole text entry point. Drains `proactive_queue` first, then voice_queue. Runs the graph. Speaks the reply. **This is what Sir runs to test.**
- `apps/voice/aegon_voice.py` — voice capture only. NVIDIA-hosted whisper-large-v3 (Riva gRPC, `NVIDIA_STT_API_KEY`) + local silero-vad. 1.5s merge window. No text logic. Audio leaves the machine for transcription (2026-08-07 change).
- `apps/enroll_owner.py` — **[Phase A2 — to build]** one-time voice enrollment for Sir. Records 5 samples, saves voiceprint to `core/security/sir_voiceprint.npy`.
- `apps/morning_trigger.py` — triggers morning mode runner manually.
- `apps/backup_keys.py` — backs up both encryption keys (`AEGON_TOKEN_KEY` + `AEGON_ENCRYPTION_KEY`). Run: `python -m apps.backup_keys`.
- `apps/weekly_review.py` — **[Phase A6 — to build]** Sunday review script. Memory health + sentinel hit rate + 3 memory quality questions. Run: `python -m apps.weekly_review`.

---

## Sub-agents (`agents/`)
- `memory_agent/memory_agent.py` (+ `_prompt.py`) — all memory reads/writes/deletes. Delete path now requires approval gate (**F.9**). Contradiction detection. Targeted form lookup.
- `planner_agent/planner_agent.py` (+ `_prompt.py`) — breaks goals into steps; tracks tasks/commitments. Four modes: goal, review, prioritize, general.
- `summarizer_agent/summarizer_agent.py` (+ `_prompt.py`) — summarization, breakdown, analysis. Three modes.

---

## Graph & orchestration (`core/orchestration/`)
- `graph.py` — builds and compiles the LangGraph state machine. Single source of truth for all nodes and edges.
- `state.py` — `AegonState` typed dict. Shared object flowing through every node. Fields include: `access_level`, `proactive_context`, `pending_approval`, `approval_verdict`, `requires_approval`. **[Phase A2 adds `access_level` field]**
- `llm_client.py` — single shared LLM client. `call_llm(...)`. Backend chain `BACKEND_ORDER = (nvidia, nvidia_alt, openrouter, ollama)`, walking on 429 or any failure. Primary: NVIDIA NIM `nvidia/nemotron-3-nano-30b-a3b`, alt `nvidia-nemotron-nano-9b-v2` (both `NVIDIA_LLM_API_KEY`) — NVIDIA outages are **per-model**, so one model is not redundancy (503 on the primary while three siblings served fine, 2026-08-07). `PRIMARY_BACKEND` = one-line switch for Phase C2. Replaced Groq 2026-08-07. **Model choice is latency-driven, not capability-driven** — bigger models queue worse on NVIDIA's shared endpoint (super-120b: 1.6–17.2s; nano-30b-a3b: 1.3–1.9s). Do not "upgrade" to super/ultra without re-measuring.
- `checkpointer.py` — persistent state in PostgreSQL. Survives restart.
- `referent_store.py` — **[Phase B5 / F33 — in progress, mocked gate passed 2026-08-17]** bounded (4 slots, 30-min TTL), thread-safe, per-session typed referent store. `Referent{value, type, provenance, created_at}`. `add()`/`latest()`/`clear_session()`. `latest()` provenance-gates to `allowed_provenance` (defaults to `("tool_result",)` only) — a `memory`-provenance referent is never returned unless a caller explicitly widens the allow-list, so it fails closed by default. Not persisted; resets with the process, same as `proactive_queue.py`.

### Nodes (`core/orchestration/nodes/`)
- `intent_classifier.py` — Groq #1. Classifies intent. **F.2/F23 done: punctuation-independent.** Bug 1a: weather/news/schedule classified as live-data TASKS (not conversation); general-knowledge questions stay conversation (rule 14 + counter-example in `prompts/intent_classifier_prompt.py`).
- `orchestrator_node.py` — Groq #2. Routes to worker. Builds A2A payload. Picks tool from registry. Contains F22 schema-echo backstop (drops dict-valued `tool_input`). Bug 1b: parses/validates a `tool_calls` batch (≥2 known tools for multi-tool turns, else collapses to single). **[Phase B5 / F33 — in progress]**: parses an optional `referents` field from the orchestrator LLM's own JSON output (no new call, no widened firewall — same trust boundary as today); stores each as `tool_result`-provenance via `referent_store.add()` only once a valid tool manifest is confirmed; resolves bare backreference words (`there`/`that`/`them`/`it`/`those`/`this`/`him`/`her`) in `tool_input`/each `tool_calls` element against `referent_store.latest()` before the tool call goes out. Field-name → referent-type heuristic (`_FIELD_TYPE_HINTS`) prefers a same-type match; falls back to most-recent-of-any-type. Leaves the placeholder word unresolved (today's behavior) when nothing matches — no regression.
- `conversation_node.py` — Groq #3a. Casual conversation (Aegon personality). Mode-aware.
- `task_node.py` — Groq #3b. Brain-only tasks. Capability check + approval gate. Mode-aware.
- `mode_switch_node.py` — no LLM. Updates `active_mode`. **[Phase A5 adds auto-detection from time/calendar/activity]** Manual keyword override always wins.
- `tool_node.py` — runs tools: approval-park / approved-run / direct-run. Phrases output by `response_style`. Uses `approval_prompt()` + `redact_for_log()`. Bug 1b: multi-run branch executes each non-gated tool in a `tool_calls` batch and joins answers; gated tools in a batch are never auto-run (flagged for separate approval).
- `approval_handler.py` — handles a pending-approval reply. Keyword match first, LLM fallback for ambiguous. Fail closed. **[F.9 adds `memory_delete` action type here]**
- `governance_node.py` — three-layer axiom enforcement before TTS. Layer 1: structural (no LLM). Layer 2: pattern matching (no LLM). Layer 3: LLM only for ambiguous. **F.3: three-layer refactor needed here.** F21 override (`_own_data_intents`) already present.
- `response_synthesizer.py` — Groq final personality finish. `_challenge_check()` (A4) fires only on brain-only task/plan turns — Bug 2: skipped whenever a tool ran this turn (`tool_result` set), so read-only retrievals never get "Still confirm?". **[Phase A2 adds `access_control.filter_response()` call here]**. Axiom 6 framing. Rule-1 truncation fix.

---

## Sentinel (`core/sentinel/`) — **[Phase A1 — to build]**
- `sentinel.py` — daemon thread. Always running. Monitors memory every 30 minutes. Fires on events. Pushes `Finding` objects to `proactive_queue`. Never blocks voice loop. Never writes to memory.
- `rules.py` — five deterministic rules: deadline, habit_deviation, stale_decision, dormant_project, recurring_error. Plus event triggers: `on_new_fact()`, `on_calendar_approaching()`.
- `findings.py` — `Finding` dataclass. Fields: type, content, urgency, timing, created_at, surfaced, sir_response.

---

## Feedback (`core/feedback/`) — **[Phase A1.4 — to build]**
- `feedback_store.py` — logs every sentinel finding surfaced and Sir's response (acted_on / ignored / dismissed / corrected). Computes hit rate per rule type. Used by weekly review and sentinel for priority adjustment.

---

## Memory (`core/memory/`)
- `memory_store.py` — the memory store (PostgreSQL/pgvector). Eight forms: user_profile, conversation, decision, project, habit, error, inference (Phase A3), trusted_contact (Phase A2). **[Phase A3 needs `get_active_projects()`, `get_open_decisions()`, `get_emotional_weight()`, `get_all_facts_for_inference()`, `get_session_metadata()` added]**
- `fact_extractor.py` — extracts facts from turns. Sir-statement turns only (not tool turns, not memory_query turns). Buffer clears after each run. F16 gate confirmed in code.
- `context_injector.py` — formats Tier-3 facts into system prompt. `build_memory_context(query)` + `build_session_context(query)` are **relevance-gated** (2026-06-21): per-turn `search_facts` retrieval, only facts ≥0.35 similarity injected — a greeting pulls nothing. `_retrieve_relevant()` helper. No LLM call.
- `inference_engine.py` — **[Phase A3.2 — to build]** weekly LLM pass over all facts. Generates pattern inferences. Stores as `inference` form with `source="inference_engine"`. Runs Sunday at 02:00 or first session of week.
- `vault_sync.py` — Obsidian → Tier-3 memory sync at session start. **Identity-only (2026-06-20):** stores note title + optional frontmatter `purpose:` line; note BODY is never read into a fact. `_extract_purpose()` parses frontmatter only, stops at closing `---`. Content persisted only on Sir's explicit "remember the content of note X" — Part 2 DONE: `note_remember` intent → `memory_agent._handle_note_remember()` reads the note via `ObsidianReadConnector` and stores its body (`source="explicit"`, capped 2000 chars). Local embedding, no external call (Axiom 2).
- `session_logger.py` — encrypted session logs. 1.5s merge window. Fires `on_user_turn_complete` callback.
- `db_init.py` — database initialization. Schema for all memory forms. **[Phase A2 adds `trusted_contact` form; Phase A3 adds `inference` form]**

### Modes (`core/modes/`)
- `morning_mode_runner.py` — morning operating mode logic.
- `morning_briefing.py` — **[Phase F.6 — to build/complete]** structured briefing builder. Fires when `active_mode == "morning"` at session start. Outputs: sentinel queue + calendar + active tasks. Under 60 seconds. Opens with "Sir, here is your briefing."

---

## Awareness (`core/awareness/`) — **[Phase B3 — to build]**
- `screen_monitor.py` — periodic screenshot analysis using local vision model. No cloud. Provides activity context.
- `app_monitor.py` — `psutil` active application detection. Provides activity context for mode auto-detection.

---

## Calendar polling (`core/connectors/`) — **[Phase A1.3 — to build]**
- `calendar_polling.py` — polls calendar every 5 minutes. Fires `sentinel.on_calendar_approaching()` when event is within 15 minutes.

---

## Observability (`core/observability/`)
- `decision_logger.py` — logs every routing decision to `logs/decisions.jsonl`.
- `logs/decisions.jsonl` — full decision trail.
- `logs/tool_calls.jsonl` — every tool call with per-connector redaction.

---

## Protocols (`core/protocols/`)
- `a2a_schema.py` — the agent-to-agent message schema between nodes.

---

## Security (`core/security/`)
- `governance_rules.py` — the eight axioms as evaluable Python. The constitution. Three-layer structure documented here.
- `voice_auth.py` — **[Phase A2.1 — to build]** resemblyzer voiceprint verification. Local, no cloud. `enroll_owner()` + `verify()`. Threshold 0.75.
- `access_control.py` — **[Phase A2.2 — to build]** three-tier access model (owner / trusted_guest / unknown). `get_access_level()` + `filter_response()`. RESTRICTED_FORMS and RESTRICTED_TOPICS defined here.
- `sir_voiceprint.npy` — **[Phase A2.1 — created by enroll_owner.py]** Sir's voiceprint embedding. Local only.
- `token_store.py` — encrypted OAuth token store. Fernet. Key from `AEGON_TOKEN_KEY` env var. Tokens at `core/security/tokens/<service>.token`.
- `gmail_auth.py` — Gmail OAuth flow. One-time auth + auto-refresh.
- `spotify_auth.py` — Spotify OAuth. Auth + self-refreshing client. `ensure_device` + `launch_in_app` (Windows, `spotify:` URIs only, Axiom 4 approved). `describe_spotify_error(e, action)` — shared spoken-quality error phrasing (429/401/403/404), used by all five connectors. **Do not add retry/backoff logic here — spotipy already retries 429/5xx three times honouring `Retry-After`; a 429 reaching Aegon means those were exhausted.**
- `gmail_client_secret.json` — OAuth client secret (gitignored).
- `tokens/` — encrypted token files (gitignored).

---

## Prompts (`prompts/`)
- `intent_classifier_prompt.py` — 8 intent labels. Rule 13 (file ops always = task). **F.2: add punctuation-independence rule + unpunctuated examples**
- `orchestrator_prompt.py` — routing instructions for orchestrator_node. **[Phase B5 / F33]** Rule 11: optional `referents` output field — Sir's own words for a named place/person/artist/repo/note used to fill `tool_input`, never a converted/looked-up form (e.g. "Tunisia", not "Africa/Tunis"). Bare backreference words ("there" etc.) pass through `tool_input` literally, never guessed by the LLM.
- `conversation_prompt.py` — Aegon personality system prompt.
- `task_prompt.py` — task handling instructions.
- `tool_node_prompt.py` — honesty principles + Axiom 6 content-is-data framing.
- `governance_prompt.py` — three-layer governance instructions. Axioms 1–8. Axiom 6 injection-fail example.
- `synthesizer_prompt.py` — final personality finish. Axiom 6 framing. Rule-1 truncation fix. **[Phase A4 adds challenge-check instructions]**
- `approval_handler_prompt.py` — yes/no/cancel interpretation instructions.
- `mode_prompts.py` — six operating mode definitions + auto-detect triggers.

---

## Schemas (`schemas/`)
- `intent_schema.py` — single source of truth for 8 valid intent labels: `conversation`, `task`, `memory_query`, `summarize_request`, `plan_request`, `mode_switch`, `clarification_needed`, `rule_override_attempt`.

---

## Tool infrastructure (`tools/`)
- `base_connector.py` — `BaseConnector` ABC. Every tool subclasses this. `validate()`, `execute()`, `describe()`, `permission_level`, `requires_approval()`, `approval_prompt()`, `redact_for_log()`.
- `mcp_connector.py` — `MCPConnector` bridge to MCP stdio servers. Language-agnostic. `mcp_env` passes environment to server. Written once — every MCP-backed tool reuses.
- `tool_registry.py` — auto-discovers connectors by scanning for `connector.json`. Safe `importlib` load. `requires_approval` decided here (not by LLM).
- `tool_logger.py` — logs every tool call to `tool_calls.jsonl`. Per-connector redaction.
- `core/research_notes.py` — saves link-bearing search results to `workspace/research/<date>-<slug>.md` so Aegon can say "I have put the links in a note" instead of reading URLs aloud. Called from `tool_node._build_response()` (summarize branch); triggers on results carrying `href`, so it covers every link-returning search tool without a hardcoded list. **Ungated by Sir's explicit decision (2026-08-07) — the only ungated write path in the system.** Bounded: workspace only (never the vault), auto-generated filenames, `is_allowed()` re-checked, never memory content, skipped below 2 linked results. Do not widen.
- `file_paths.py` — `ALLOWED_PATHS` scope guard + `OBSIDIAN_VAULT` and `WORKSPACE` constants. `is_allowed()` uses `os.path.commonpath`. Blocks out-of-scope paths.
- `connector_creator/scaffold.py` — scaffolds a new connector folder.

---

## Connectors (`tools/` — each folder = `*_tool.py` + `connector.json` + `__init__.py`)

### Built and verified
- `clock/` — time/date via MCP time server. IP timezone. `aspect` phrasing. **read_only.** F22 ✅
- `weather/` — wttr.in. One spoken line. **read_only, verbatim.** ✅
- `web_search/` — DuckDuckGo. **read_only, summarize.**
- `github_search/` — GitHub repo search via official MCP binary (`tools/bin/github-mcp-server.exe`). Path via `GITHUB_MCP_BINARY` env var. **read_only.**
- `gmail_read/` — reads new emails (metadata + snippet). No-new-mail detection. **read_only.** **[F.8: add `_check_injection()` + relay-and-flag]**
- `gmail_send/` — sends email. Verbatim-before-send approval. Body redacted in log. **always_gated.**
- `calendar_read/` — Google Calendar. Today's events. OAuth reuses Gmail token foundation. **read_only.**
- `file_read/` — reads text file in ALLOWED_PATHS. **read_only.**
- `file_write/` — writes text file in ALLOWED_PATHS. Scope-guarded. **write_gated.**
- `news/` — RSS: Reuters/BBC/AP/Al Jazeera. 24h window. feedparser. **read_only.**
- `spotify_search/` — track search. **read_only.**
- `spotify_control/` — pause/resume/skip/previous. Resume names current track. **always_gated.**
- `spotify_play/` — play a named track. Searches + plays top match. **always_gated.**
- `spotify_play_playlist/` — play a named playlist from Sir's library. **always_gated.**
- `spotify_playlists/` — lists Sir's playlists. No track counts (API limitation, F19 handled). **read_only.**
- `obsidian_search/` — keyword search across vault `.md` files. Top 5 results with excerpts. **read_only.**
- `obsidian_read/` — full content of a named note (case-insensitive title match). **read_only.**
- `obsidian_create/` — creates new `.md` in vault root. No overwrite. **write_gated.** Explicit Sir instruction only. **[F.7: confirm no auto fact-push; ingestion is one-way Obsidian→memory]**
- `obsidian_append/` — appends text to existing note. No overwrite. **write_gated.**

### Binaries
- `tools/bin/github-mcp-server.exe` — GitHub MCP Go binary v1.1.2. Windows. Path via `GITHUB_MCP_BINARY` env var.

---

## Reminders (`tools/` + `core/reminders/`)
- `tools/reminder_set/` — durable reminders via Google Calendar. Writes Aegon-stamped events (private prop `aegon_reminder=1`). **write_gated.**
- `tools/timer_set/` — ephemeral in-memory timer. `threading.Timer`. No calendar. For short countdowns. **read_only.** Note: `enabled:true` — Axiom 4 audit pending Sir's call.
- `core/reminders/reminder_watcher.py` — daemon thread. 60s poll. Voices only Aegon-stamped events (Axiom 6). Uses `core/voice/speak.py`.
- `core/voice/speak.py` — Aegon's single TTS mouth. NVIDIA Riva gRPC — Chatterbox-Multilingual (`Chatterbox-Multilingual.en-US.Male`, env-tunable via `AEGON_TTS_VOICE`), cloud/DGX-hosted, key from `NVIDIA_TTS_API_KEY`. Returns LINEAR_PCM 22050 Hz, played via pyaudio. `_speak_lock` serializes playback. All spoken output routes through here (response_synthesizer, reminder_watcher, timer_set, morning_briefing, sentinel). History: local Chatterbox tried 2026-06-19, reverted (4GB GPU); Gemini TTS/Charon used until 2026-08-07, replaced by hosted Chatterbox — same model family, no VRAM cost.

---

## Tests (`tests/`)

### Phase F tests — to be created
- `tests/phase_f/test_whisper_accuracy.py` — 20-turn STT accuracy measurement
- `tests/phase_f/test_routing_punctuation.py` — 10 unpunctuated questions route correctly
- `tests/phase_f/test_governance_layers.py` — three-layer governance; Layer 3 not called on clear turns
- `tests/phase_f/test_f21_governance_override.py` — extends existing test (was 6/6; add Layer 2 + Layer 3 tests)
- `tests/phase_f/test_f16_extraction_gate.py` — tool/memory_query turns produce zero facts
- `tests/phase_f/test_morning_briefing.py` — briefing fires automatically, under 60 seconds
- `tests/phase_f/test_obsidian_ingestion.py` — confirms no auto fact-push, Obsidian→memory ingestion works, stores stay distinct
- `tests/phase_f/test_axiom6_relay_flag.py` — injection emails relayed with warning, not blocked
- `tests/phase_f/test_delete_confirmation.py` — every delete asks confirmation; no-leak test

### Phase A tests — to be created
- `tests/phase_a/test_sentinel_rules.py` — each of 5 rules generates findings correctly in isolation
- `tests/phase_a/test_sentinel_no_blocking.py` — sentinel never delays voice loop turns
- `tests/phase_a/test_voice_auth.py` — 95% accuracy Sir, 95% accuracy non-owner
- `tests/phase_a/test_access_control.py` — owner full, unknown restricted, full-access override
- `tests/phase_a/test_session_context.py` — context paragraph in system prompt, no LLM call
- `tests/phase_a/test_inference_engine.py` — inferences generated from seeded patterns
- `tests/phase_a/test_challenge_layer.py` — habit conflict detected, no false positives
- `tests/phase_a/test_mode_auto_detect.py` — time/calendar/activity trigger correct modes
- `tests/phase_a/test_feedback_store.py` — surfaces logged, responses logged, hit rate correct

### Existing tests
- `test_f21_governance_override.py` — deterministic F21 proof (currently 6/6).
- `test_axiom6.py` — Axiom 6 framing proof (live LLM). Tests 3 and 5 must be updated when F.8 is built.
- `phase5/test_tool_routing.py` — end-to-end classifier→tool→governance→synth.
- `phase3/*` — intent / orchestrator / governance / full-graph (some are stubs).
- connector tests: `test_github_connector`, `test_spotify_connector`, `test_spotify_auth`, `spotify_reauth`, `spotify_playlist_debug`, `discover_github_tools`.
- memory tests: `test_memory_store`, `test_fact_extractor`, `test_extract_and_store`, `test_context_injector`, `test_session_logger`.
- misc/legacy: `test_groq`, `test_gemini`, `test_json_routing`, `test_stt`, `test_aegon_voice`, `test 3 agents`, `resave_model`.
- `docs/retired/test_task_router.py` — retired.

---

## Project-level docs
- `flags.md` — open flags register. Every unresolved issue, open decision, deferred item. Single source of truth for flags. Resolved flags stay in resolved log — never deleted.
- `aegon_state.md` — current state. Read every session. Keep tiny. Done / next / open flags summary.
- `aegon_roadmap.md` — full archive: phases, decisions, flags, build steps, success criteria. Read in slices only.
- `aegon_architecture.md` — system design and locked decisions. Read in slices only.
- `aegon_file_index.md` — this file.
- `docs/aegon_build_log.md` — session-by-session build narrative.
- `docs/retired/` — retired files.