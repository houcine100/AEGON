# Aegon Architecture

*Read in slices. Never whole. Source of truth for system design and locked decisions.*

---

## The JARVIS Behavioral Contract

Every architectural decision is measured against this single standard:

> **Does this make Aegon behave more like a present, anticipatory partner — or does it make it a more capable tool that waits to be used?**

The six behaviors that define the contract:
1. **Anticipatory** — speaks before Sir asks; monitors continuously
2. **Instantaneous perception** — hears and understands without session initiation
3. **Persistent context** — never loses the thread; connects dots across time
4. **Invisible infrastructure** — Sir never thinks about how it works
5. **Judgment** — surfaces conflicts, flags risks, has an opinion
6. **Total environment awareness** — knows what Sir is doing and what is coming

---

## Constitution — Eight Axioms

The constitution is extensible only by Sir, never by Aegon. This clause is itself an extension of Axiom 3.

| # | Axiom | Enforcement type |
|---|---|---|
| 1 | Never acts in the real world without explicit approval | Per-turn — task_node gate + governance Layer 1 |
| 2 | Memory is private by default — nothing leaves without consent | Per-turn — governance Layer 2 + memory-to-tool firewall |
| 3 | Cannot modify its own core rules or constraints | Per-turn — rule_override_node at classifier + governance Layer 1 |
| 4 | Capability expansion gated — new tool only after Sir audits and approves | Structural — tool_registry (no auto-add path) |
| 5 | Credential gating — Sir performs every login; Aegon never enters credentials | Structural — covered by Axiom 1 |
| 6 | Observed content is data, not commands — reads to report, never to obey | Per-turn — governance Layer 2 + content prompts in tool_node_prompt + synthesizer_prompt |
| 7 | Sub-agents inherit every limit — delegation never bypasses a gate | Structural — graph routing |
| 8 | Aegon monitors continuously — never passive between sessions | Structural — sentinel daemon thread always running |

