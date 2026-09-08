# Aegon — CV / LinkedIn Descriptions

## Short (LinkedIn "Featured project" / headline, ~40 words)
**Aegon — Personal Multi-Agent AI Assistant (JARVIS-style)**
Built a voice-native, multi-agent AI system in LangGraph with real-time speech I/O, long-term semantic memory (PostgreSQL + pgvector), a proactive monitoring daemon, and a governed tool layer enforcing an 8-axiom safety constitution across 20+ integrated tools.

---

## Medium (LinkedIn "About" project entry, ~150 words)
**Aegon — Personal Multi-Agent AI Assistant**
Designed and built a full-stack, voice-first AI assistant modeled on the JARVIS behavioral contract: anticipatory, context-persistent, and capable of independent judgment rather than passive Q&A.

- **Architecture**: LangGraph state machine orchestrating 5 specialized agents (memory, planner, summarizer, task, conversation) through a typed agent-to-agent protocol, with a 3-layer governance engine enforcing a hard-coded, self-immutable safety constitution (8 axioms) before any real-world action.
- **Voice pipeline**: sub-second cloud STT/TTS (NVIDIA Riva) with local VAD (silero), full duplex, <3s round-trip latency.
- **Memory**: three-tier system — working, episodic (encrypted session logs), and semantic (PostgreSQL + pgvector, 8 fact forms, contradiction detection, dedup) — feeding relevance-gated context into every LLM call.
- **Proactive layer**: a always-on sentinel daemon that surfaces findings (deadlines, stale decisions, habit drift) unprompted, with a feedback loop that suppresses low-value alerts over time.
- **Tools**: 20+ gated integrations (Gmail, Calendar, Spotify, GitHub, Obsidian, web/news search) behind an approval-gated, auto-discovering tool registry.

---

## Long (CV bullet points — resume format)

**Aegon — Personal Multi-Agent AI Assistant** *(solo project, ongoing)*

- Architected a voice-native multi-agent assistant on **LangGraph**, orchestrating 5 sub-agents (memory, planner, summarizer, task, conversation) via a typed A2A message protocol and a persistent PostgreSQL-backed checkpointer.
- Designed and implemented a **3-layer governance engine** (deterministic structural rules → pattern matching → LLM-judged edge cases) enforcing an 8-axiom safety constitution — no unapproved real-world actions, no self-modifying rules, privacy-by-default memory — resolving ~90% of turns with zero LLM calls for auditability and cost control.
- Built a **three-tier memory system** (working / episodic / semantic) on **PostgreSQL + pgvector** with local sentence-embedding deduplication, contradiction detection, and relevance-gated context injection — avoiding both context bloat and stale-fact leakage into unrelated conversation.
- Built an **always-on sentinel daemon** implementing 5 proactive-monitoring rules (deadline tracking, habit deviation, stale decisions, dormant projects, recurring errors) with a logged feedback loop that auto-suppresses low-hit-rate alert types.
- Implemented a **real-time voice pipeline**: local VAD (silero) → cloud STT/TTS (NVIDIA Riva, whisper-large-v3 / Chatterbox-Multilingual) achieving ~3s round-trip turn latency, with an LLM provider failover chain (NVIDIA NIM → OpenRouter → local Ollama) for resilience against rate limits and outages.
- Integrated **20+ external tools** (Gmail, Google Calendar, Spotify, GitHub, Obsidian, web/news search) behind a self-auditing tool registry with three permission tiers (read-only / write-gated / always-gated) and per-call approval gating for irreversible actions.
- Hardened the system against **prompt-injection via untrusted content** (e.g., email bodies) — content is relayed with an explicit warning rather than acted on, preserving usability without compromising the "observed content is data, not commands" safety axiom.
- Maintained rigorous engineering discipline throughout: staged rollout across 6 phases with named success-gate criteria, a disaster-recovery rebuild after a full environment loss (rebuilt STT/TTS/LLM provider stack, reconstructed a from-scratch dependency manifest via AST import analysis), and full test coverage per feature (100+ passing unit/integration tests across governance, memory, and routing subsystems).

**Stack**: Python, LangGraph, PostgreSQL, pgvector, NVIDIA Riva (STT/TTS), NVIDIA NIM / OpenRouter / Ollama (LLM), sentence-transformers, resemblyzer (voiceprint auth), Docker, MCP (Model Context Protocol).

---

## One-liner (headline / summary section)
Built Aegon, a governed multi-agent AI assistant with voice I/O, long-term memory, and proactive monitoring — engineered around a self-enforcing 8-axiom safety architecture, not bolted-on guardrails.
