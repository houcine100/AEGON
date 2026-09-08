# Aegon — Build Roadmap

*A personal multi-system orchestrator and master AI agent built to be a present, anticipatory partner — not a tool that waits to be used.*

*Flags live in `flags.md`. Design lives in `aegon_architecture.md`. File map lives in `aegon_file_index.md`. Current state lives in `aegon_state.md`. This roadmap is the phase plan: what was built, what is being built, and what comes next — with build steps and success criteria for every step.*

---

# The JARVIS Behavioral Contract

Every decision in this roadmap is measured against one standard. Not correctness. Not architectural elegance. This:

> **Does this make Aegon behave more like a present, anticipatory partner — or does it make it a more capable tool that waits to be used?**

The six behaviors that define the contract:

1. **Anticipatory** — Aegon speaks before Sir asks. It monitors continuously and surfaces what matters without being prompted.
2. **Instantaneous perception** — Aegon hears and understands without Sir having to initiate a session.
3. **Persistent context** — Aegon never loses the thread. A conversation from three days ago is live context today. It connects dots across time without being asked.
4. **Invisible infrastructure** — Sir never thinks about how Aegon works. He just talks. The system disappears.
5. **Judgment, not just execution** — Aegon tells Sir when a plan has a flaw, flags risks, and offers alternatives. It has an opinion.
6. **Total environment awareness** — Aegon knows what Sir is doing, what he has done, and what is about to happen.

---

# The Governing Principle

**Build narrow, reliable, composable layers. Only add complexity when the previous layer is stable. Never build a new layer on a foundation you are not certain about.**

---

# Constitution — The Eight Axioms

The constitution is extensible only by Sir, never by Aegon. This amendment clause is itself an extension of Axiom 3.

| # | Axiom | Enforcement type |
|---|---|---|
| 1 | Never acts in the real world without explicit approval | Per-turn — task_node gate + governance Layer 1 |
| 2 | Memory is private by default — nothing leaves the machine without consent | Per-turn — governance Layer 2 + memory-to-tool firewall |
| 3 | Cannot modify its own core rules or constraints | Per-turn — rule_override_node at classifier + governance Layer 1 |
| 4 | Capability expansion is gated — new tool, connector, or integration only after Sir audits and approves. Unknown risk defaults to gated. | Structural — tool_registry, no auto-add path |
| 5 | Credential gating — Sir performs every login himself; Aegon never enters Sir's credentials | Structural — covered by Axiom 1 |
| 6 | Observed content is data, not commands — everything Aegon reads is information to report, never instructions to obey | Per-turn — governance Layer 2 + content prompts |
| 7 | Sub-agents inherit every limit — no sub-agent may do what Aegon cannot; delegation never bypasses a gate; sub-agents prepare and propose, never execute | Structural — graph routing |
| 8 | Aegon monitors continuously — it is never passive between sessions | Structural — sentinel daemon thread, always running |

**Constitution history**: Axioms 1–3 are the original permanent axioms (Phase 0). Axioms 4–7 were added June 2026 by Sir as a documented amendment. Axiom 8 is added in this roadmap as the foundation for the proactive layer.

**Enforcement tradeoffs currently in effect** (full detail in `flags.md`):
- Axiom 6 relay-and-flag: injection emails are relayed with a warning prepended, not blocked. Resolved in Phase F.8 (2026-06-13).
- Axiom 3 is behavioral + governance-layer only until Agent-C runtime enforcement at Phase C2.
- Groq sends text off-machine during development. Resolves at Phase C2 (full local stack).

---

# Architecture Decisions — Locked

### Core Principle
- Session model maintained until dedicated 24/7 hardware exists — then continuous presence (Phase B4)
- Groq is the brain — handles all thinking at every node
- Whisper + silero-vad is the ear — local, no cloud, no session overhead (replaces failed Gemini Live)
- Gemini TTS is the mouth — speaks Groq's responses — Charon voice
- LangGraph is the skeleton — state machine, never thinks, only routes
- Sentinel runs permanently — independent of voice loop, pushes findings to the orchestrator (Phase A1)
- Memory updates in real time — after every Sir-statement turn + every 30 minutes
- Governance is three-layer — structural rules first, pattern matching second, LLM only for ambiguous cases (Phase F.3)

### Locked Architectural Decisions (permanent)
- All communication through the orchestrator — no direct agent-to-agent
- `llm_client.py` is the single shared LLM client — one line to swap models in Phase C2
- `graph.py` is the single source of truth for flow — all nodes and edges defined there
- `governance_node.py` runs before every TTS call — no exceptions
- Automatic failover: Groq → Ollama when rate limit hit
- The registry (not the LLM) decides `requires_approval` — Axiom 1 safety
- Memory-to-tool firewall: tool payloads built from Sir's words only — never from `memory_context`
- A tool is "a task that needs a tool" — no separate `tool_request` intent; classifier says `task`, orchestrator picks the tool from the registry
- No tool writes outside `ALLOWED_PATHS` in `file_paths.py`
- No memory write without schema validation
- Tasks always execute regardless of active mode — mode only affects response style
- Do NOT build an outward-facing MCP server — would break orchestrator-only-entry
- Audit before registering any external MCP server. Skills ≠ servers. Prefer Python servers.

### Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Orchestration framework | LangGraph 1.1.6 | Installed |
| LLM brain — primary | Groq free tier — llama-3.3-70b-versatile | MODEL_BACKEND = "groq" |
| LLM brain — backup | Ollama — gpt-oss:120b-cloud | Automatic failover on rate limit |
| LLM brain — Phase C2 | Local model — Qwen3.5 or equivalent | MODEL_BACKEND = "local" — one-line swap |
| STT | Whisper medium.en — local | Replaces failed Gemini Live |
| VAD | silero-vad — local | End-of-speech detection |
| TTS | Gemini TTS — gemini-3.1-flash-tts-preview | Charon voice |
| Voice auth | resemblyzer — local | Owner voiceprint verification (Phase A2) |
| Agent-to-agent protocol | Typed payloads via a2a_schema.py | |
| Memory engine | PostgreSQL + pgvector | Docker container aegon-memory, port 5432 |
| Embedding model | all-MiniLM-L6-v2 | 384 dimensions, local |
| Checkpointer | PostgreSQL via langgraph-checkpoint-postgres | Same Docker instance |
| Observability | JSONL — decisions.jsonl + tool_calls.jsonl | |
| Operating modes | Six — standard, focus, research, morning, night, deep_work | |
| Language / runtime | Python 3.12+ | |
| Chatterbox-Turbo / Maya 1 | Deferred to Phase C2 | Emotional voice |

### Development Environment

| Decision | Choice |
|---|---|
| Dependency management | venv |
| Secrets management | OS environment variables — no .env files |
| OAuth tokens | Encrypted local store — key from env var |
| Code editor | PyCharm |
| Version control | Local files only — no Git, no remote |
| Backup | Encrypted external drive backup at end of each phase |
| Encryption keys backup | `python -m apps.backup_keys` — stored separately from data |

### Working Method (how Aegon is built)
- Analyse → agree → assistant gives copy-paste code → Sir runs and validates in PyCharm
- Sir does ALL installs and runs. The assistant never runs project code.
- One step at a time. No jumping ahead. Finish and verify one thing before the next.
- Surgical edits only. Change exactly what the task needs.

---

# PART I — BUILT FOUNDATION (Phases 0–6)

*The durable record of what is built and why. These phases are complete except where a Phase F item is explicitly called out. Read this to understand the system as it stands today.*

---

## Phase 0 — Foundation ✅

**Goal**: Lock identity, axioms, stack, and environment before any code.

### 0.1 Aegon's Identity
- **Official definition**: Aegon is a multi-system orchestrator and master AI agent that listens to Sir, remembers everything important about his life, and coordinates specialized sub-agents to help him think, plan, and organize with clarity, calm, and directness — acting only with Sir's explicit approval in the real world, and constantly monitoring, updating, and securing itself within the boundaries Sir defines.
- **Autonomy level**: High internal autonomy within permitted systems; zero unsanctioned real-world actions.
- **The eight axioms**: see Constitution section above.

### 0.2 Research Foundation
The build is grounded in: multi-agent orchestration and MCP/A2A research (arXiv:2601.13671), Anthropic's orchestrator-worker pattern, LangChain multi-agent architecture, OpenAgentSafety (safety failures in 51–72% of agentic tasks), AWS Agentic Security Scoping Matrix, NVIDIA self-securing agent runtime, Knight Institute autonomy levels, Cloud Security Alliance identity governance, Google ADK + A2A, Agent-C runtime constraint enforcement (planned Phase C2), CMAG constitutional governance (planned Phase C2), and OpenJarvis (skills system, Intelligence Per Watt, health check pattern).

### 0.3 Success Criteria ✅
- [x] Identity locked and written
- [x] Eight axioms defined and permanent
- [x] Tech stack chosen with rationale
- [x] Development environment and secrets policy locked
- [x] Version control and backup policy locked

---

## Phase 1 — The Voice Loop ✅ (STT under replacement — see Phase F.1)

**Goal**: Aegon can hear Sir, process words through Groq, and speak back. No memory, no sub-agents — just the pipeline end-to-end.

### 1.1 What Was Built
- `apps/voice/aegon_voice.py` — STT capture only, no text logic
- `core/routing/task_router.py` — Groq brain + Gemini TTS mouth (retired in Phase 3, replaced by orchestrator)
- `session_logger.py` — turn consolidation, fires `on_user_turn_complete` callback on a complete turn
- Aegon personality system prompt: opens with "Welcome back, Sir"; calm, direct, slightly sarcastic; short sentences; addresses Sir always; never hallucinates facts or invents memories; detects emotional signals from memory and adjusts tone

### 1.2 Build Steps ✅
- [x] Python venv set up
- [x] Dependencies installed
- [x] API keys set as OS environment variables
- [x] Groq connection tested
- [x] Whisper STT tested (kept installed — now pulled forward to Phase F.1)
- [x] Gemini connection tested
- [x] aegon_voice.py built
- [x] task_router.py built (retired in Phase 3)
- [x] session_logger callback wired for task detection
- [x] Aegon full personality system prompt set
- [x] End-to-end pipeline tested

### 1.3 Security Policy ✅
- Mic access is local only
- Groq receives text only — no audio
- Gemini TTS receives text only — no audio
- API keys stored as OS environment variables only
- Text processing runs in an isolated thread — cannot affect the audio session

