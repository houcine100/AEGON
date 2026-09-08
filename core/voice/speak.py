# core/voice/speak.py
# Aegon's single mouth — NVIDIA Riva (Chatterbox-Multilingual, DGX Cloud-hosted).
# Every spoken line goes through here: conversation turns, briefings, reminders,
# timers. There is no other TTS path.
#
# Runs off-machine (cloud, NVIDIA-hosted) — local Chatterbox was tried and
# reverted earlier (4GB GPU couldn't hold Whisper + a local TTS model at once).
# This is the same model family, hosted, so that VRAM limit no longer applies.
# The API key is read from the NVIDIA_TTS_API_KEY environment variable — never hardcoded.

import os
import re
import threading

import pyaudio
import riva.client

_RIVA_SERVER = "grpc.nvcf.nvidia.com:443"
_FUNCTION_ID = "ddacc747-1269-4fab-bfd9-8f593dead106"  # chatterbox-multilingual-tts

_auth = riva.client.Auth(
    uri=_RIVA_SERVER,
    use_ssl=True,
    metadata_args=[
        ["function-id", _FUNCTION_ID],
        ["authorization", f"Bearer {os.environ.get('NVIDIA_TTS_API_KEY')}"],
    ],
)
_tts_service = riva.client.SpeechSynthesisService(_auth)

# Voice is env-tunable so it can be auditioned without code edits.
TTS_VOICE = os.environ.get("AEGON_TTS_VOICE", "Chatterbox-Multilingual.en-US.Male")
LANGUAGE_CODE = "en-US"
SAMPLE_RATE = 22050  # Riva TTS default — LINEAR_PCM, 16-bit, mono

# Chatterbox rejects input over 500 chars outright, and truncates output past ~500
# speech tokens (~20s). Long relayed content (news, search results, lists) blows both,
# producing NO audio at all. So we clean and chunk here rather than shortening replies:
# the synthesizer is required to relay content in full, and that requirement is correct.
MAX_TTS_CHARS = 420  # headroom under 500 — chunk, never truncate

# Markdown must die here, not in the prompt. The synthesizer's "return it exactly as is"
# rules outrank any "strip markdown" instruction, so asking the LLM does not work.
# Deterministic beats behavioural.
_MD_PATTERNS = [
    (re.compile(r"```[\s\S]*?```"), " "),            # fenced code blocks
    (re.compile(r"`([^`]*)`"), r"\1"),               # inline code
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),         # bold
    (re.compile(r"(?<!\w)\*([^*\n]+)\*(?!\w)"), r"\1"),  # italics
    (re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)"), r"\1"),    # underscore italics
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),    # headings
    (re.compile(r"^\s*[-*+]\s+", re.M), ""),         # bullet markers
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),   # [label](url) -> label
]
# A raw URL read aloud is a string of gibberish. Drop it from SPEECH only —
# the printed transcript still shows the full link.
_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def _clean_for_speech(text: str) -> str:
    """Strip markdown and URLs so nothing symbolic gets read aloud."""
    for pattern, repl in _MD_PATTERNS:
        text = pattern.sub(repl, text)
    text = _URL_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _chunk_for_tts(text: str, limit: int = MAX_TTS_CHARS) -> list:
    """Split into <=limit pieces on sentence boundaries, never mid-word."""
    if len(text) <= limit:
        return [text]
    # Sentence-ish boundaries first; fall back to hard wrapping for runaway sentences.
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    chunks, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limit:
            current += " " + sentence
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return [c for c in chunks if c]


# Serializes playback so two utterances never speak over each other.
_speak_lock = threading.Lock()


def speak(text: str) -> None:
    """Speak text aloud in Aegon's voice. Logs and skips on failure.

    Long text is cleaned and chunked, then spoken as consecutive pieces under a single
    lock so a long answer is never interleaved with another utterance. A failure on one
    chunk stops that utterance rather than leaving half a sentence hanging.
    """
    if not text or not text.strip():
        return

    cleaned = _clean_for_speech(text)
    if not cleaned:
        return
    chunks = _chunk_for_tts(cleaned)

    with _speak_lock:
        p = None
        stream = None
        try:
            for chunk in chunks:
                resp = _tts_service.synthesize(
                    chunk,
                    TTS_VOICE,
                    LANGUAGE_CODE,
                    sample_rate_hz=SAMPLE_RATE,
                )
                if not resp.audio:
                    print("[voice] TTS returned empty audio — skipping rest.")
                    return
                if stream is None:
                    p = pyaudio.PyAudio()
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=SAMPLE_RATE,
                        output=True,
                    )
                stream.write(resp.audio)
        except Exception as e:
            print(f"[voice] TTS error: {e}")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            if p is not None:
                p.terminate()
