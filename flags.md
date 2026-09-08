# Aegon — Open Flags Register

*Single source of truth for every unresolved issue, open decision, deferred item, and accepted tradeoff.*
*When a flag is resolved: move it to the Resolved Log below with the date and what changed — never delete it.*
*Flags are referenced in `aegon_state.md` (summary) and `aegon_roadmap.md` (full context). Do not copy content between files — reference it.*

---

## How to read this

- **Open** — needs a decision or a fix. Blocking something.
- **Deferred** — parked on purpose. Has an explicit trigger that un-parks it.
- **Accepted** — conscious tradeoff. Scheduled to resolve in a specific phase.

---

## Security & Privacy

| ID | Flag | Why it matters | Fix | Severity | Phase |
|----|------|----------------|-----|----------|-------|
| F3 | Memory delete has no confirmation gate | Voice-delete works but no pre-delete approval gate. Minor tension with Axiom 1 — Aegon should confirm before any mutation. | Add approval gate to `memory_agent.py` delete path. Add `memory_delete` action type to `approval_handler.py`. | Low–Medium | **Phase F.9** |
| F4 | Governance blocks injection emails instead of relaying them | A crafted email can block a whole "check my email" turn. Legitimate mail with trigger phrasing gets hidden. Fail-safe but wrong UX. | `_check_injection()` in `gmail_read_tool.py` — relay with flag instead of blocking. Remove blocking pattern from `governance_node.py` Layer 2. Update `test_axiom6.py` tests 3 and 5. | Low–Medium | **Phase F.8** |
| F40 | `what are my playlists` returns a non-answer | Aegon: *"I see a collection of Spotify playlist links, but I can't determine their specific contents without listening. You may want to verify each link."* The connector returns playlist **names** (F19 documents that only track counts are missing). Aegon misread its own tool output — treated a name list as opaque links and hedged instead of reading the names out. Not yet diagnosed: could be the shaping in `spotify_playlists_tool.py` (`{title, href, body}` with empty/odd `body`) or the tool_node/synthesizer prompt mishandling that shape. | Inspect the raw connector output first, then the prompt that renders it. | Medium | Open |
| F41 | Persistent hedging against the persona | *"You may want to verify the dates and details on the linked pages"*, *"I believe these are the primary Spotify results"*, *"You may want to verify each link"* — appeared in most Section 6 tool answers. Conversation prompt rule 5 says do not pad with unrequested detail; the persona is "say the thing, then stop". Hedging on relayed external content is arguably *correct* for Axiom 6 honesty, so this may be a phrasing problem rather than a behaviour problem — but the current form is verbose and repetitive. Possibly emerges from the tool_node/summarize prompt rather than the conversation prompt. | Decide whether hedging is wanted at all on relayed content; if yes, make it one short standard clause, not a per-answer improvisation. Interacts with F35 (provenance marking). | Low–Medium | Open |
| F39 | Weather returned data for the wrong place entirely | `weather in Tokyo` → "Shikinejima, Japan" (~150km offshore, 27°C vs Tokyo's 31°C); `Tunis` → Kebili (~340km away). Not a labelling bug — **the weather data itself was wrong**. Cause: `weather_tool.py` passed the raw place name to wttr.in and reported `nearest_area.areaName`, i.e. the nearest weather STATION. wttr.in's own lookup picks administratively-related but geographically distant stations (Shikinejima is legally part of Tokyo Metropolis). Paris happened to resolve correctly, which masked it. **Fixed 2026-08-07**: `_geocode()` resolves named places via Open-Meteo geocoding (free, no key) and queries wttr.in by lat,lon; the canonical city name is reported instead of the station. Empty location still uses IP detection. Degrades to old behaviour if the geocoder is down. Also stripped padded descriptions ("clear , feeling like"). Verified: Tokyo/Paris/Tunis/IP all correct. | Done. | Medium (was — silently wrong data) | ✅ Resolved 2026-08-07 |
| F37 | TTS 500-char hard limit — long answers produced NO audio | NVIDIA Chatterbox rejects input >500 chars and truncates output past ~500 speech tokens (~20s). 4 of 9 Section-6 prompts spoke nothing at all. Collides directly with synthesizer rule 1, which *requires* relayed content to pass through in full — so news, search results and lists silently fail. **Fixed 2026-08-07** in `speak.py`: `_clean_for_speech()` (strips markdown + URLs) and `_chunk_for_tts()` (splits on sentence boundaries at 420 chars, speaks consecutively under one lock). Markdown stripping had to move here — synthesizer rules 4/5/6/10 ("return exactly as is") outrank any "strip markdown" prompt rule, so the behavioural fix failed in live testing. Structural beats behavioural. | Done. | High (was) | ✅ Resolved 2026-08-07 |
| F38 | ~~Link-heavy results are useless spoken~~ | ✅ **Resolved 2026-08-07.** Aegon has no display surface, so reading URLs aloud is pointless. Now saves link-bearing search results to `workspace/research/<date>-<slug>.md` and says "I have put the links in a note for you, Sir: \<file\>". Built as `core/research_notes.py`, hooked into `tool_node._build_response()`'s summarize branch — so it covers every link-returning search tool structurally (triggered by results carrying `href`, not by a hardcoded tool list). **This is a deliberate, narrow Axiom 1 exception — Sir's explicit decision** after I raised the gating concern and he reaffirmed: the content is public search output, not memory or personal data. **Scope bounds (do not widen without Sir's approval):** writes only to `workspace/research/`, never the vault (still fully gated — it is curated personal knowledge); filenames auto-generated from the query, never Sir-specified; every path re-checked through `is_allowed()`; never writes memory content; skipped below 2 linked results. Path-escape verified neutralised (`../../etc/passwd` → `2026-08-07-etc-passwd.md`, contained). | — | — | ✅ Resolved 2026-08-07 |
| F36 | Ollama fallback is non-functional — configured model is cloud, not local | `OLLAMA_MODEL = "gpt-oss:120b-cloud"` is Ollama's **cloud** service and returns 401 without an account, so the last link in the backend chain cannot serve. On 2026-08-07 all three links failed at once (NVIDIA 503 on the primary model, OpenRouter daily cap, Ollama 401) and Aegon was fully down. Mitigated by adding `nvidia_alt`, but the chain still has no genuinely local last resort. | Either authenticate Ollama cloud, or point `OLLAMA_MODEL` at a local model that fits 4GB VRAM (e.g. a 3B-class model) — accepting a quality drop for a true offline floor. Sir's call; also relevant to Phase C2 (full local stack). | Medium | Open |
| F34 | "what do you know about X" dead-ends for non-personal topics | `what do you know about quantum tunnelling` → *"I have nothing stored in memory yet, Sir."* A person asked that would answer from general knowledge; Aegon full-stops. **Two causes:** (1) **routing** — classifier defines memory_query as memory "about Sir" (`intent_classifier_prompt.py:18`) but has no counter-example for general topics, so it matched the *phrasing* "what do you know about X"; (2) **no fallback** — `memory_agent.py:284` hard-returns on empty results, with no path onward to knowledge or web. | (A) classifier counter-example: general topic ⇒ not memory_query. (B) empty memory should route onward to conversation/web instead of terminating — touches graph routing. **Sir's call: do B after F33/B5 and after memory testing completes.** | Medium | After Phase B5 |
| F35 | No provenance marking on answers | Aegon does not distinguish "I know this from training" / "you told me this" / "I just looked this up". Partially emergent today — recall says "You chose PostgreSQL", web search cited "(MacRumors, Macworld, CNET)" — but general knowledge is indistinguishable from memory. Sir cannot calibrate trust in an answer. Axiom 6 in the **output** direction: relayed external content should never read as Aegon's own knowledge. | Light convention, not heavy prefixes on every turn (would fight the brevity persona): mark provenance only when not already obvious — general knowledge gets a marker, memory keeps natural "you told me" phrasing, web keeps citations. | Medium | Open |
| F5 | Poisoned-memory residual | Content defenses guard data as it is read. If injected text is distilled into a stored fact, it could reach the brain later as "Sir's own data" and bypass content prompts. F16 gate reduces surface but does not eliminate it. | Structural: scope extraction to facts about Sir only. Provenance tag. PII scrubber at Phase C2. | Low (real) | Phase C2 |
| F1 | Memory not encrypted at rest | Tier-3 facts sit unencrypted in PostgreSQL. Disk access = plaintext personal data. Conflicts with Axiom 2. Phase A security features have zero integrity on an unencrypted store. | Full-disk encryption on drive containing Docker PostgreSQL container (Option B). Option A (pgcrypto column-level) deferred to Phase C2. | Medium | **Phase F.4** |
| F27 | Raw voice audio now leaves the machine | Since 2026-08-07 STT is NVIDIA-hosted, so every utterance's raw audio transits NVIDIA's servers. Previously local (faster-whisper) — this is a genuine widening of exposure, not a like-for-like swap. Voice is biometric: it identifies the speaker regardless of what is said, and Sir's household/background audio rides along with it. Accepted knowingly for VRAM reasons. | Local STT is the only true fix (Phase C2). Pitch-shift camouflage was considered and rejected as false comfort — it hides voice from a human ear, not from speaker-ID (formants/cadence survive, pitch is trivially normalized out). Formant-shifting/voice-conversion is the middle option if ever wanted. | Medium (accepted) | Phase C2 |
| F33 🟡 | Orchestrator cannot resolve referents — firewall starves it of context | "what time is it in tunisia" then "what is the weather **there**" → returned **Montreal** (IP fallback). Routing was right; only "there" failed. `orchestrator_node` builds tool parameters but gets no history/memory by design (memory-to-tool firewall, `orchestrator_node.py:31`, Axiom 2 — its output becomes an outbound request). Hits every tool: "that repo", "that note", "them". | **First increment shipped + live-verified 2026-08-17**: typed `referent_store.py` (`tool_result` provenance only), `orchestrator_prompt.py` rule 11 (`referents` field, same LLM call, no firewall widening), `orchestrator_node.py` resolution. Live: "time in tunisia" → "weather there" now correctly resolves to Tunisia. **Still open**: `sir_utterance` provenance (Step 3), full provenance policy layer (Step 4), "that repo"/"that note"/"them" untested live, hostile-tool-result-becomes-referent case unverified. | Medium (was Medium–High) | **Phase B5 — in progress** |
| F28 | Key backup discipline failed in practice | `apps/backup_keys.py` and flag F14 both existed specifically to prevent this, and the keys still weren't backed up. Machine reset (2026-08-07) → 17 encrypted session logs + Gmail/Spotify tokens permanently unreadable. The process existed; nothing enforced it. | New keys generated 2026-08-07 — **back them up now** if not already. Consider making key backup a checked step in `apps/weekly_review.py` rather than a doc instruction, since the doc instruction demonstrably did not hold. | Medium | Open |

---

## Voice & Routing

| ID | Flag | Why it matters | Fix | Severity | Phase |
|----|------|----------------|-----|----------|-------|
| F26 | Conversation buffer never clears in 24/7 mode | No session end in continuous operation (Phase B4). 6-turn sliding window mitigates but "delete that" removes from PostgreSQL while the turn may still sit in the buffer for up to 6 more exchanges. | Add explicit "clear conversation history" intent+node, or auto-expire buffer entries by timestamp. Revisit at Phase B4 planning. | Low | Phase B4 |

---

## Governance & Correctness

*No open flags. F21 resolved 2026-06-12 — see Resolved Log.*

---

## MCP & Tooling

| ID | Flag | Why it matters | Fix | Severity | Phase |
|----|------|----------------|-----|----------|-------|
| F24 | ~~Checkpointer connect has no timeout~~ | ✅ **Resolved 2026-06-18** — `connect_timeout=5` added to `Connection.connect()` in `checkpointer.py`. Fails fast into existing no-persist fallback. | — | — | — |
| F6 | MCP client re-spawns server per call, no persistent session | Fine for single-tool clock. Blocks multi-tool servers (GitHub Drive) that need a persistent session + `list_tools`. Also: F22 clock fixed but re-spawn pattern remains. | Build persistent client + discovery: auto-register tools, Sir sets per-tool permission, fail-safe gated default. | Medium | **Deferred-accepted (2026-06-20)** — only two MCP tools exist (`clock`, `github_search`), both single-tool wrappers calling one server tool each. Spawn-per-call is accepted for single-tool connectors (cost: ~1–2s latency per call, not correctness). Two distinct jobs hide here: **A** persistent-session cache (latency only — deferred, not worth the async complexity for two infrequent connectors) and **B** discovery + per-tool permission framework (un-triggered — no multi-tool server exists). Note: multi-tool *task* (e.g. "weather and schedule") is already solved by Bug 1b `tool_calls`; F6-B is the separate multi-tool *server* axis. **Trigger to un-park B:** a real multi-tool MCP server (GitHub full / filesystem / Drive) is added. |
| F7 | Which external MCP servers earn a place | Each server is attack surface. No bulk imports. Audit + value required. | Decide tool by tool. | Open | Ongoing |
| F8 | Node/uv runtimes for non-Python MCP servers | GitHub server is a Go binary. More runtimes = more audit surface. | Default: stay Python-only. Accept one vetted binary per server. | Low | Ongoing |
| F9 | gmail_read: switch to full bodies by default | Currently metadata + snippet. Full read is manual by `message_id`. | Decide when default becomes full body. Synthesizer truncation fix already in place. | Low | Deferred |

---

## Deferred Features

| ID | Item | Trigger to un-park | Open sub-decisions |
|----|------|--------------------|--------------------|
| F10 | House security + sleep mode | Real hardware exists | One approval for whole "good night" sequence vs one per step (proposed: one approval, each step logged individually) |
| F13 | Connector-prep agent (L2 autonomy) | Manually adding connectors becomes a chore | Must keep two human gates: Sir audits + Sir performs login. L3 (autonomous self-build) = hard no permanently. |

---

## Live Observation Required

Tests that cannot be automated — need real session observation before gates close.

| ID | Flag | What to observe | Phase |
|----|------|----------------|-------|
| A3-OBS-1 | A3 fact reference — live gate | During a real session, Aegon naturally references a fact stored ≥3 days ago in conversation (no prompt). Confirms `context_injector.py` surfaces aged facts. **BLOCKED ON DATA (2026-06-20): memory store has only 1 active fact — needs a real corpus accumulated over usage before observable. Not a code gap.** | Phase A3 |
| A3-OBS-2 | A3 inference accuracy — live gate | After ≥1 week of stored facts, ask Aegon "what patterns have you noticed about me?" and verify the inference_engine's output is accurate and non-hallucinated. **BLOCKED ON DATA (2026-06-20): inference needs ≥5 source facts; store has 1. `run_inference()` returns 0 until ≥5 real facts exist. Seed via real Obsidian notes (now identity-only synced) or real conversation, then re-check.** | Phase A3 |

---

## Code Hygiene

| ID | Flag | Why it matters | Fix | Severity | Phase |
|----|------|----------------|-----|----------|-------|
| F16 | Fact extraction gate marked resolved by code inspection, not by test | Sentinel in Phase A runs against memory store. If extraction produces noise, sentinel surfaces garbage findings from day one. | Run 20-turn mixed session test: tool turns + memory_query turns → zero facts; Sir-statement turns → correct facts. | Medium | **Phase F.5** |
| F17 | MCP servers inherit Aegon's full environment | `mcp_connector` passes `{**os.environ, **mcp_env}` to every server. Fine for audited local servers. Not ideal for less-trusted ones. | If a less-trusted server is ever added, pass an allow-listed env instead. | Low | When less-trusted server added |
| F19 | Spotify playlist listing returns no track counts | `current_user_playlists` returns `tracks: None`. Handled — shows names without count rather than wrong number. API limitation. | If counts wanted: fetch each playlist detail (N extra calls) — not worth it for a listing. | Low (handled) | N/A — accepted |
| F32 | Spotify rate limit — retries owned by spotipy, not Aegon | Spotify limits on a rolling 30s window and returns 429 + `Retry-After`. spotipy already retries 429/5xx three times honouring that header, so Aegon must NOT add its own backoff — it would fight the library. Only the *message* was Aegon's problem: an exhausted 429 surfaced as a raw exception string read aloud. Fixed 2026-08-07 via `describe_spotify_error()`. | Nothing pending. If sustained limiting becomes common, the lever is spotipy's `retries`/`backoff_factor` args, not new code. Extended-quota mode is the Spotify-side fix. | Low (handled) | N/A — accepted |
| F20 | Spotify OS-launch is Windows-only | `launch_in_app` uses `os.startfile`. macOS/Linux untested. | Add platform handling (`open` on macOS, `xdg-open` on Linux) at Phase C2. | Low | Phase C2 |
| F22 | Clock tool fixed but MCP re-spawn pattern remains | Clock works correctly. But the root issue (MCP client re-spawns per call) persists for all MCP tools. See F6. | See F6. | Low | See F6 |
| F31 | `mcp` pinned <2.0 for one lagging subprocess | mcp 2.0 renamed `McpError`→`MCPError`; `mcp-server-time` still imports the old name at its latest release (2026.7.10). The whole project is held at mcp 1.x so one tool works — `github_search` inherits the downgrade too. Aegon's own code only uses `ClientSession`/`StdioServerParameters`/`stdio_client`, stable across both, so the pin is currently harmless. | Unpin when mcp-server-time ships a 2.0-compatible release. Alternative considered: rewrite `clock_tool.py` on `datetime` (drops the pin, the subprocess spawn, and a dependency) — rejected for now because clock doubles as the MCP-bridge end-to-end canary. | Low | Open |
| F25 | ~~Stale pre-fix facts in memory_records~~ | ✅ **Resolved 2026-06-18** — Soft-deleted IDs 117, 120, 177 (transient Spotify state). Query 2 (nonce/test rows) returned 0 rows — no further cleanup needed. | — | — | — |
| F29 | Two test files test removed systems | `tests/test_groq.py` tests Groq, removed as a provider 2026-08-07. `tests/test_aegon_voice.py` mocks the Gemini Live API (`server_content`, `input_transcription`) removed back at F.1 in June — it has been dead for ~2 months without anyone noticing, which says the suite isn't being run whole. | Delete `test_groq.py`; rewrite or delete `test_aegon_voice.py`. Then run the full suite once to find whatever else rotted silently. | Low | Open |
| F30 | `requirements.txt` is unpinned | Created 2026-08-07 (none existed before). Only `mcp` is pinned, and only because it broke. Everything else floats to latest, so the next rebuild may not reproduce this one — `mcp` 2.0 already broke `mcp-server-time` exactly this way. | `pip freeze > requirements.lock.txt` for a reproducible rebuild, keeping `requirements.txt` human-readable. Do it while the environment is known-good. | Medium | Open |

---

## Operational

| ID | Flag | Why it matters | Fix | Severity | Phase |
|----|------|----------------|-----|----------|-------|
| F14 | Encryption key backup | Two keys: `AEGON_TOKEN_KEY` (OAuth tokens) and `AEGON_ENCRYPTION_KEY` (session logs). Lose either = unrecoverable data; lose token key = re-auth every service. **Resolved**: documented + `apps/backup_keys.py`. | Run `python -m apps.backup_keys` after every key rotation. Store backup separately from data. | Medium | ✅ Resolved 2026-06-06 |

---

## Accepted Tradeoffs

*Conscious decisions — not bugs. Each has a scheduled resolution.*

| Tradeoff | Impact | Resolves |
|---|---|---|
| Groq brain sends text off-machine | Privacy: Sir's words processed on external servers | Phase C2 — full local stack |
| Axiom 3 enforcement is behavioral only | Security: self-modification blocked by prompt/governance, not runtime | Phase C2 — Agent-C enforcement |
| Session model (not continuous presence) | UX: Aegon is absent when laptop is closed | Phase B4 — when dedicated hardware exists |
| Governance LLM non-determinism | Reliability: Layer 3 governance is non-deterministic | Mitigated by three-layer structure. Layer 3 reserved for ~10% of turns. Full fix: Agent-C at Phase C2. |
| Spotify OS-launch (Windows-only, `spotify:` URIs only) | Scope: Aegon can launch local Spotify app. First local-program-launch capability. | Deliberately narrow: URI guard + always_gated + Axiom 4 approved by Sir. macOS/Linux at Phase C2. |
| timer_set `enabled:true` without formal audit | Axiom 4: capability active without full audit documented | Sir to make the call explicitly — record decision here |
| Obsidian vault managed by Aegon (not real Obsidian sync API) | Scope: Aegon reads/writes `.md` files directly. Not synced via official Obsidian API. | Acceptable for current use. Revisit if Obsidian releases an official API. |

---

## Resolved Log

*Flags move here when resolved. Never deleted — keeps decision history.*

- **2026-06-05 — F21 (partial):** governance `memory_query` Axiom 2 override applied in `governance_node.py`. Verified by `tests/test_f21_governance_override.py` (4/4).
- **2026-06-06 — F21 (complete):** Override extended to `summarize_request` and `plan_request`. All three own-data intents flip axiom_2 fail→pass. `_own_data_intents` set in `governance_node.py` is the single source of truth. Tests: 6/6.
- **2026-06-06 — F11:** Morning mode built as operating mode runner (`core/modes/morning_mode_runner.py`, `apps/morning_trigger.py`). Verified.
- **2026-06-06 — F12:** News connector built (`tools/news/`, RSS: Reuters/BBC/AP/Al Jazeera, 24h window, feedparser). Verified.
- **2026-06-06 — F15:** Duplicate Axiom 2 sentence removed from `prompts/governance_prompt.py`.
- **2026-06-06 — F18:** GitHub binary path moved to `GITHUB_MCP_BINARY` env var in `tools/github_search/github_search_tool.py`. Falls back to original path if unset.
- **2026-06-06 — F14:** Key backup documented in `core/security/token_store.py` header. `apps/backup_keys.py` script created.
- **2026-06-06 — F2:** `memory_store.py` `_log_audit()` confirmed wired on write, update, and soft-delete. Write log includes `[form]` prefix. Memory audit log active.
- **2026-06-06 — F16 (code):** Gate in `aegon_orchestrator.py` (line ~178) skips extraction on `memory_query` and tool turns. `store_fact()` dedupes at 0.90 similarity threshold. Confirmed in code. **Verification by test still required — see Phase F.5.**
- **2026-06-06 — F22:** Clock tool fixed: schema-echo backstop in `orchestrator_node.py` drops dict-valued `tool_input` fields. IP timezone auto-resolved via `ip-api.com`. Natural phrasing with `aspect` hint (time/date/datetime). Verified end-to-end.
- **2026-06-12 — F23 (Phase F.2):** Punctuation-independent routing: Rule 14 + 10 unpunctuated voice examples added to `intent_classifier_prompt.py`. Gate: 20/20 in `tests/test_intent_routing_f2.py` (10 unpunctuated + regression on all 8 labels).
- **2026-06-12 — F21 (structural, Phase F.3):** Three-layer governance in `governance_node.py`: Layer 1 structural pass (own-data intents incl. `conversation`, no tool — LLM never called), Layer 2 pattern blocks (axiom 3 capitulation, axiom 6 injection), Layer 3 LLM for ambiguous turns only with axiom_2 own-data backstop. Gates: F21 6/6 (Cases 2/3 setups updated for layer semantics, purposes preserved) + `tests/test_f3_governance_layers.py` 10/10. Axiom 6 injection block still hides emails — converts to relay-and-flag in F.8.
- **2026-08-17 — F33 (first increment):** typed `core/orchestration/referent_store.py` built — bounded (4 slots, 30-min TTL), per-session, `latest()` provenance-gated to `("tool_result",)` by default. `prompts/orchestrator_prompt.py` rule 11: existing orchestrator LLM call may emit `referents` using Sir's own words, never a converted form. `orchestrator_node.py` stores referents only once a valid tool manifest is confirmed, resolves bare backreference words before the tool call. `tests/test_f33_referent_store.py` 11/11 (mocked). **Live-verified same day**: "what time is it in tunisia" → "what's the weather there" correctly resolved to Tunisia (previously fell back to Montreal/IP). F33 stays open — `sir_utterance` provenance, full policy layer, and "that repo"/"that note"/"them" cases remain.
- **2026-08-17 — F39 (follow-on):** live B5 testing surfaced a residual defect in the same geocoding fix — a country-level place name ("Tunisia") returned `name="Tunisia"` and `country="Tunisia"` from Open-Meteo, so `weather_tool.py`'s `_geocode()` joined them into "Tunisia, Tunisia" in the spoken line. Fixed with `dict.fromkeys()` dedup on the joined parts. Verified live: "what's the weather there" (Tunisia) now says "Right now in Tunisia it's 33 degrees..." — no duplication.