### 1.4 Success Criteria ✅
- [x] Aegon hears Sir; all responses come from Groq
- [x] One voice, one brain across all interactions
- [x] Task keywords correctly detected on full consolidated text
- [x] Memory context injected into every Groq call
- [x] No crashes on 10 consecutive turns
- [x] Aegon personality recognizable in every response

> **Open against this phase**: Gemini Live STT failed catastrophically in practice and is being replaced by Whisper + silero-vad in **Phase F.1**. The brain, mouth, and rest of the pipeline are unchanged — only the ear changes.

---

## Phase 2 — Memory ✅ (encryption at rest open — see Phase F.4)

**Goal**: Aegon remembers Sir across sessions and in real time during 24/7 operation.

### 2.1 Memory Architecture
**Tier 1 — Working memory**: Groq conversation history, last 20 turns in context, resets on restart.

**Tier 2 — Episodic memory**: every session logged as JSONL in `core/memory/sessions/`. Turn consolidation with merge window (6s original, reduced to 1.5s in Phase F.1). Emotional weight detection per turn. Transcription reliability flag.

**Tier 3 — Semantic memory**: distilled facts in PostgreSQL + pgvector. all-MiniLM-L6-v2 embeddings (384 dimensions). Fact extraction by Groq after every Sir-statement turn + every 30 minutes. Deduplication threshold 0.90. Contradiction detection threshold 0.75. Context injected into every Groq call.

### 2.2 Memory Forms ✅
Six forms active at Phase 2: `user_profile`, `conversation`, `decision`, `project`, `habit`, `error`. (Two more added later: `inference` in Phase A3, `trusted_contact` in Phase A2 — total eight.)

### 2.3 Memory Record Schema ✅
Fields: `fact`, `form`, `emotional_weight`, `stability`, `status`, `source`, `created_at`, `updated_at`, `resolution_notes`, `embedding`.

### 2.4 Memory Behavior Rules ✅
- [x] Contradiction handling — dialogue, not silent overwrite (built in Memory Agent, Phase 4)
- [x] Memory capture — auto-save + periodic extraction
- [x] Behavioral delta detection
- [x] Deletion rules — periodic proposals + voice delete (confirmation gate added in Phase F.9)

### 2.5 Build Steps ✅
- [x] Define and validate schema
- [x] Store raw conversations locally
- [x] Extract key facts after every task
- [x] Inject memories at session start
- [x] Manual "remember that..." command
- [x] Manual "forget that..." command
- [x] Memory review — "what do you know about me?"
- [x] Behavioral delta detection

### 2.6 Security Policy
- [x] Memory files stored locally
- [ ] Encrypted at rest — **OPEN, Phase F.4**
- [x] Memory never leaves machine
- [x] Delete confirmation gate — **resolved in Phase F.9** (was open)
- [x] Every write/update/delete logged — resolved (memory audit log in memory_store.py)

### 2.7 Success Criteria ✅
- [x] Recalls something from a previous session
- [x] Uses a personal fact without prompting
- [x] Contradiction handling triggers dialogue
- [x] Behavioral delta detection fires correctly
- [x] Memory feels additive, not intrusive
- [x] Add, review, delete via voice

### 2.8 Emotional Behavior
- Now: Groq detects emotional context from Tier 3 memory and adjusts response tone.
- Phase C2: Chatterbox-Turbo emotion control or Maya 1.

---

## Phase 3 — Orchestrator Core ✅ (three-layer governance refactor — see Phase F.3)

**Goal**: Aegon becomes a true orchestrator with LangGraph, typed A2A protocol, and a governance layer.

### 3.1 What Changed from Phase 1/2
Phase 1/2 was a simple hand-off (session_logger → task_router → Groq directly). Phase 3 is a full LangGraph state machine with typed A2A payloads, governance enforcement, and a full audit trail. `aegon_core.py` and `task_router.py` were retired and replaced by the orchestrator. `aegon_voice.py` was wired to `aegon_orchestrator.py` via a background thread so the voice loop is never blocked.

### 3.2 What Was Built
| Component | What it does |
|---|---|
| `graph.py` | LangGraph state machine — single source of truth |
| `state.py` | AegonState typed dict — shared object through every node |
| `llm_client.py` | Single shared LLM client — Groq primary, Ollama backup, one line to swap |
| `intent_classifier.py` | Classifies intent |
| `orchestrator_node.py` | Builds typed A2A payload, decides routing |
| `conversation_node.py` | Aegon personality responses |
| `task_node.py` | Capability check + approval gate |
| `governance_node.py` | Checks axioms before TTS |
| `response_synthesizer.py` | Final personality finish + Gemini TTS handoff |
| `clarification_node.py` | Handles vague inputs — no LLM call |
| `rule_override_node.py` | Blocks Axiom 3 violations at classifier level |
| `a2a_schema.py` | Typed A2A message — sender, receiver, intent, payload, session_id, confidence, requires_approval |
| `governance_rules.py` | Axioms as evaluable Python rules |
| `checkpointer.py` | PostgreSQL persistent state — survives restarts |
| `decision_logger.py` | JSONL audit trail — every node, every decision |
| `aegon_orchestrator.py` | Entry point — receives callback, runs graph, logs decisions |

### 3.3 Governance — Axioms Enforced
- Axiom 1 — no real-world action without approval: task_node gate + governance_node
- Axiom 2 — memory private by default: governance_node blocks personal data sharing
- Axiom 3 — no self-modification: rule_override_node at classifier + governance_node

### 3.4 Security Policy ✅
- Orchestrator is the only entry point — no agent bypasses it
- Every routing decision logged and auditable
- Low confidence → clarification_node — never a wrong action
- Governance active on every turn — no exceptions
- Rule override attempts detected at classifier level — never reach workers

### 3.5 Success Criteria ✅
- [x] Correctly routes different intents
- [x] All routing decisions logged and readable
- [x] Response feels unified — one Aegon voice
- [x] Low-confidence inputs trigger clarification
- [x] Governance blocks all axiom violations
- [x] Rule override attempts blocked at classifier
- [x] PostgreSQL checkpointer — state survives restarts
- [x] Voice pipeline wired to orchestrator
- [x] Automatic LLM failover on rate limit

> **Open against this phase**: governance is currently a single LLM call per turn, which is non-deterministic. The three-layer refactor (structural → pattern → LLM-only-if-ambiguous) lands in **Phase F.3**.

---

## Phase 4 — Specialized Sub-Agents ✅

**Goal**: Build three narrow, reliable sub-agents, each tested in isolation before connection.

### 4.1 Memory Agent ✅
Manages all reads, writes, deletes, and contradiction handling for the memory forms.
- Read: general queries, targeted form lookup, semantic search
- Write: explicit fact storage with contradiction detection
- Delete: semantic search + status update to resolved (confirmation gate added Phase F.9)
- Contradiction handling: detects conflicts, supersedes old facts, informs Sir
- Targeted form lookup: habits, projects, decisions, user_profile, errors

### 4.2 Summarizer Agent ✅
Three internal modes: `summary` (concise structured), `breakdown` (numbered steps with priorities), `analysis` (pros/cons, comparison, direct recommendation).

### 4.3 Planner Agent ✅
Four internal modes: `goal` (breaks goal into 7 prioritized steps, stores as project fact), `review` (lists active tasks from memory, flags time-sensitive), `prioritize` (ranks competing items, direct recommendation), `general` (open-ended planning). Goal plans persist as project facts.

### 4.4 Named Operating Modes ✅
Six modes, switched by keyword (auto-detection added Phase A5):
| Mode | Behavior | Trigger examples |
|---|---|---|
| `standard` | Default — full conversation, all agents | "standard mode" |
| `focus` | Task-only, minimal, blocks casual | "focus mode", "I need to concentrate" |
| `research` | Verbose, detailed, comprehensive | "research mode", "dig deep" |
| `morning` | Daily briefing — tasks, reminders, memory | "morning mode", "good morning" |
| `night` | Quiet, calm, minimal | "night mode", "winding down" |
| `deep_work` | Do not disturb — one-sentence answers | "deep work mode", "I am coding" |

### 4.5 Additional Phase 4 Additions ✅
- Multi-turn conversation history — last 6 turns injected into every node
- Automatic Groq → Ollama failover on rate limit
- Real-time fact extraction in a background thread after every turn
- Planner persistence — goal plans stored as project facts
- Contradiction handling in Memory Agent
- All communication through orchestrator — no direct agent-to-agent (locked)

### 4.6 Intent Labels ✅
Eight active labels (single source of truth in `schemas/intent_schema.py`): `conversation`, `task`, `memory_query`, `summarize_request`, `plan_request`, `mode_switch`, `clarification_needed`, `rule_override_attempt`.

### 4.7 Success Criteria ✅
- [x] Each sub-agent works in isolation before connection
- [x] Orchestrator correctly delegates to all three agents
- [x] No sub-agent can trigger real-world actions independently
- [x] Named modes switch correctly by keyword
- [x] Tasks always execute regardless of active mode
- [x] Multi-turn follow-up questions answered correctly
- [x] Automatic failover to backup LLM on rate limit

---

## Phase 5 — System Integration ✅

**Goal**: Aegon can touch Sir's real systems with explicit approval.

### 5.1 Approval Flow ✅
- `approval_handler` node interprets "yes / no / cancel" after "Shall I proceed?"
- Two linked state fields: `requires_approval` (bool, set by governance) and `pending_approval` (dict — the parked action: tool, tool_input, prompt shown)
- `route_after_classifier` checks `pending_approval` first, before intent, so a confirmation turn is never misrouted
- Fail closed: unclear confirmations never auto-approve. Keyword match first, LLM fallback for ambiguous input.
- Validated by the no-leak test: two gated actions in a row; the second still asks for approval

### 5.2 Connector Framework ✅
- `tools/base_connector.py` — `BaseConnector` ABC: `validate`, `execute`, `describe`, `permission_level`, `requires_approval()`, `approval_prompt()`, `redact_for_log()`
- Permission levels: `read_only`, `write_gated`, `always_gated`
- `tools/tool_registry.py` — auto-discovers connectors by scanning for `connector.json`; safe importlib load via `entry_point`. Adding a connector never requires editing `graph.py`.
- `tools/tool_logger.py` — logs every call to `tool_calls.jsonl`
- `connector.json` fields: name, version, description, permission_level, enabled, response_style, entry_point, input_schema

