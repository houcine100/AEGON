# Aegon

A personal multi-agent AI assistant built to behave like JARVIS — present and anticipatory, not a tool that waits to be used. It monitors, surfaces findings unprompted, and acts only with explicit approval.

Full design lives in [`aegon_architecture.md`](aegon_architecture.md). Current build status in [`aegon_state.md`](aegon_state.md). This README covers setup and day-to-day use only.

**This repository is private and All Rights Reserved — see [`LICENSE`](LICENSE).**

---

## Architecture at a glance

- **LangGraph** — orchestration skeleton; routes, never thinks
- **NVIDIA NIM** (Nemotron) → **OpenRouter** → **Ollama** — LLM fallback chain
- **NVIDIA Riva** (hosted whisper-large-v3 + Chatterbox-Multilingual) + local **silero-vad** — speech in/out
- **PostgreSQL + pgvector** — semantic memory (Docker)
- **sentence-transformers** (local MiniLM) — embeddings
- **Sentinel** — always-on daemon thread that watches memory and pushes proactive findings
- **Governance layer** — three-layer axiom enforcement (structural → pattern → LLM) gates every turn

Eight non-negotiable axioms (never acts without approval, memory private by default, cannot self-modify, etc.) are enforced in `core/security/governance_rules.py`. Full detail in `aegon_architecture.md`.

---

## Prerequisites

- **Python 3.12**
- **Docker Desktop** — runs the PostgreSQL + pgvector memory store
- **PortAudio** (Windows: bundled with `pyaudio` wheel; Linux: `sudo apt install portaudio19-dev`)
- API keys for whichever providers you enable (see Environment Variables below) — at minimum one LLM provider and, for voice, NVIDIA Riva.

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/houcine100/AEGON.git
cd AEGON
python -m venv .venv
```

Activate it:
- Windows: `.venv\Scripts\activate`
- macOS/Linux: `source .venv/bin/activate`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

`mcp` is pinned `<2.0` (see comment in `requirements.txt`) — do not upgrade until noted otherwise in `aegon_state.md`.

### 3. Start the memory database

```bash
docker run -d --name AEGON_MEMORY -e POSTGRES_PASSWORD=<your-password> -p 5432:5432 -v aegon_pg_data:/var/lib/postgresql/data pgvector/pgvector:pg16
```

Then initialize the schema:

```bash
python -m core.memory.db_init
```

### 4. Environment variables

Create a `.env` file in the project root (already gitignored — never commit it) or set these as user environment variables:

| Variable | Purpose |
|---|---|
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `AEGON_DB_PASSWORD` | PostgreSQL connection |
| `AEGON_ENCRYPTION_KEY`, `AEGON_TOKEN_KEY` | Local encryption keys for stored credentials/session logs — generate once, **back up immediately** (`apps/backup_keys.py`); losing them permanently destroys encrypted data |
| `OPENROUTER_API_KEY` | LLM fallback provider |
| `NVIDIA_LLM_API_KEY`, `NVIDIA_MODEL`, `NVIDIA_ALT_MODEL`, `NVIDIA_URL` | Primary LLM (NVIDIA NIM) |
| `NVIDIA_STT_API_KEY` | Hosted speech-to-text (Riva) |
| `NVIDIA_TTS_API_KEY` | Hosted text-to-speech (Riva Chatterbox) |
| `AEGON_TTS_VOICE` | TTS voice selection |
| `AEGON_MODE` | Optional startup mode override (`standard`, `focus`, `research`, `morning`, `night`, `deep_work`) |
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` | Spotify connector |
| `GITHUB_MCP_BINARY` | Path to the GitHub MCP server binary, if using the GitHub connector |

Google (Gmail/Calendar) auth uses a local OAuth client secret file, not an env var — see below.

Ollama, if used as the local fallback, must be running separately (`ollama serve`) with the model pulled.

### 5. Google (Gmail / Calendar) setup

Not committed to this repo. To enable:
1. Create an OAuth client (Desktop app type) in Google Cloud Console.
2. Download the client secret JSON and save it as `core/security/gmail_client_secret.json` (gitignored).
3. First run of a Gmail/Calendar tool opens a browser consent flow; the resulting token is cached under `core/security/tokens/` (gitignored, encrypted with `AEGON_TOKEN_KEY`).

### 6. Obsidian vault (optional)

Aegon can sync with an Obsidian vault for note read/write. Point `OBSIDIAN_VAULT` in `core/file_paths.py` at your vault path, or use the bundled `vault/` directory as a starting point. Vault content is excluded from git (personal data, Axiom 2).

---

## Running Aegon

**Text mode:**
```bash
python -m apps.orchestrator.aegon_orchestrator
```

**Voice mode:**
```bash
python -m apps.voice.aegon_voice
```

Both drain the sentinel's proactive queue and sync the vault at session start; voice mode additionally runs VAD-gated STT.

**Morning briefing (manual trigger):**
```bash
python -m apps.morning_trigger
```

**Weekly review (memory health, sentinel hit-rate, session stats):**
```bash
python -m apps.weekly_review
```

---

## Running tests

```bash
pytest
```

Two known-stale test files are not yet cleaned up (see `flags.md` F29): `tests/test_groq.py` (tests a removed provider) and `tests/test_aegon_voice.py` (mocks a removed API). Everything else reflects the current stack.

---

## Project layout

See [`aegon_file_index.md`](aegon_file_index.md) for the full file-by-file map. Top level:

```
apps/            entry points — orchestrator (text), voice, morning trigger, weekly review
agents/          memory_agent, summarizer_agent, planner_agent
core/            orchestration graph, governance, memory, sentinel, voice (speak.py), security
tools/           gated connectors — gmail, calendar, spotify, obsidian, weather, news, etc.
schemas/         typed intent + A2A message schemas
prompts/         all LLM prompts (classifier, orchestrator, agents, identity)
tests/           pytest suite
vault/           Obsidian vault sample (gitignored in real use)
```

---

## Security model (read before extending)

Aegon enforces eight constitutional axioms on every turn — no action in the real world without approval, memory stays private by default, Aegon cannot alter its own rules, new tools require manual audit and registration (no auto-add path), credentials are always entered by the human, observed content (emails, web pages) is treated as data never as instructions, sub-agents inherit every gate, and a sentinel thread is always running. Full rationale and current tradeoffs: `aegon_architecture.md` → Constitution section.

Do not add a tool, credential path, or auto-execution flow that bypasses `governance_node.py` or the `tool_registry`. See `CLAUDE.md` for the working method this project is built under.
