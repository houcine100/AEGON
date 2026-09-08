#core/memory/session_logger.py

import json
import queue
import threading
from datetime import datetime
from pathlib import Path
import base64
import os
from cryptography.fernet import Fernet
import hashlib

def get_fernet() -> Fernet:
    """Get Fernet cipher from encryption key environment variable."""
    key = os.environ.get("AEGON_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError("AEGON_ENCRYPTION_KEY not set.")
    # Derive a 32-byte key from the provided string
    derived = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

SESSIONS_DIR = Path(__file__).resolve().parent / "sessions"
GAP_THRESHOLD_SECONDS = 1800  # 30 minutes
MIN_TEXT_LENGTH = 3            # discard turns shorter than this
MERGE_WINDOW_SECONDS = 1.5     # merge fragments within this window (F.1: Whisper delivers whole utterances)

EMOTIONAL_KEYWORDS = {
    "stressed", "stress", "anxious", "anxiety", "worried", "worry",
    "frustrated", "frustration", "angry", "anger", "sad", "tired",
    "exhausted", "overwhelmed", "scared", "nervous", "excited",
    "happy", "great", "amazing", "terrible", "awful"
}

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def detect_emotional_weight(text: str) -> str:
    text_lower = text.lower()
    for keyword in EMOTIONAL_KEYWORDS:
        if keyword in text_lower:
            return keyword
    return "neutral"


def make_session_filename() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SESSIONS_DIR / f"session_{timestamp}.jsonl"


def is_valid_turn(text: str) -> bool:
    """Discard noise — too short or punctuation only."""
    cleaned = text.strip().strip(".,!?;:-()[]{}\"'")
    return len(cleaned) >= MIN_TEXT_LENGTH

def _is_ascii_latin(text: str) -> bool:
    """Returns False if text contains non-Latin scripts."""
    try:
        text.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

# ─────────────────────────────────────────
# SESSION LOGGER
# ─────────────────────────────────────────

class SessionLogger:

    def __init__(self, on_user_turn_complete=None):
        self.session_file = None
        self.last_turn_time = None
        self.lock = threading.Lock()
        self._buffers = {}
        self.on_user_turn_complete = on_user_turn_complete
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._start_new_session()

    def _start_new_session(self):
        self.session_file = make_session_filename()
        self.last_turn_time = datetime.now()
        self._write_record({
            "type": "session_start",
            "timestamp": self.last_turn_time.isoformat()
        })

    def _check_gap(self):
        now = datetime.now()
        if self.last_turn_time:
            gap = (now - self.last_turn_time).total_seconds()
            if gap >= GAP_THRESHOLD_SECONDS:
                self._flush_all_buffers()
                self._write_record({
                    "type": "session_end",
                    "timestamp": self.last_turn_time.isoformat(),
                    "reason": "gap_timeout"
                })
                self._start_new_session()
        self.last_turn_time = now

    def _write_record(self, record: dict):
        try:
            f = get_fernet()
            line = json.dumps(record, ensure_ascii=False)
            encrypted = f.encrypt(line.encode()).decode()
            with open(self.session_file, "a", encoding="utf-8") as fp:
                fp.write(encrypted + "\n")
        except Exception as e:
            # Fallback to plaintext if encryption fails
            print(f"[Logger] Encryption failed, writing plaintext: {e}")
            with open(self.session_file, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _flush_buffer(self, speaker: str):
        buf = self._buffers.get(speaker)
        if not buf:
            return
        text = buf["text"].strip()
        timestamp = buf["timestamp"]
        del self._buffers[speaker]
        if not is_valid_turn(text):
            return
        record = {
            "type": "turn",
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp.isoformat(),
            "emotional_weight": detect_emotional_weight(text),
            "transcription_reliable": _is_ascii_latin(text)
        }
        self._write_record(record)
        # Fire callback with full consolidated text for user turns
        if speaker == "user" and self.on_user_turn_complete is not None:
            try:
                self.on_user_turn_complete(text)
            except Exception as e:
                print(f"[Logger] Callback error: {e}")

    def _flush_all_buffers(self):
        for speaker in list(self._buffers.keys()):
            self._flush_buffer(speaker)

    def log_turn(self, speaker: str, text: str):
        with self.lock:
            self._check_gap()
            now = datetime.now()
            buf = self._buffers.get(speaker)

            if buf is None:
                # Start new buffer
                self._buffers[speaker] = {"text": text, "timestamp": now}
            else:
                gap = (now - buf["timestamp"]).total_seconds()
                if gap <= MERGE_WINDOW_SECONDS:
                    # Merge fragment into existing buffer
                    self._buffers[speaker]["text"] += " " + text
                else:
                    # Gap too large — flush old buffer, start new one
                    self._flush_buffer(speaker)
                    self._buffers[speaker] = {"text": text, "timestamp": now}

    def flush_speaker(self, speaker: str):
        """Force flush a speaker's buffer — call when turn is complete."""
        with self.lock:
            buf = self._buffers.get(speaker)
            if not buf:
                return
            text = buf["text"].strip()
            timestamp = buf["timestamp"]
            del self._buffers[speaker]
            if not is_valid_turn(text):
                return
            record = {
                "type": "turn",
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp.isoformat(),
                "emotional_weight": detect_emotional_weight(text),
                "transcription_reliable": _is_ascii_latin(text)
            }
            self._write_record(record)
            # Fire callback on flush for user turns
            if speaker == "user" and self.on_user_turn_complete is not None:
                try:
                    self.on_user_turn_complete(text)
                except Exception as e:
                    print(f"[Logger] Callback error: {e}")

    def log_task(self, task_text: str, groq_response: str):
        with self.lock:
            now = datetime.now()
            record = {
                "type": "task",
                "task_text": task_text,
                "groq_response": groq_response,
                "timestamp": now.isoformat(),
                "emotional_weight": detect_emotional_weight(task_text)
            }
            self._write_record(record)

    def end_session(self):
        with self.lock:
            self._flush_all_buffers()
            self._write_record({
                "type": "session_end",
                "timestamp": datetime.now().isoformat(),
                "reason": "user_exit"
            })


# ─────────────────────────────────────────
# LOGGER WORKER
# ─────────────────────────────────────────

class SessionLoggerWorker(threading.Thread):

    def __init__(self, logger: SessionLogger, log_queue: queue.Queue):
        super().__init__(daemon=True, name="session-logger")
        self.logger = logger
        self.log_queue = log_queue

    def run(self):
        while True:
            item = self.log_queue.get()
            try:
                if item is None:
                    self.logger.end_session()
                    return
                action = item.get("action")
                if action == "turn":
                    self.logger.log_turn(item["speaker"], item["text"])
                elif action == "flush":
                    self.logger.flush_speaker(item["speaker"])
                elif action == "task":
                    self.logger.log_task(item["task_text"], item["groq_response"])
            finally:
                self.log_queue.task_done()

def create_session_logger(on_user_turn_complete=None):
    logger = SessionLogger(on_user_turn_complete=on_user_turn_complete)
    log_queue = queue.Queue()
    worker = SessionLoggerWorker(logger=logger, log_queue=log_queue)
    return log_queue, worker