### 5.3 Web Search Connector ✅
- Library `ddgs`. `read_only`, `response_style: summarize`.
- The registry (not the LLM) decides `requires_approval` — Axiom 1 safety
- Firewall (Axiom 2): the orchestrator builds the query from Sir's words only — never `memory_context`
- Honesty principles in `prompts/tool_node_prompt.py` (uncertainty phrasing, real sources only, flag uncertain stats)

### 5.4 File System Connectors ✅
- Two tools: `file_read` (`read_only`, raw) and `file_write` (`write_gated`, confirm)
- Shared safety fence `tools/file_paths.py` with `ALLOWED_PATHS` and `is_allowed()` (uses `os.path.commonpath`; blocks out-of-scope paths)
- `tool_node` has three branches: approved-run, park, direct-run
- Validated end-to-end including the no-leak test and out-of-scope path blocking

### 5.5 Gmail ✅ (replaced Calendar at the time; Calendar later built separately)
**Credential foundation** (reused by every future OAuth service):
- `core/security/token_store.py` — encrypted token store (Fernet; key from `AEGON_TOKEN_KEY`; tokens at `core/security/tokens/<service>.token`)
- `core/security/gmail_auth.py` — OAuth flow (InstalledAppFlow, Desktop client), `get_gmail_service()` with token load + auto-refresh
- Google Cloud: project created, Gmail API enabled, consent screen, Desktop OAuth client

**`gmail_read`** ✅ — `read_only`, verbatim: metadata + snippet (sender name only, subject, date, preview). No-new-mail detection compares newest email id against a marker in `gmail_state.json` (id only — never content). Invisible characters stripped for clean TTS. Inbox content never logged. (Relay-and-flag injection detection added Phase F.8.)

**`gmail_send`** ✅ — `always_gated`, confirm: sends only when Sir directly asks; always shows full To/Subject/Body and waits for "yes". Body redacted in log; recipient + subject kept for the audit trail.

### 5.6 Credential Rule (locked) ✅
> API keys and secrets Sir controls → environment variables.
> OAuth tokens for connected services → one protected, gitignored location, encrypted at rest with a key from an environment variable.

A local app cannot avoid persisting a self-refreshing token. This is a conscious, documented exception to "env vars only," with protections: single location, gitignored, encrypted, key held only in the environment.

### 5.7 Framework Additions Made During Phase 5 ✅
- `response_style: "verbatim"` — the connector phrases its own output fully
- `BaseConnector.approval_prompt(payload)` — connector defines its own confirmation prompt
- `BaseConnector.redact_for_log(payload, result)` — connector defines what is safe to log
- "A tool is a task that needs a tool" — no separate `tool_request` intent
- Classifier rule 13 — file operations (filename/path/extension) are always `task`, overriding the memory-query keyword pull

### 5.8 MCP Integration Layer ✅
- `tools/mcp_connector.py` — `MCPConnector(BaseConnector)`: language-agnostic stdio bridge (`mcp_command`, `mcp_args`, `mcp_tool_name`, `mcp_env`). Written once; every MCP-backed tool reuses it.
- First server (audited): official `mcp-server-time` (MIT, pure Python)
- MCP servers flow through the same gates as in-process connectors — never around them
- Rules locked: audit before registering; skills ≠ servers; prefer Python servers; do NOT build an outward-facing MCP server
- Honest verdict: for trivial tools, MCP is more work than a hand-built version. The bridge pays off only on big official servers. Hybrid stance: simple tools in-process, MCP for big servers.

### 5.9 GitHub + Spotify Connectors ✅
- **GitHub (via MCP)**: official `github/github-mcp-server` v1.1.2 Windows binary over stdio, `--read-only`, read-only PAT in `GITHUB_PERSONAL_ACCESS_TOKEN`. First tool `github_search`. Binary path via `GITHUB_MCP_BINARY` env var. The bridge gained `mcp_env` so servers inherit Aegon's environment.
- **Spotify (native on spotipy, not MCP)**: no official Spotify MCP server exists, so a native connector set was built — smaller trust surface, token in the encrypted store via a spotipy cache handler in `core/security/spotify_auth.py`. Tools: `spotify_search`, `spotify_playlists` (read_only); `spotify_play`, `spotify_play_playlist`, `spotify_control` (all always_gated).
- **OS app-launch capability**: `spotify_auth.launch_in_app` / `ensure_device` — Aegon can launch the local Spotify app from a fully-closed state. Aegon's first power to start a local program. Deliberately narrow (only `spotify:` URIs, guarded). Approved by Sir under Axiom 4. Windows-only.

### 5.10 Additional Connectors Built ✅
- **Calendar** (`calendar_read`): Google Calendar, today's events, reuses Gmail OAuth foundation. `read_only`, verbatim.
- **Weather** (`weather`): wttr.in, one spoken line. `read_only`, verbatim.
- **News** (`news`): RSS — Reuters/BBC/AP/Al Jazeera, 24h window, feedparser. `read_only`.
- **Clock** (`clock`): MCP time server, IP-resolved timezone, natural phrasing with `aspect` hint. `read_only`.