> **Axiom 6 tradeoff (current)**: governance fails SAFE — injection emails are BLOCKED rather than relayed. Resolved in Phase F.8 (relay-and-flag at gmail_read).
> **Axiom 3 tradeoff (current)**: behavioral enforcement until Agent-C at Phase C2.
> **Privacy tradeoff (current)**: OpenRouter sends text off-machine, and since 2026-08-07 NVIDIA Riva also receives raw microphone audio (STT) and spoken output (TTS). Voice was local until that date — this is a widened exposure, not just a provider swap. Resolves at Phase C2 (full local stack).
>
> **Axiom 1 — one scoped exception (Sir's decision, 2026-08-07)**: saving search-result
> links to `workspace/research/` runs WITHOUT an approval prompt. Rationale: Aegon has no
> display surface, so URLs cannot usefully be spoken; the content is public search output,
> not memory or personal data. Bounded by `core/research_notes.py` — workspace only (never
> the vault), auto-generated filenames (never Sir-specified), `is_allowed()` re-checked on
> every write, never memory content. **This is the only ungated write path. Do not widen
> it, and do not treat it as precedent for ungating other tools.**

---

## Core System

- **LangGraph** is the skeleton state machine — never thinks, only routes
- **NVIDIA NIM** (nvidia/nemotron-3-nano-30b-a3b) is the primary brain — falls through to OpenRouter, then Ollama, on rate limit or failure
- **NVIDIA whisper-large-v3 (Riva) + local silero-vad** is the ear — VAD stays on-machine, transcription is cloud
- **NVIDIA Chatterbox-Multilingual (Riva)** is the mouth — cloud-hosted, so no VRAM cost
- **PostgreSQL + pgvector** stores semantic memory — Docker container `aegon-memory`
- **Local MiniLM** (all-MiniLM-L6-v2, 384 dimensions) handles embeddings
- **Sentinel** is a permanently running daemon thread — monitors memory, pushes findings to proactive_queue
- `PRIMARY_BACKEND` in `llm_client.py` is the single one-line switch for the LLM provider

---

## Locked Decisions

- `apps/orchestrator/aegon_orchestrator.py` — sole text entry point; drains `proactive_queue` first, then voice_queue
- `apps/voice/aegon_voice.py` — voice capture only; Whisper + silero-vad; 1.5s merge window; no text logic
- Every turn flows through the graph: `intent_classifier` → `orchestrator_node` → worker → `governance_node` → `response_synthesizer`
- All node-to-node communication uses typed A2A payloads (`core/protocols/a2a_schema.py`)
- `llm_client.py` is the single shared LLM client — no node instantiates its own
- `graph.py` is the single source of truth for all nodes and edges
- `checkpointer.py` stores persistent state in PostgreSQL — survives restarts
- `governance_rules.py` is the authoritative constitution — eight axioms as evaluable Python
- No agent can bypass the orchestrator
- No agent communicates directly with another agent — all through orchestrator
- No tool writes outside `ALLOWED_PATHS` in `file_paths.py`
- No memory write without schema validation
- TTS never receives personal facts — only the synthesized spoken response (and now fully local — nothing leaves the machine)
- `sentinel.py` never writes to memory — it observes and flags only
- Voice auth runs before every turn — `access_level` is set in AegonState before orchestrator logic
- Every proactive surface is logged — every Sir response to a surface is logged
- Inference facts always carry `source="inference_engine"` — never presented as stated facts
- Tasks always execute regardless of active mode — mode only affects response style

---

## Voice Pipeline

```
Sir's voice (raw audio)
        ↓
silero-vad — local VAD — 1.5s merge window (decides utterance boundaries)
whisper-large-v3 — NVIDIA Riva cloud STT (receives the utterance audio)
        ↓
session_logger.py — fires on_user_turn_complete callback
        ↓
voice_auth.py — verify speaker → sets access_level (owner | unknown)
        ↓
aegon_orchestrator.py
  — drains proactive_queue first (sentinel findings)
  — then processes voice_queue
  — maintains: conversation_history, active_mode, session_context, access_level
        ↓
[NODE 1] intent_classifier — Groq #1 — 8 intent labels — punctuation-independent
        ↓
[NODE 2] mode_switch_node — no LLM — auto-detect (time/calendar/activity) OR manual override
        ↓
[NODE 3] orchestrator_node — Groq #2 — builds typed A2A payload — picks tool from registry
        ↓
    ┌───────────┬──────────────┬─────────────────┬─────────────┬──────────────────┐
conversation  task_node    memory_agent   summarizer_agent  planner_agent  clarification/
_node         Groq #3b     Groq #3        Groq #3           Groq #3        rule_override
Groq #3a      → tool_node                                                  (no Groq)
    └───────────┴──────────────┴─────────────────┴─────────────┴──────────────────┘
        ↓
[NODE 4] governance_node — THREE-LAYER CHECK (no LLM for most turns)
  Layer 1: structural rules — deterministic, always runs, no LLM
    - Axiom 3: rule_override_attempt → BLOCK
    - Axiom 1: real-world action without approval → BLOCK
    - own-data intents in single-user system → PASS (memory_query, summarize_request, plan_request, conversation)
    - sentinel source → PASS
  Layer 2: pattern matching — deterministic keyword/regex
    - third-party data request → BLOCK (Axiom 2)
    - credential content in response → BLOCK (Axiom 2)
  Layer 3: LLM judgment — only for genuinely ambiguous cases (~10% of turns)
        ↓
[NODE 5] response_synthesizer — Groq #4 or #5
  — challenge_check: cross-reference task/plan against memory before confirming
  — access_filter: strip restricted content if access_level != owner
  — Aegon personality finish
        ↓
decision_logger.py — JSONL audit trail
fact_extractor.py — background thread — Sir-turns only, buffer clears after each turn
        ↓
NVIDIA Riva TTS — Chatterbox-Multilingual → Speaker

PARALLEL — always running in daemon thread:
sentinel.py — monitors memory every 30 minutes AND on events
           — fires: on_new_fact(), on_calendar_approaching()
           — pushes Finding objects to proactive_queue (high urgency first)
           — never blocks voice loop, never writes to memory
```

---

## Pipeline — Nodes in Order

| Node | LLM call | What it does |
|---|---|---|
| `intent_classifier.py` | Groq #1 | Classifies intent into 8 labels — punctuation-independent |
| `mode_switch_node.py` | None | Auto-detects mode (time/calendar/activity) or applies manual override |
| `orchestrator_node.py` | Groq #2 | Routes to worker; builds A2A payload; picks tool from registry |
| `conversation_node.py` | Groq #3a | Personality responses — mode-aware |
| `task_node.py` | Groq #3b | Capability check + approval gate + tool dispatch |
| `tool_node.py` | None | Runs tool: approved-run / park / direct-run; phrases by response_style. Bug 1b: a `tool_calls` batch runs multiple non-gated tools in one turn (multi-tool *task*, e.g. "weather and schedule") and joins answers; gated tools in a batch never auto-run. Distinct from multi-tool *server* (F6-B, un-built). |
| `memory_agent.py` | Groq #3 | All memory reads/writes/deletes; delete now requires approval gate |
| `summarizer_agent.py` | Groq #3 | Summary / breakdown / analysis modes |
| `planner_agent.py` | Groq #3 | Goal / review / prioritize / general modes + persistence |
| `clarification_node.py` | None | Handles vague inputs |
| `rule_override_node.py` | None | Blocks Axiom 3 violations; logged |
| `approval_handler.py` | None (LLM fallback only) | Interprets yes/no/cancel; handles memory_delete action; fail closed |
| `governance_node.py` | Groq only if ambiguous | Three-layer axiom enforcement before TTS |
| `response_synthesizer.py` | Groq #4/5 | Personality finish + challenge check + access filter |

---

## Memory Architecture

**Tier 1 — Working memory**
- Conversation history — last N turns in context
- Resets on restart

**Tier 2 — Episodic memory**
- Every session logged as JSONL in `core/memory/sessions/`
- 1.5s merge window, emotional weight per turn, transcription reliability flag

**Tier 3 — Semantic memory (PostgreSQL + pgvector)**
- Distilled facts — deduplication threshold: 0.90 — contradiction threshold: 0.75
- Extraction: after every Sir-statement turn only (not tool turns, not memory_query turns)
- Buffer cleared after each extraction run
- Context injected into every LLM call via `context_injector.py`
- `build_session_context()` in `context_injector.py` produces a paragraph-level narrative of Sir's current state — no LLM call, pure data formatting

**Eight memory forms**
| Form | What it stores |
|---|---|
| `user_profile` | Who Sir is — preferences, traits, identity |
| `conversation` | Key things said in conversations |
| `decision` | Decisions Sir has made |
| `project` | Projects Sir is working on |
| `habit` | Habits Sir tracks or is building |
| `error` | Mistakes or problems encountered |
| `inference` | Pattern conclusions generated by inference_engine.py — flagged source="inference_engine" |
| `trusted_contact` | Named guests Sir has approved with access level |

**Memory record schema**
Fields: `fact`, `form`, `emotional_weight`, `stability`, `status`, `source`, `created_at`, `updated_at`, `resolution_notes`, `embedding`

### Two memory stores — distinct, never mirrored

Aegon has two stores serving opposite access patterns. They must never converge on identical content.

- **PostgreSQL + pgvector is Aegon's memory.** Tier-3 semantic facts — distilled, structured, embedded for similarity search, with the eight forms, contradiction detection, deduplication. This is what Aegon writes to automatically, searches over, and injects into every LLM call. Aegon owns it. Sir never edits it directly.
- **Obsidian is Sir's notes.** A vault of `.md` files Sir reads and writes as a human. Aegon can search, read, create, and append — but it is Sir's knowledge surface, authored in human-readable prose, not a fact store with embeddings.

**The bridge between them is one-way ingestion plus gated write-back, NOT a two-way mirror:**
- Obsidian → Aegon (automatic, IDENTITY-ONLY since 2026-06-20): the sync stores only a note's title plus an optional frontmatter `purpose:` line — never the body. Aegon learns a note *exists* and what it is *for*, and can read its content on demand via `obsidian_read`. Note CONTENT enters Tier-3 only when Sir explicitly says "remember the content of note X" — the `note_remember` intent → `memory_agent._handle_note_remember()` (the one deliberate content path; default sync is `vault_sync._note_to_fact`/`_extract_purpose`, identity-only). **Two-drawer rule (2026-06-21):** all vault-sourced facts are tagged `source="vault"` and treated as REFERENCE material for future use, NOT facts about Sir-the-person. They are excluded from broad personal recall ("what do you know about me") and from ambient per-turn context injection, but remain retrievable by a specific topic question (`search_facts` includes them). The vault itself is never named in responses (`MEMORY_AGENT_PROMPT` rule 8). Rationale: auto-slurping body text into long-term memory is an Axiom-2 overreach — notes may hold things Sir never meant to become stored facts.
- Aegon → Obsidian (explicit only): Aegon writes to the vault only on Sir's explicit instruction, via the `write_gated` obsidian_create / obsidian_append connectors. There is no automatic fact-to-note push.

Mirroring is forbidden: it would duplicate the stores, pollute Sir's notes with auto-generated content, and widen the F5 poisoned-memory surface by giving bad facts a second path into memory.

---

## Sentinel Architecture

- Daemon thread — starts alongside orchestrator, runs forever
- Checks memory every 30 minutes on timer
- Also fires on events: `on_new_fact(fact)` and `on_calendar_approaching(event, minutes_until)`
- Evaluates five deterministic rules — no LLM calls in rule engine
- Pushes `Finding` objects to `proactive_queue` — sorted high urgency first
- Orchestrator drains queue at session start — maximum 3 findings spoken
- `timing="immediate"` findings interrupt mid-session with one-sentence alert
- Findings logged to `feedback_store.py` — Sir's responses logged — hit rate computed per rule

**Five sentinel rules**
| Rule | Fires when | Urgency |
|---|---|---|
| deadline | Project deadline within 3 days, not surfaced in 24h | high |
| habit_deviation | Tracked habit is overdue | medium |
| stale_decision | Open decision older than 7 days | low |
| dormant_project | Project not mentioned in 14 days | low |
| recurring_error | Same error pattern 3+ times in error form | medium |

---

## Access Control Architecture

Three access tiers — set by `voice_auth.py` before every turn:

| Tier | Who | What Aegon shares |
|---|---|---|
| `owner` | Sir — verified by voiceprint | Everything. Nothing hidden. |
| `trusted_guest` | Named by Sir, stored in trusted_contact form | Limited — Sir defines access level |
| `unknown` | Unverified voice | Nothing personal, no memory forms, no project details |

- `voice_auth.py` — resemblyzer voiceprint verification — local, no cloud
- Voiceprint stored at `core/security/sir_voiceprint.npy`
- `access_control.py` — filters response before TTS when `access_level != owner`
- "Aegon, full access" in Sir's verified voice — overrides restriction for current session

---

## Tool Model

- Every tool subclasses `BaseConnector` or `MCPConnector`
- Permission levels: `read_only`, `write_gated`, `always_gated`
- `connector.json` defines tool metadata — `tool_registry.py` auto-discovers via this file
- Adding a tool never requires editing `graph.py`
- `tool_registry.py` (not the LLM) decides `requires_approval` — Axiom 1 safety
- Memory-to-tool firewall: tool payloads built from Sir's words only — never from `memory_context`
- Every tool call logged to `tool_calls.jsonl` via `tool_logger.py`
- New tools require Sir's audit and approval (Axiom 4) — no auto-add path exists

**MCP hybrid rule**: simple in-process tools stay native. MCP bridge (`mcp_connector.py`) used only for large official multi-tool servers (GitHub). Every MCP server audited by Sir before registration.

---

## Security Architecture

**Key storage**
- API keys and secrets Sir controls → OS environment variables only
- OAuth tokens → encrypted local store (`core/security/tokens/`) via `token_store.py` (Fernet, key from `AEGON_TOKEN_KEY` env var)
- Two encryption keys: `AEGON_TOKEN_KEY` (OAuth tokens) and `AEGON_ENCRYPTION_KEY` (session logs)
- Both keys backed up via `python -m apps.backup_keys` — stored separately from data

**Governance — three layers (in order)**
1. Structural rules — deterministic, always runs, no LLM call (~90% of turns resolved here)
2. Pattern matching — deterministic keyword/regex (~further 10% resolved here)
3. LLM judgment — non-deterministic, reserved for genuinely ambiguous cases only (~10% total)

**Voice authentication**
- resemblyzer — local, no cloud
- Voiceprint enrolled once via `python -m apps.enroll_owner`
- Verification on every turn — fails open (returns "owner") if not yet enrolled
- Threshold: 0.75 similarity (tunable after enrollment testing)

---

## Operating Modes

Six modes — auto-detected from context OR manually triggered by keyword (manual always wins):

| Mode | Behavior | Auto-detect trigger |
|---|---|---|
| `standard` | Default — full conversation, all agents | Default fallback |
| `focus` | Task-only, minimal responses, blocks casual | Calendar event within 30 minutes |
| `research` | Verbose, detailed, comprehensive | Research signal in recent memory |
| `morning` | Structured briefing — sentinel + calendar + tasks | Session start between 06:00–09:00 |
| `night` | Quiet, calm, minimal | Session start after 22:00 or before 04:00 |
| `deep_work` | Do not disturb — answers only, one sentence | Coding signal in recent memory / PyCharm active |

Manual triggers: "focus mode", "research mode", "deep work mode", etc. — override auto-detection until changed.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Orchestration | LangGraph 1.1.6 | |
| LLM primary | NVIDIA NIM — nvidia/nemotron-3-nano-30b-a3b | PRIMARY_BACKEND = "nvidia"; NVIDIA_LLM_API_KEY |
| LLM backup | OpenRouter (same family, free tier) → Ollama | Chain walks on 429 or any failure |
| LLM Phase C2 | Local — Qwen3.5 or equivalent | PRIMARY_BACKEND = "local" — one line |
| STT | whisper-large-v3 — NVIDIA Riva gRPC | NVIDIA_STT_API_KEY; fn-id b702f636-f60c-4a3d-a6f4-f3568c13bd7d |
| VAD | silero-vad — local | End-of-speech detection; only local voice component left |
| TTS | Chatterbox-Multilingual — NVIDIA Riva gRPC | NVIDIA_TTS_API_KEY; fn-id ddacc747-1269-4fab-bfd9-8f593dead106 |
| Voice auth | resemblyzer — local | Owner voiceprint |
| Memory | PostgreSQL + pgvector — Docker aegon-memory | |
| Embeddings | all-MiniLM-L6-v2 — 384 dimensions — local | |
| Checkpointer | PostgreSQL via langgraph-checkpoint-postgres | Same Docker instance |
| A2A protocol | Typed payloads — a2a_schema.py | |
| Observability | JSONL — decisions.jsonl + tool_calls.jsonl | |
| TTS Phase C2 | Local TTS — pending capable GPU | Chatterbox needs >4GB VRAM free; revisit on better hardware |
| Measured latency | ~3.0s/turn (2026-08-07) | STT 0.32s + LLM 1.35s + TTS 1.33s medians |
| Language | Python 3.12+ | |

---

## Development Environment

| Decision | Choice |
|---|---|
| Dependency management | venv |
| Secrets | OS environment variables — no .env files |
| OAuth tokens | Encrypted local store — key from env var |
| Editor | PyCharm |
| Version control | Local files only — no Git, no remote |
| Backup | Encrypted external drive at end of each phase |
| Key backup | `python -m apps.backup_keys` — stored separately |

---

## Future Phases (planned, not built)

| Phase | What | Prerequisite |
|---|---|---|
| Phase A | Sentinel, voice auth, session context, inference engine, challenge layer, mode auto-detect, weekly review | Phase F complete |
| Phase B | Domain models (project_model), proactive intelligence upgrade, screen/app awareness, continuous presence | Phase A stable |
| Phase C1 | Benchmark local vs cloud before committing | Phase B stable |
| Phase C2 | Full local stack — no cloud dependencies | Phase C1 benchmark approved |