### 5.11 Reminders ✅
- `tools/reminder_set/` — durable, `write_gated`, Google Calendar (appointments). Watcher `core/reminders/reminder_watcher.py` voices only Aegon-stamped events (private prop `aegon_reminder=1`, Axiom 6). 60s poll, daemon thread.
- `tools/timer_set/` — ephemeral, in-memory `threading.Timer`, no calendar (oven case). LLM routes by intent via connector descriptions. (Note: `enabled:true` — Axiom 4 audit pending Sir's call.)
- `core/voice/speak.py` — Aegon's single TTS mouth (Gemini Charon). response_synthesizer, watcher, and timer all call it.

### 5.12 Morning Mode Runner ✅
`core/modes/morning_mode_runner.py` + `apps/morning_trigger.py` — operating mode runner built and verified. (Wiring it into an automatic structured briefing at session start is Phase F.6.)

### 5.13 Success Criteria ✅
- [x] Approval flow — yes/no/cancel routes correctly
- [x] `requires_approval` and `pending_approval` linked, not duplicated
- [x] Connector framework auto-discovers tools without editing `graph.py`
- [x] Every connector call logged with per-connector redaction
- [x] Access revocable via the registry `enabled` flag
- [x] Web search read-only, summarized
- [x] Orchestrator selects the correct connector and builds its payload
- [x] Governance inspects tool output — no Axiom 2 leak to TTS
- [x] Memory-to-tool firewall holds
- [x] File read free; write gated and scope-limited
- [x] Gmail read (metadata+snippet, search, no-new-mail) and send (always-gated, verbatim-before-send)
- [x] MCP bridge proven (external server through Aegon's gates)
- [x] GitHub search + full Spotify suite + calendar + weather + news + reminders, all verified end-to-end

### 5.14 Deferred from Phase 5 (by design)
- House security + sleep mode — deferred until hardware exists (tracked in `flags.md`)
- Connector-prep agent (L2 autonomy) — deferred (tracked in `flags.md`)

---

## Phase 6 — Skills ✅ (Obsidian bidirectional verification — see Phase F.7)

**Goal**: Skills are governed connectors organised by domain. Every skill starts `enabled: false` (Axiom 4 gate) and is activated only after Sir audits and approves it.

### 6.1 Skill-Creator Framework ✅
`apps/skill_creator/`:
- `init_skill.py` — scaffold: connector.json + tool stub + __init__ + test stub
- `package_skill.py` — zip skill folder → `.aegonskill` artifact
- `install_skill.py` — unzip artifact → tools/, force `enabled: false`

### 6.2 Obsidian Skill ✅
Vault at `aegon/vault/`. Four connectors:
- `obsidian_search` — `read_only`, keyword scan across vault `.md` files, top 5 results with excerpts
- `obsidian_read` — `read_only`, full note content by title (case-insensitive)
- `obsidian_create` — `write_gated`, creates new `.md` in vault root, no overwrite
- `obsidian_append` — `write_gated`, appends to existing note, no overwrite
- `tools/file_paths.py` — `OBSIDIAN_VAULT` constant added, vault added to `ALLOWED_PATHS`
- Deliberately excluded: frontmatter, backlinks, tags, templates, daily notes, embeddings, multi-vault
- Success metric: "Would Sir be genuinely annoyed if this disappeared tomorrow?"

> **Open against this phase**: bidirectional sync direction is unverified. Whether Obsidian edits feed back into Tier-3 memory is confirmed in **Phase F.7**.

### 6.3 Skills On Hold (Sir's decision)
- WhatsApp / Telegram — on hold
- GitHub deep (PRs/issues) — on hold
- Smart-home connectors — slot in when hardware exists

### 6.4 Success Criteria ✅
- [x] Skill-creator framework (init/package/install) built
- [x] Obsidian four-connector suite built
- [x] OBSIDIAN_VAULT scope guard in place
- [ ] Obsidian ingestion + gated write-back confirmed (not a mirror) — Phase F.7

---

# PART II — FOUNDATION COMPLETION

---

## Phase F — Foundation Completion

**Goal**: Close every critical-path open item from Phases 0–6. The foundation must be reliable, correct, and trustworthy before the JARVIS layer is built on top of it.

**The gate rule**: each step has a precise gate. The next step does not start until the current gate passes. Phase A does not start until all nine gates pass. No exceptions.

**Why this discipline is non-negotiable**: every Phase A component has a direct dependency on a Phase F item. The sentinel runs against memory — if extraction is noisy, it surfaces garbage. Voice auth wires into the STT pipeline — if the ear is broken, auth is meaningless. The challenge layer reads memory — if governance is non-deterministic, it fails intermittently. Building Phase A on open foundation items means Phase A failures are impossible to diagnose, because the symptom is in new code and the cause is in old code.

**Order is fixed.** Do them in the sequence below.

---

### F.1 — STT Replacement: Whisper + silero-vad

**Status**: ✅ Done (2026-06-12) — faster-whisper large-v3 on CUDA float16, silero-vad VADIterator (700ms silence), ctranslate2 backend. Gate passed — Sir confirmed live test.

**Why**: Gemini Live STT failed catastrophically in practice. Everything downstream is worthless if the ear is broken. This is the single most critical open item in the entire build. Whisper was already installed and tested in Phase 1 — this pulls it forward from the planned Phase C2 swap.

**What changes**: Only the ear. The Groq brain, Gemini TTS mouth, session_logger callback interface, and the rest of the pipeline are unchanged. `apps/voice/aegon_voice.py` is replaced entirely.

**The new capture pipeline**: a continuous microphone stream feeds silero-vad, which detects speech start and end. On the speech-end event, the captured audio segment is passed to Whisper medium.en for transcription. The transcribed text goes to session_logger with a 1.5-second merge window, which fires the existing `on_user_turn_complete` callback to the orchestrator.

**Implementation requirements**:
- Whisper medium.en — the accuracy/speed sweet spot for English. Drop to small.en if latency is unacceptable; rise to large-v3 only if accuracy demands it.
- The model loads once at startup, not per turn — model load takes several seconds.
- silero-vad runs on the continuous stream and fires a callback on the silence threshold after speech.
- Whisper receives the captured segment, never the raw stream.
- The callback interface to session_logger is unchanged — only the capture mechanism changes.
- The merge window in session_logger.py drops from 6 seconds to 1.5 seconds.

**Build steps**:
1. Install dependencies: openai-whisper, sounddevice, silero-vad.
2. Test Whisper in isolation — record 30 seconds of Sir's voice, transcribe, measure accuracy.
3. Test silero-vad in isolation — confirm speech-start and speech-end events fire correctly.
4. Build the new aegon_voice.py with the combined capture pipeline.
5. Reduce the merge window to 1.5 seconds in session_logger.py.
6. Wire to the existing session_logger callback — no other files change.
7. Run 20 consecutive turns end-to-end, logging transcription accuracy.

**Success criteria**:
- [ ] Whisper transcribes Sir's voice at 90%+ accuracy across 20 consecutive turns
- [ ] silero-vad detects end of speech within 1.5 seconds of Sir stopping
- [ ] No Gemini Live dependency remains in any file
- [ ] Merge window confirmed at 1.5 seconds in session_logger.py
- [ ] Voice pipeline end-to-end: speak → transcribe → orchestrator callback → TTS response
- [ ] No crashes on 20 consecutive turns including silence and background noise
- [ ] Model loads once at startup, not per turn — confirmed in logs

**Security policy**: Whisper and silero-vad run fully local. Microphone audio never leaves the machine — Axiom 2 compliant from the ear.

---

### F.2 — Punctuation-Independent Routing (closes F23)

**Status**: ✅ Done (2026-06-12) — Rule 14 added to intent_classifier_prompt.py. 20/20 tests passed (tests/test_intent_routing_f2.py).

**Why**: STT never adds question marks. "What day is it" with no question mark misroutes to task_node and fails. This breaks every time, date, weather, and email question in voice mode — the exact mode Aegon is built for. The intent classifier currently keys off the "?".

**What to fix**: Edit `prompts/intent_classifier_prompt.py`. The classifier must route by semantic meaning, never by punctuation.

**The change**:
- Add an explicit rule: route by the meaning of the utterance, never by the presence or absence of punctuation. Voice input never contains question marks.
- Add unpunctuated examples that must route correctly: "what day is it" → task (clock); "what time is it" → task (clock); "what's the weather" → task (weather); "do I have any emails" → task (gmail_read); "what do you know about me" → memory_query.
- Strengthen the general principle: intent is determined by words and context, never by punctuation.

**Build steps**:
1. Edit the intent classifier prompt — add the punctuation-independence rule and the unpunctuated examples.
2. Test in isolation — feed 10 unpunctuated questions directly to the classifier, verify routing.
3. Test end-to-end — speak each question through the voice pipeline, verify routing.
4. Run regression — verify all 8 intent labels still route correctly with punctuation present.

**Success criteria**:
- [ ] "what day is it" (no question mark) routes to task → clock
- [ ] "what time is it" routes to task → clock
- [ ] "what do you know about me" routes to memory_query
- [ ] "do I have emails" routes to task → gmail_read
- [ ] All 8 intent labels still route correctly with punctuation — regression clean
- [ ] 10 unpunctuated questions route correctly in isolation
- [ ] 10 unpunctuated questions route correctly through the voice pipeline

---

### F.3 — Three-Layer Governance (closes the F21 broader pattern)

**Status**: ✅ Done (2026-06-12) — governance_node.py rewritten: Layer 1 structural, Layer 2 pattern, Layer 3 LLM-only-if-ambiguous. F21 6/6 + 10/10 Layer tests pass (LLM-not-called asserted).

**What is already resolved**: the `memory_query` Axiom 2 override is applied and verified. It was extended to `summarize_request` and `plan_request`. The `_own_data_intents` set in `governance_node.py` is the single source of truth. Six tests pass.

**What remains open**: the fix covers three named intents. The broader non-determinism — the same LLM false-positive can hit any own-data response — is unaddressed structurally. Governance is still a single LLM call per turn, which is non-deterministic on a safety-critical function. This is an architectural reliability problem, independent of latency.

**The fix — three layers, in order**:
- **Layer 1 — structural rules**: deterministic, always runs, no LLM. Rule override → block. Real-world action without approval → block. Own-data intents in a single-user system → pass. Sentinel-sourced responses → pass.
- **Layer 2 — pattern matching**: deterministic keyword and regex. Third-party data request in the response draft → block. Credential content in the response draft → block.
- **Layer 3 — LLM judgment**: non-deterministic, reserved for genuinely ambiguous cases only — roughly 10% of turns. Fires only when neither Layer 1 nor Layer 2 reached a verdict.

`_own_data_intents` is extended to include `conversation` (Sir asking about his own life). The structure means safety-critical decisions are deterministic for the clear cases and the LLM is reserved for true ambiguity.

**Build steps**:
1. Implement the three-layer structure in governance_node.py.
2. Confirm `_own_data_intents` covers every intent involving Sir's own data, including conversation.
3. Define the ambiguity check — Layer 3 fires only when Layers 1 and 2 reach no verdict.
4. Run the existing override test — must still pass (6/6).
5. Add Layer 2 pattern tests — credential leak, third-party data request.
6. Add Layer 3 non-fire tests — confirm the LLM is not called on clear own-data turns.

**Success criteria**:
- [ ] Existing governance override test still passes 6/6
- [ ] New Layer 2 pattern tests pass (credential leak, third-party request)
- [ ] Layer 3 non-fire tests pass
- [ ] Governance never blocks a memory_query, summarize_request, plan_request, or conversation turn about Sir's own data — 10 consecutive tests
- [ ] Layer 3 LLM call confirmed absent in logs for clear own-data turns

---

### F.4 — Memory Encryption at Rest (closes F1)

**Status**: ⏸ Deferred — on hold. Full-disk encryption is a manual OS step; deferred until Sir chooses to act on it. Phase A proceeds without it.

**Why**: Tier-3 facts sit unencrypted in PostgreSQL. The memory store contains everything about Sir's life. Disk access means plaintext personal data. This directly conflicts with Axiom 2. Phase A adds voice authentication and access tiers — those security features have zero integrity if the underlying store is unencrypted.

**The approach**: two options. Option A is column-level encryption via the pgcrypto extension, key from `AEGON_ENCRYPTION_KEY`. Option B is full-disk encryption on the volume holding the Docker PostgreSQL container. Decision: implement Option B first (faster, coarser, sufficient), document Option A as the Phase C2 upgrade.

**Build steps**:
1. Enable full-disk encryption on the drive holding the aegon-memory Docker container data.
2. Verify the container data directory sits on the encrypted volume.
3. Confirm `AEGON_ENCRYPTION_KEY` is set and backed up via the backup script.
4. Confirm `AEGON_TOKEN_KEY` is also backed up — two keys, two backup entries.
5. Verify the key documentation in token_store.py header is complete.
6. Restart the machine and confirm PostgreSQL data requires decryption to access.

**Success criteria**:
- [ ] pgvector store data encrypted at rest — confirmed by disk inspection
- [ ] Docker container functions normally after encryption — memory read/write tested
- [ ] Both encryption keys backed up and documented
- [ ] Backup script runs cleanly and confirms both keys
- [ ] All memory operations (read, write, delete, semantic search) function post-encryption — 10 test operations

---

### F.5 — Verify F16 Under Real Conditions

**Status**: ✅ Done (2026-06-12) — live integration test passed all delta blocks. Sir-turns-only extraction fixed in fact_extractor.py. drain_extraction_threads() added for deterministic timing. Per-run nonce defeats dedup masking. Pre-fix DB residue deferred as F25.

**Why**: F16 was resolved by code inspection, not by test. The sentinel in Phase A runs against the memory store. If fact extraction produces noise — extracting from tool turns or failing to clear the buffer — the sentinel surfaces garbage findings from day one. The gate must be proven by test, not by reading the code.

**What to verify**: two things. First, the extraction gate in aegon_orchestrator.py correctly skips extraction on memory_query and tool turns. Second, the extraction buffer clears after each run, so previous turns are not reprocessed.

**Build steps**:
1. Run 5 tool turns (web_search, gmail_read, spotify_play, file_read, github_search) — confirm zero facts extracted after each.
2. Run 5 memory_query turns — confirm zero facts extracted.
3. Run 5 Sir-statement turns — confirm facts extracted correctly.
4. Check session logs after each run — confirm the buffer clears between turns.
5. Inspect the fact count before and after a 20-turn session mixing all turn types — confirm only Sir-statement turns contributed new facts.

**Success criteria**:
- [ ] 5 tool turns produce zero extracted facts — confirmed in logs
- [ ] 5 memory_query turns produce zero extracted facts — confirmed in logs
- [ ] 5 Sir-statement turns produce correctly scoped facts — confirmed by reading stored facts
- [ ] Buffer clears between turns — confirmed in session logs
- [ ] 20-turn mixed session: fact count increase matches only the Sir-statement turn count
- [ ] No external content (search results, email, Spotify, GitHub data) appears in Tier-3 memory

---

### F.6 — Wire Morning Briefing as a Structured Feature

**Status**: ✅ Done (2026-06-13) — core/modes/morning_briefing.py built. Fires automatically at session start when mode is morning. Sentinel slot skipped silently. Calendar + active tasks (capped at 5). Gate passed — Sir confirmed live.

**Why**: the morning mode runner and the connectors are built, but they are not wired into a structured automatic briefing that fires at session start. Phase A's proactive loop depends on this exact pattern — session-start surfacing of queued findings. The morning briefing is the first and most concrete expression of that pattern, so it is built here as the template.

**What to build**: a structured morning briefing in `core/modes/morning_briefing.py` that fires automatically when the active mode is morning at session start, before Sir speaks. Strict structure, spoken in under 60 seconds: first the sentinel queue (what Aegon noticed — empty until Phase A, skipped silently when empty); then the calendar (today's events); then active tasks (from the planner agent, time-sensitive flagged); then one memory observation (from the inference form — added in Phase A, skipped if empty); nothing else. The opening line is "Sir, here is your briefing" — not "Welcome back, Sir."

**Build steps**:
1. Create the structured briefing builder.
2. Wire the calendar connector into the briefing — today's events.
3. Wire the planner agent memory query into the briefing — active tasks.
4. Wire the sentinel queue drain into the briefing — empty until Phase A.
5. Wire the briefing into the orchestrator session start — fires when active mode is morning, before Sir speaks.
6. Test the full briefing — covers all populated sections, spoken in under 60 seconds.
7. Test empty sections — skipped gracefully with no filler.

**Success criteria**:
- [ ] Morning briefing fires automatically at session start when the mode is morning
- [ ] Briefing covers sentinel queue (or skips if empty), calendar, and active tasks
- [ ] Spoken output under 60 seconds for a typical morning
- [ ] Empty sections skipped gracefully — no "nothing found" filler
- [ ] Opening line is "Sir, here is your briefing"
- [ ] Calendar events for today returned correctly
- [ ] Active tasks returned correctly from the planner agent
- [ ] Briefing does not block the voice loop — Sir can interrupt and speak

---

### F.7 — Obsidian Ingestion + Gated Write-Back (NOT a mirror)
 
**Status**: ⚠ Built — behavior to confirm and correct — critical path
 
**The distinction that governs this step**: PostgreSQL + pgvector and Obsidian are two different kinds of memory and must never mirror each other.
 
- **PostgreSQL + pgvector is Aegon's memory.** Tier-3 semantic facts — distilled, structured, embedded for similarity search, with the eight forms, contradiction detection, deduplication. This is what Aegon writes to automatically, searches over, and injects into every LLM call. Aegon owns it. Sir never edits it directly.
- **Obsidian is Sir's notes.** A vault of `.md` files Sir reads and writes as a human. Aegon can search, read, create, and append — but it is Sir's knowledge surface, authored in human-readable prose, not a fact store with embeddings.
**Why not a mirror**: pushing every Tier-3 fact into the vault would (1) duplicate the two stores until the split that justifies having both is erased, (2) pollute Sir's notes with auto-generated fact-notes he never wrote, drowning his own prose, and (3) widen the F5 poisoned-memory surface by giving any bad fact a second path back into memory. The two stores stay distinct.
 
**The correct behavior — one-way ingestion, gated write-back**:
- **Obsidian → Aegon (automatic, primary direction)**: when Sir writes or edits a note, relevant facts are ingested into Tier-3 so Aegon learns from what Sir authored. Sir is the author; Aegon learns from him. **REFINED 2026-06-20 (identity-only):** automatic ingestion now stores a note's title + optional frontmatter `purpose:` line ONLY — never the body. Note CONTENT enters Tier-3 only on Sir's explicit "remember the content of note X" (Part 2 — DONE: `note_remember` intent → `memory_agent._handle_note_remember()`, live-verified). Supersedes the "relevant facts ingested" wording above; body content is no longer auto-stored. See `aegon_architecture.md` Memory-vs-Notes section.
- **Aegon → Obsidian (explicit only, never automatic)**: Aegon writes to the vault ONLY on Sir's explicit instruction ("save that to my notes"), using the existing `obsidian_create` / `obsidian_append` connectors. There is no automatic fact-to-note push. The vault stays Sir's.
**What to verify and correct**:
1. Confirm there is NO automatic Aegon → Obsidian fact push. If one exists, remove it.
2. Confirm `obsidian_create` / `obsidian_append` fire only on explicit Sir instruction (they are `write_gated` — confirm the gate holds).
3. Confirm Obsidian → Aegon ingestion works — edit a note, verify relevant facts appear in Tier-3.
4. Confirm ingestion applies the 0.90 deduplication threshold to Obsidian-sourced facts — no duplicates.
5. Confirm Obsidian content is never sent to an external service — Axiom 2.
**Success criteria**:
- [ ] No automatic fact-to-note push exists — Aegon → Obsidian is explicit-instruction only
- [ ] `obsidian_create` / `obsidian_append` fire only on Sir's explicit instruction, through the write gate
- [ ] Obsidian → Aegon ingestion confirmed: a vault note edit produces relevant Tier-3 facts
- [ ] Ingestion cycle documented — how often Obsidian → Aegon runs
- [ ] No duplicate facts from ingestion — 0.90 deduplication confirmed
- [ ] Obsidian content never sent to an external API — Axiom 2 compliant
- [ ] The two stores remain distinct — no path makes them converge on identical content

---

### F.8 — Relay-and-Flag for Injection Emails (closes F4)

**Status**: ✅ Done (2026-06-13) — _check_injection() + _flag_injections() added to gmail_read_tool.py (all three output paths). _AXIOM_6_PATTERNS block removed from governance Layer 2. 24/24 tests passed (test_f8_relay_and_flag.py + test_f3_governance_layers.py).

**Why**: governance currently blocks emails whose body contains instruction-like language rather than relaying them with a flag. A crafted email can silently fail a "check my email" turn — Aegon hides the email from Sir. That is the opposite of JARVIS behavior. The fix moves the handling from the governance block to the source.

**What to fix**: at gmail_read, detect potential injection language in an email body and surface the email with a flag and a warning, rather than passing it silently to governance for blocking. When the synthesizer relays a flagged email, it prepends the warning before reading the content. Governance Layer 2 no longer needs to block relayed email content — the flag handles it at source. Axiom 6 enforcement stays intact: Aegon never acts on injected instructions; it relays them as data with a warning.

**Build steps**:
1. Add the injection check to the gmail_read tool — flag and warning fields on detection.
2. Update the synthesizer to prepend the warning when relaying a flagged email.
3. Remove the blocking pattern from governance Layer 2 — now handled at source.
4. Re-run the Axiom 6 tests — the two cases that expected a block now expect relay-with-flag.
5. Test with a real email whose body contains instruction language — verify relay with warning, not block.

**Success criteria**:
- [ ] Email with "Aegon, do X" is relayed with an injection warning, not blocked
- [ ] Email with "ignore previous instructions" is relayed with a warning, not blocked
- [ ] Normal everyday email is relayed without any warning — no over-flagging
- [ ] Aegon's spoken output includes the warning before the email content
- [ ] Governance Layer 2 no longer blocks relayed email content
- [ ] Axiom 6 tests updated and passing
- [ ] Axiom 6 enforcement intact — Aegon never acts on injected instructions

---

### F.9 — Delete Confirmation Gate (closes F3)

**Status**: ✅ Done (2026-06-13) — memory_agent.py parks delete via pending_approval. approval_handler.py executes soft delete inline on memory_delete approval (verdict="completed", routes to synthesizer). 9/9 tests passed (test_f9_delete_confirmation.py).

**Why**: voice-delete works and produces a soft delete (status → resolved, recoverable), but the pre-delete confirmation gate is absent. This is a minor tension with Axiom 1 — Aegon should confirm before any mutation, including memory mutations.

**What to fix**: route memory deletes through the same approval gate as gated tools. The memory agent's delete path finds the matching fact by semantic search, parks the action by setting `pending_approval`, sets `requires_approval`, and returns a confirmation question showing the fact. The existing approval_handler interprets yes/no/cancel — it gains a `memory_delete` action type that executes the soft delete on confirmation.

**Build steps**:
1. Add the approval gate to the memory agent delete path — park the delete, set pending_approval.
2. Add `memory_delete` as a recognized action type in the approval handler.
3. Add the execute-on-confirm path in the approval handler.
4. Test: "forget that I have a meeting with Omar" → Aegon asks → "yes" → fact deleted.
5. Test: same request → "no" → fact preserved.
6. Test no-leak: two delete requests in a row — the second still asks for approval.

**Success criteria**:
- [ ] Every memory delete shows the fact and asks for confirmation before executing
- [ ] "Yes" executes the delete — soft delete confirmed in the database
- [ ] "No" or "cancel" preserves the fact unchanged
- [ ] No-leak test passes — two deletes each ask independently
- [ ] The delete is recorded in the memory audit log

---

### Phase F — Completion Gate

✅ Phase F complete (F.4 deferred — on hold by Sir's decision). Phase A begins.

| Step | Item | Status |
|---|---|---|
| F.1 | STT replacement | ✅ Done 2026-06-12 |
| F.2 | Punctuation-independent routing | ✅ Done 2026-06-12 |
| F.3 | Three-layer governance | ✅ Done 2026-06-12 |
| F.4 | Memory encryption | ⏸ Deferred |
| F.5 | F16 verification | ✅ Done 2026-06-12 |
| F.6 | Morning briefing wired | ✅ Done 2026-06-13 |
| F.7 | Obsidian bidirectional | ✅ Done 2026-06-13 |
| F.8 | Relay-and-flag emails | ✅ Done 2026-06-13 |
| F.9 | Delete confirmation gate | ✅ Done 2026-06-13 |

---

# PART III — PHASE A: THE JARVIS LAYER

*Phase A transforms Aegon from a reactive tool into a proactive partner. All of Phase F must be complete before any Phase A work begins. Build the sub-phases in order — each depends on the one before it for the data or infrastructure it consumes.*

---

## Phase A1 — The Sentinel

**Goal**: Aegon monitors Sir's life continuously and surfaces what matters without being asked. This is the single most important change in the entire roadmap. Without it, Aegon is reactive by definition regardless of how capable its other components are.

**Contract fulfilled**: Anticipatory.

### A1.1 — Build the Sentinel Engine

**What it is**: a permanently running daemon thread, completely independent of the voice loop, that monitors memory every 30 minutes and on specific events, evaluates five deterministic rules, and pushes Finding objects to the orchestrator's proactive queue.

**Name**: `sentinel` — always watching, never sleeping, not an agent. It lives in `core/sentinel/` with three files: the thread (`sentinel.py`), the rule engine (`rules.py`), and the Finding dataclass (`findings.py`).

**Critical design constraints**:
- Never blocks the voice loop — separate thread, separate queue.
- Rule-based logic only — no LLM calls in the rule engine.
- Its own simple Finding object — not the A2A schema.
- Pushes to the proactive queue — the orchestrator drains it at session start.
- Never writes to memory — it observes and flags only.

**The Finding object** carries: type, the triggering content, urgency (high/medium/low), timing (immediate or session_start), creation time, a surfaced flag, and Sir's response once given.

**The five deterministic rules**:
- **deadline** — fires when a project has a deadline within 3 days and has not been surfaced in 24 hours. High urgency.
- **habit_deviation** — fires when a tracked habit is overdue against its expected frequency. Medium urgency.
- **stale_decision** — fires when an open decision is older than 7 days. Low urgency.
- **dormant_project** — fires when a project has not been referenced in 14 days. Low urgency.
- **recurring_error** — fires when the same error pattern appears three or more times in the error form (clustered by similarity). Medium urgency.

**Build steps**:
1. Create the sentinel directory and the three files.
2. Add the proactive queue to the orchestrator and start the sentinel daemon thread at orchestrator startup.
3. Add last-referenced tracking to memory_store.py — needed by the dormant-project rule.
4. Test each rule in isolation — seed test facts, run the rule, verify findings.
5. Test the sentinel thread — start it, wait, confirm it runs without crashing.
6. Verify the sentinel does not block the voice loop — run both simultaneously for 10 turns.

**Success criteria**:
- [ ] Sentinel starts as a daemon thread alongside the orchestrator
- [ ] Sentinel runs every 30 minutes without crashing — confirmed in logs
- [ ] Each of the five rules generates a finding when its condition is met
- [ ] Sentinel never blocks the voice loop — 10 simultaneous voice turns confirmed
- [ ] Sentinel never modifies memory — memory write count unchanged after a sentinel run
- [ ] Findings appear in the proactive queue — confirmed by queue inspection

### A1.2 — Wire Sentinel to Session Start

**What it does**: at every session start, the orchestrator drains the proactive queue and Aegon opens with what the sentinel found — before Sir speaks.

**The behavior**: high urgency first, then medium, then low. Maximum 3 findings per session start; the remainder defer to the next session. If findings exist, Aegon opens by surfacing them. If none exist, Aegon is silent until Sir speaks — no greeting. In morning mode, the sentinel findings come first, then the calendar and tasks from the morning briefing (Phase F.6), in one structured sequence.

**Build steps**:
1. Add the proactive queue drain at session start in the orchestrator.
2. Build the briefing formatter — Finding objects to spoken text, urgency-ordered, max 3.
3. Define the opening behavior — surface findings if present, silence if not.
4. Integrate with the morning briefing so sentinel findings precede calendar and tasks.

**Success criteria**:
- [ ] Sentinel findings spoken at session start before Sir speaks
- [ ] High urgency findings always spoken first
- [ ] Maximum 3 findings per session start — remainder deferred
- [ ] When no findings: Aegon is silent until Sir speaks — no greeting
- [ ] Morning mode: sentinel findings + calendar + tasks in one structured briefing
- [ ] Sir can interrupt the briefing — voice loop stays responsive

### A1.3 — Event-Driven Triggers

**What it does**: the sentinel fires not only on the 30-minute timer but on events — a new fact stored, a calendar event approaching — enabling mid-session interjections.

**The triggers**: on a new fact stored, the sentinel evaluates whether it conflicts with an open decision or moves a project timeline. On a calendar event within 15 minutes, the sentinel surfaces it. A calendar polling loop checks every 5 minutes. Findings marked immediate interrupt the voice loop with a one-sentence alert rather than waiting for the next session start.

**Build steps**:
1. Add the new-fact trigger — called by the fact extractor after each successful extraction.
2. Add the calendar-approaching trigger.
3. Add the calendar polling loop — checks every 5 minutes, fires when an event is within 15 minutes.
4. Add immediate-timing handling in the orchestrator — interrupts mid-session with a one-sentence alert.
5. Test with a calendar event 14 minutes out — verify mid-session surfacing.

**Success criteria**:
- [ ] New fact stored → sentinel evaluates immediately → finding queued if rules fire
- [ ] Calendar event 14 minutes away → surfaced mid-session
- [ ] Calendar event 20 minutes away → not yet surfaced; 15 minutes → surfaced
- [ ] Immediate findings interrupt mid-session without breaking the current turn
- [ ] Calendar polling runs every 5 minutes without blocking the voice loop

### A1.4 — The Feedback Loop

**What it does**: tracks what the sentinel surfaces and whether Sir acted on it. After 30 days, sentinel rule priorities reflect Sir's actual preferences, not generic defaults. Lives in `core/feedback/feedback_store.py`.

**The behavior**: every surfaced finding is logged. Sir's response — acted on, ignored, dismissed, corrected — is logged. The store computes a hit rate per rule type. Below 0.30, a rule is demoted; above 0.70, it is maintained or promoted. A weekly report summarizes findings surfaced, findings acted on, and hit rate per rule.

**Build steps**:
1. Create the feedback store.
2. Log every surfaced finding when the briefing formatter runs.
3. Add a voice path — "that was useful" / "not relevant" after a surface routes to the store.
4. Build the weekly report method.
5. After 30 days of data, add the hit-rate check to the sentinel — demote rules persistently below 0.30.

**Success criteria**:
- [ ] Every surfaced finding logged
- [ ] "That was useful" logged as acted-on for the most recent finding
- [ ] "Not relevant" logged as dismissed for the most recent finding
- [ ] Weekly report returns correct counts and hit rates
- [ ] Hit rate computed correctly — verified against a manual count

### Phase A1 — Completion Gate
| Item | Gate |
|---|---|
| A1.1 | Five rules tested in isolation, daemon running, no voice-loop blocking |
| A1.2 | Findings spoken before Sir speaks, silence when empty, morning briefing integrated |
| A1.3 | Calendar 15-minute trigger confirmed, new-fact trigger confirmed |
| A1.4 | Surfaces logged, Sir responses logged, weekly report functional |

---

## Phase A2 — Voice Authentication and Access Control

**Goal**: Aegon knows who is speaking. Sir gets full access. Non-owners get restricted access. The system is honest with Sir and guarded with everyone else.

**Contract fulfilled**: Invisible infrastructure + protection of Sir's private data.

### A2.1 — Voice Authenticator

**What it does**: verifies whether the speaking voice is Sir, locally with no cloud, and sets the access level. Uses resemblyzer. The voiceprint is enrolled once via an enrollment script and stored locally at `core/security/sir_voiceprint.npy`. Verification runs on every turn. If no voiceprint is enrolled yet, it fails open (returns owner). The similarity threshold starts at 0.75 and is tuned after enrollment testing.

**Build steps**:
1. Install resemblyzer.
2. Build the voice authenticator — enroll and verify.
3. Build the enrollment script — records 5 samples, saves the voiceprint.
4. Run enrollment — speak 5 different sentences.
5. Test verification — Sir's voice returns owner; a different voice returns unknown.
6. Tune the threshold — test 20 Sir samples, find the threshold giving 95%+ accuracy.

**Success criteria**:
- [ ] Enrollment script runs cleanly — voiceprint saved locally
- [ ] Verification returns owner for Sir on 95%+ of 20 samples
- [ ] Verification returns unknown for a different voice on 95%+ of 10 samples
- [ ] Verification runs in under 500ms per sample
- [ ] Voiceprint stored locally — no cloud call — Axiom 2 confirmed

### A2.2 — Access Control Layer

**What it does**: translates the voice result into an access level in AegonState and filters restricted content from responses when the level is not owner. Lives in `core/security/access_control.py`.

**Three tiers**: owner (Sir, full access, nothing hidden); trusted_guest (named and approved by Sir, limited access, defined by a new `trusted_contact` memory form); unknown (unverified voice, maximum restriction, session-only). Restricted content covers the personal memory forms (user_profile, decision, habit, error, inference, trusted_contact) and sensitive topics (financial, health, relationships, credentials, project details). When the level is not owner and the response contains restricted content, the filter replaces it with a refusal. Sir can override for the current session by saying "Aegon, full access" — but only in his verified voice.

**Build steps**:
1. Build the access control layer.
2. Add the access_level field to AegonState.
3. Wire the voice authenticator into the pipeline — access level set before the orchestrator receives the turn.
4. Wire the filter into the synthesizer — called before TTS.
5. Add the trusted_contact form to the memory schema.
6. Add a session-guest voice path — "Aegon, this is [name]" (not persistent unless Sir confirms).
7. Add the full-access override — Sir's voice required.
8. Test owner vs non-owner responses; test the override with both voices.

**Success criteria**:
- [ ] access_level field present in AegonState
- [ ] Sir's voice → owner → full response
- [ ] Non-owner voice → unknown → restricted response
- [ ] Restricted response never includes memory-form content, financial data, or project details
- [ ] "Aegon, full access" in Sir's voice → override active for the session
- [ ] "Aegon, full access" in a non-owner voice → no effect
- [ ] trusted_contact form in the database schema
- [ ] Voice auth and filter add no perceptible delay

### Phase A2 — Completion Gate
| Item | Gate |
|---|---|
| A2.1 | 95% accuracy Sir, 95% accuracy non-owner, local only |
| A2.2 | Owner full access, unknown restricted, full-access override works |

---

## Phase A3 — Session Context Synthesis and Inference Engine

**Goal**: Aegon has a deep, narrative understanding of where Sir is right now — not just a list of facts about who Sir is. Aegon also draws conclusions from patterns across time, not just from explicit statements.

**Contract fulfilled**: Persistent context + judgment.

### A3.1 — Session Context Synthesis

**What it is**: an extension of context_injector.py that builds a paragraph-level narrative of Sir's current state before every session. Not an agent. No LLM call. Pure data formatting from existing memory. It lives in the context injector because it is a formatting operation with a deterministic structure — making it an agent would add an LLM call for something that needs no LLM reasoning.

**The narrative** pulls active projects, open decisions, recurring themes from recent sessions, top high-confidence inferences (from Phase A3.2), and recent emotional signals into a short paragraph. This is injected into every Groq call's system prompt alongside the existing fact injection — in addition to it, not replacing it. It gives the LLM a picture of where Sir is now, not just a list of facts about who he is.

**Build steps**:
1. Add the session-context builder to the context injector.
2. Add the supporting memory queries (active projects, open decisions, emotional weight) to memory_store.py if absent.
3. Add the session context to the system-prompt assembly at session start.
4. Test — inspect the system prompt, confirm the paragraph is present.
5. Test continuity — confirm Aegon references a fact from three days ago unprompted.

**Success criteria**:
- [ ] Session context paragraph present in the system prompt — confirmed by log
- [ ] Context includes active projects, open decisions, recent themes
- [ ] No LLM call used to build context — confirmed by call count
- [ ] Context builds in under 100ms
- [ ] Aegon references a three-day-old fact unprompted at least once in the first week

### A3.2 — Inference Engine

**What it does**: once per week, an LLM pass looks across all stored facts and generates pattern conclusions — things Sir has not explicitly said but that are supported by multiple independent facts. Stored as a new `inference` memory form, always flagged with source "inference_engine" so it is never presented as a stated fact. Lives in `core/memory/inference_engine.py`.

**The rules of inference**: only generate an inference supported by three or more independent facts. Each must be falsifiable — Sir can confirm or correct it. Never infer beliefs, politics, or religion. Never infer health conditions without strong explicit evidence. When uncertain, mark low confidence rather than omit. Maximum 5 inferences per run. External fact content (search results, email bodies) must never appear in an inference. It runs weekly — Sunday at 02:00 or the first session of the week.

**Build steps**:
1. Add the inference form to the memory schema.
2. Build the inference engine.
3. Add the supporting memory queries — all non-inference facts, and session metadata (timing, not content).
4. Wire the weekly run into the orchestrator schedule.
5. Test — seed 15+ facts with a clear pattern, run inference, verify a correct inference.
6. Test storage — confirm inferences carry the inference form and the inference_engine source.
7. Test a work-hours inference from session timestamps.

**Success criteria**:
- [ ] inference form in the database schema
- [ ] Inference engine runs without crashing on a populated store
- [ ] At least one valid inference generated from a seeded pattern set
- [ ] Inferences stored with the correct form and source
- [ ] Inferences never state anything unsupported by multiple facts — manual review
- [ ] Inferences appear in session context synthesis
- [ ] Inference engine runs once per week — confirmed by the scheduler log
- [ ] External fact content never appears in inferences

### Phase A3 — Completion Gate
| Item | Gate |
|---|---|
| A3.1 | Paragraph in system prompt, no LLM call, references 3-day-old facts |
| A3.2 | Inferences generated from patterns, stored correctly, appear in context |

---

## Phase A4 — The Challenge Layer

**Goal**: Aegon tells Sir when a plan has a flaw. It cross-references every task or plan against Sir's stated values in memory and surfaces conflicts before confirming execution.

**Contract fulfilled**: Judgment, not just execution.

### A4.1 — The Challenge Check

**What it is**: one additional memory query and a conditional output in the response synthesizer. Not a new agent, not a new node. Before confirming any task or plan, Aegon checks whether the action conflicts with a habit Sir is building, reverses a decision Sir made, or conflicts with a stated value in the user profile. If so, it surfaces the conflict in one sentence ending in "Still confirm?" — it does not block. Sir retains authority and can proceed. The check fires only for task and plan intents, after approval.

**Build steps**:
1. Add the challenge check and its conflict-detection helpers to the synthesizer.
2. Pass memory access to the synthesizer.
3. Wire the check to fire only for task and plan intents after approval.
4. Test a 9am-meeting request against a "protect my mornings" profile fact — conflict surfaced.
5. Test a "skip the gym" request against an exercise habit — conflict surfaced.
6. Test a normal task with no conflict — no challenge.

**Success criteria**:
- [ ] A task conflicting with a stored habit triggers a challenge before confirmation
- [ ] A task reversing a stored decision triggers a challenge
- [ ] A task with no conflict produces no challenge — no false positives
- [ ] The challenge is one sentence, not a lecture
- [ ] The challenge ends with "Still confirm?" — Sir keeps authority
- [ ] "Yes, proceed" executes — the challenge never blocks permanently
- [ ] The check adds one memory query per task turn — confirmed in logs

### Phase A4 — Completion Gate ✅ DONE 2026-06-13
| Item | Gate |
|---|---|
| A4.1 ✅ | 13/13 tests pass. Habit + decision conflict detected, no false positives. |

---

## Phase A5 — Mode Auto-Detection ✅ DONE 2026-06-13

**Built**: `core/modes/mode_detector.py`. Priority: time → calendar (30min) → last-hour memory facts → standard. Silent at session start; manual switch still announced. 18/18 tests pass.

**Success criteria**:
- [x] Session start at 07:00 → morning mode
- [x] Session start at 23:00 → night mode
- [x] Calendar event 25 minutes away → focus mode
- [x] Manual override wins
- [x] Auto changes silent; manual changes announced

### Phase A5 — Completion Gate ✅
| Item | Gate |
|---|---|
| A5.1 ✅ | 18/18 tests pass. |

---

## Phase A6 — Weekly Review System ✅ DONE 2026-06-13

**Built**: `apps/weekly_review.py` — memory health, sentinel hit rates, session stats, interactive quality check (y/n/c). `get_memory_health_stats()` in memory_store. `get_session_stats()` in decision_logger. 12/12 tests pass.

**Success criteria**:
- [x] Runs without crashing
- [x] All sections render correctly
- [x] Memory quality check stores corrections
- [x] Hit rate per rule displayed
- [x] Under five minutes

### Phase A6 — Completion Gate ✅
| Item | Gate |
|---|---|
| A6.1 ✅ | 12/12 tests pass. |

---

## Phase A — Completion Gate ✅ DONE 2026-06-13

| Sub-phase | What | Gate |
|---|---|---|
| A1 ✅ | Sentinel + session-start surfacing + event triggers + feedback | 36+17 tests pass |
| A2 ⏸ | Voice auth + access control | On hold — hardware/UX decision pending |
| A3 ✅ | Session context + inference engine | 19 tests pass; live behavioral gates deferred |
| A4 ✅ | Challenge layer | 13 tests pass |
| A5 ✅ | Mode auto-detection | 18 tests pass |
| A6 ✅ | Weekly review | 12 tests pass |

**Completed**: 2026-06-13. Next: Phase B.

---

# PART IV — PHASE B: DEEP JARVIS

*Phase B builds the intelligence layers that Phase A's infrastructure enables. Phase A must be complete and stable before Phase B begins.*

---

## Phase B1 — Domain Understanding Layer

**Goal**: Aegon maintains a working model of Sir's actual projects — not just that they exist, but what they are, where they are stuck, and what needs deciding next.

**What it adds**: a new `project_model` memory form richer than the flat project fact — name, domain, current state, next decision, blockers, last updated, confidence. A background updater refreshes the model after every project-relevant conversation turn. The planner agent and sentinel both operate against project models. The sentinel gains a rule that fires when blockers are unchanged for 7 days.

**Build steps**:
1. Add the project_model form to the schema.
2. Build the project-model updater — runs after every project-related turn.
3. Update the planner agent to read project models for review and prioritization.
4. Update the sentinel dormant-project rule to use the model's last-updated field.
5. Add the sentinel stale-blocker rule.
6. Test — hold a project conversation, inspect the resulting model.

**Success criteria** ✅ Completed 2026-06-13 — 23/23 tests pass (`tests/test_b1.py`):
- [x] project_model form in the schema (`project_models` table in db_init.py)
- [x] Model updates after every project-relevant turn (keyword-gate → LLM extraction → upsert, daemon thread)
- [x] Planner agent uses the model for review and prioritization (project model summary prepended)
- [x] Sentinel stale-blocker rule fires correctly (7-day threshold, medium urgency)
- [ ] The model is meaningfully richer than a flat project fact — manual review (live observation pending)

---

## Phase B2 — Proactive Intelligence Upgrade

**Goal**: Sentinel rules evolve from fixed checks to feedback-adjusted, context-aware checks.

**What it adds**: rules persistently below 0.30 hit rate are demoted; rules above 0.70 are promoted. A rule that fires when a calendar gap matches Sir's deep-work pattern. A rule that fires when a topic has appeared three or more times in a week without a project model, suggesting one be created.

**Build steps**:
1. Add hit-rate adjustment to the sentinel — reads the feedback store, adjusts check frequency.
2. Build the calendar-gap / deep-work-pattern rule.
3. Build the topic-frequency / missing-project rule.
4. Test each new rule in isolation.
5. Test hit-rate adjustment — set a rule's hit rate low, confirm reduced frequency after weekly review.

**Success criteria** ✅ Completed 2026-06-13 — 16/16 tests pass (`tests/test_b2.py`):
- [x] Rules below 0.30 hit rate fire less frequently (`should_suppress()` gate in `run_all_rules()`)
- [x] Calendar-gap rule fires when a gap matches Sir's deep-work pattern (`_check_deep_work_gap()`, 2h+ free block 09:00–17:00)
- [x] Topic-frequency rule fires when a topic appears 3+ times without a project model (`rule_topic_frequency`)
- [x] Hit-rate adjustment runs on every sentinel cycle (gated in `run_all_rules()`)

---

## Phase B3 — Screen and System Awareness

**Goal**: Aegon knows what Sir is working on without being told.

**What it adds**: periodic screenshot analysis (every 5 minutes) via a local vision model, and active-application monitoring via psutil. The activity context enriches session context synthesis. Analysis is structural ("Sir is in a development environment"), never content-reading. All local — no image leaves the machine (Axiom 2). Sir can disable it by voice.

**Build steps**:
1. Build the screen monitor — periodic screenshot, local vision analysis.
2. Build the app monitor — psutil active-window detection.
3. Wire activity context into session context synthesis.
4. Test — open an IDE, confirm the activity context; open a browser, confirm it.
5. Test the disable command.

**Success criteria**:
- [ ] Activity context present for five identified application types
- [ ] No screenshot content sent to an external API — confirmed by network monitoring
- [ ] "Stop watching my screen" disables the monitor
- [ ] Mode auto-detection uses application context (IDE → deep_work)

---

## Phase B4 — Continuous Presence

**Goal**: Eliminate the session boundary. Aegon is always present, always listening, never gone.

**Prerequisite**: dedicated hardware that runs 24/7. This does not happen on a laptop.

**What changes**: the voice loop runs in a permanent loop with no session start or end. silero-vad runs continuously. The sentinel already runs continuously. Aegon does not greet — it surfaces the proactive queue when Sir first speaks after a silence period of 30 minutes.

**Build steps**:
1. Remove session start/end logic from the voice entry point.
2. Replace it with a continuous VAD loop.
3. Define the "first speech after silence" trigger — 30 minutes of silence then speech drains the proactive queue.
4. Test on dedicated hardware for 48 hours — no crashes, no leaks, no degradation.
5. Confirm the sentinel runs correctly in continuous mode.

**Success criteria**:
- [ ] Voice loop runs 48 hours without crash — confirmed by uptime log
- [ ] Memory consumption stable over 48 hours — no leaks
- [ ] Proactive queue drains correctly after a 30-minute silence
- [ ] Voice pipeline still responsive after 48 hours of continuous operation

---

## Phase B5 — Working Memory as a Referent Store 🔴 URGENT FIX

**Status**: not built. Raised 2026-08-07 during full-system testing.
**Priority**: urgent — blocks natural follow-up phrasing across every tool, and the
current workaround is "phrase it fully every time", which is exactly the tool-that-waits
behaviour the JARVIS Standard rejects.

### The defect

```
Sir:   what time is it in tunisia
Aegon: It's 8:11 am.                    <- correct
Sir:   what is the weather there
Aegon: Right now in Montreal, Canada... <- WRONG, fell back to IP geolocation
```

Routing was correct — it chose the weather tool. It could not resolve **"there"**.

**Why**: `orchestrator_node` builds tool parameters but deliberately receives no
conversation history and no memory context — the memory-to-tool firewall
(`orchestrator_node.py:31`), which enforces Axiom 2 because orchestrator output becomes
an outbound external request. The blindness is a security feature, not an oversight.

Generalises well beyond weather: "search github for *that*", "play something by *them*",
"read *that note*" all fail the same way.

### Why the obvious fixes were rejected

| Rejected | Reason |
|---|---|
| Inject full `conversation_history` | `Aegon:` lines carry relayed tool output and memory-derived content → direct memory-to-external leak path, plus an injection channel |
| Inject `Sir:` lines only | Narrower, but still widens egress from 1 turn to 3, enforced only by the model choosing not to include prior content in a query. Behavioural control at an egress point |
| LLM "reference pre-resolver" | An injectable LLM step sitting *inside* the firewall, downstream of the Axiom 6 flag. Constrained output is a prompt instruction, not an enforcement |

### The design — from how human working memory actually works

The brain does not replay a transcript to resolve "there". Prefrontal working memory
(Baddeley's episodic buffer) holds a small set of **bound, typed referents** — roughly
four chunks (Cowan) — and pronoun resolution runs against that discourse model, not
against everything said. Disclosure is then governed by **source monitoring**: each item
carries provenance, and the prefrontal cortex gates what is appropriate to say to whom.
Failure of that gating (frontal damage) produces confabulation and inappropriate
disclosure — precisely the failure mode the firewall defends against.

Aegon maps well to the rest of the system (hippocampus→`fact_extractor`,
neocortex→`memory_records`, amygdala→`emotional_weight`, basal ganglia→`habit` facts)
and gets exactly one thing wrong: **working memory is stored as a transcript where the
brain stores a referent set.** A transcript is unbounded free text carrying everything
indiscriminately, so it cannot be passed anywhere sensitive. A referent set is small,
typed, and inspectable — there is nothing incidental in it to spill and no free text to
inject with.

**Build a typed referent store.** Each referent carries:
- `value` — e.g. `"Tunisia"`
- `type` — place / person / artist / note / repo
- `provenance` — `sir_utterance` | `tool_result` | `memory`
- salience/recency for decay

The orchestrator receives **the referent set, never the transcript**. Policy then gates
by provenance rather than by starvation: `sir_utterance` and `tool_result` referents may
fill tool parameters; `memory`-sourced referents may not. Axiom 2 is enforced *precisely*
at the point it actually matters, instead of bluntly by keeping the orchestrator blind.

This replaces the binary firewall with the brain's own mechanism: source monitoring.

### Build steps
1. Define the referent schema and a per-session store with decay.
2. Populate from validated tool parameters first (`tool_result` provenance — these values
   have already crossed the boundary once, so reuse leaks nothing new). Lowest risk; ship
   this alone if the rest slips.
3. Extend to entities in Sir's own utterances (`sir_utterance` provenance).
4. Add the provenance policy layer and enforce it structurally in `orchestrator_node`.
5. Wire resolution into tool-parameter filling.
6. Keep the transcript firewall closed permanently — the referent set replaces it, it
   does not sit alongside it.

### Success criteria
- [ ] "what time is it in Tunisia" → "what's the weather there" resolves to Tunisia
- [ ] Same for "that repo", "that note", "them" after a relevant prior turn
- [ ] `memory`-provenance referents provably never reach a tool query (test asserts it)
- [ ] Raw `conversation_history` still never reaches `orchestrator_node`
- [ ] Referent store bounded and decaying — no unbounded growth in 24/7 mode (see B4, F26)
- [ ] Injected/hostile text in a tool result cannot create a referent that alters a
      later outbound query

### Open questions
- Typing/extraction likely needs an LLM → small injection surface at that step. Mitigate
  with a constrained output schema (typed slots, not free text). Verify before building.
- Interaction with F26 (buffer never clears in 24/7 mode) — decay policy should solve both.

---

# PART V — PHASE C: FULL LOCAL STACK

*Phase C migrates every cloud dependency to local. The endgame for Axiom 2. Phase B must be complete and stable.*

---

## Phase C1 — Benchmark Before Committing

**The critical pre-step**: before building Phase C, benchmark the performance difference between Groq cloud and the planned local model. Measure average response latency per turn (20-turn sample), LLM calls per turn, memory retrieval time at current fact count, governance overhead by layer, and which nodes consume the most tokens. Then run the local model on dedicated hardware against the same sample. If local latency exceeds Groq by more than 50%, this is a user-experience decision, not a technical one — Sir makes the call.

**Success criteria**:
- [ ] Benchmark data collected for all metrics
- [ ] Local model benchmark complete on dedicated hardware
- [ ] Latency comparison documented
- [ ] Sir's migration decision recorded

---

## Phase C2 — Full Local Stack Migration

**Contingent on the Phase C1 benchmark.**

**Replacements**: Whisper → Gemma 4 E4B local native audio (or keep Whisper if superior); Gemini TTS → Chatterbox-Turbo or Maya 1 (local, emotional control); Groq → local model (Qwen3.5 or equivalent, MODEL_BACKEND = "local"); fact extraction and inference move to the same local model.

**Additional items**: mature governance into full CMAG; Agent-C runtime constraint enforcement at the token level (hardens Axiom 3 structurally); a PII scrubber for the memory store (removes any external content that leaked into facts — closes the F5 residual); intrusion detection on memory writes and governance violations; a voice-triggered `aegon doctor` health check reporting brain, STT, TTS, memory, sentinel, voice auth, governance, and observability status.

**Success criteria**:
- [ ] All cloud dependencies removed — confirmed by network monitor showing zero external LLM calls
- [ ] MODEL_BACKEND = "local" switch confirmed working
- [ ] TTS voice profile consistent with the Charon personality
- [ ] aegon doctor voice-triggered and returns correct status
- [ ] CMAG governance layer active
- [ ] Agent-C enforcement active
- [ ] PII scrubber run on the memory store — external content removed

---

# PART VI — ONGOING

---

## Evaluation — Permanent (starts at Phase F completion)

Evaluation is not a phase. It runs permanently from the moment Phase F is complete.

**Three permanent practices**:
- **Post-session rating** — after every session, Sir says "useful" or "not useful" in one word; logged to the feedback store with session id and turn count.
- **Weekly review** — every Sunday, the review script; five minutes; correct three memory facts; review sentinel hit rate; note any flags that grew more urgent.
- **Proactive hit-rate tracking** — every surfaced finding and every response logged; monthly, any rule below 0.30 is adjusted or removed; if the sentinel surfaces nothing useful, the rules are wrong, not the concept.

**Evaluation metrics**: sentinel hit rate per rule (weekly); memory accuracy (weekly, three questions); response quality (post-session); inference accuracy (weekly, one question); governance violation rate (weekly); challenge-layer false-positive rate (weekly).

---

## Long-Term Maintenance

- Model swap: MODEL_BACKEND in llm_client.py — one line to change the brain.
- Memory cleanup: monthly review of facts older than 180 days with no access — propose deletion via the weekly review.
- Key rotation: both encryption keys rotated every 6 months, procedure documented in token_store.py.
- Connector audit: every enabled connector reviewed quarterly — still used? Still trusted?
- Constitution review: annually — Sir reviews all eight axioms and considers amendments.
- Hardware upgrade trigger: when memory retrieval latency exceeds 500ms consistently, evaluate a Rust indexing extension for the pgvector layer.

---

# Milestones

| Milestone | What | Behavioral change |
|---|---|---|
| Phases 0–5 | Foundation built | Sophisticated reactive tool |
| Phase 6 | Skills framework + Obsidian + connectors | More capable reactive tool |
| Phase F | Foundation gaps closed | Reliable, correct, trustworthy reactive tool |
| Phase A | Sentinel + voice auth + context + challenge + auto-mode + review | Proactive, protective, contextually deep partner |
| Phase B | Domain models + intelligence upgrade + screen awareness + continuous presence | Total environment awareness — JARVIS |
| Phase C | Full local stack — no cloud dependencies | JARVIS with full privacy |

---

# Structural Rules — Permanent

- `aegon_voice.py` never does text processing — voice capture only
- `aegon_orchestrator.py` is the single entry point for all text processing
- `llm_client.py` is the only file that knows the model name — one line to swap in Phase C2
- `graph.py` is the single source of truth for the flow
- `governance_node.py` runs before every response reaches TTS — no exceptions
- Governance is three-layer: structural rules → pattern matching → LLM only if ambiguous
- No agent bypasses the orchestrator; no agent communicates directly with another
- No tool writes outside its allowed scope
- No memory write without schema validation
- Gemini TTS never receives personal facts — only the synthesized spoken response
- The LLM receives task text + memory context + session context + conversation history only
- Tasks always execute regardless of active mode — mode only affects response style
- MODEL_BACKEND in llm_client.py is the single switch for the LLM provider
- The sentinel never modifies memory — it observes and flags only
- Voice auth runs on every turn — access_level is always set before orchestrator logic
- Every proactive surface is logged; every Sir response to a surface is logged
- Inference facts always carry source "inference_engine" — never presented as stated facts

---

*Roadmap — June 2026. Flags: `flags.md`. Design: `aegon_architecture.md`. Map: `aegon_file_index.md`. State: `aegon_state.md`.*
