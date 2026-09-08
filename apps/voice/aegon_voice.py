#apps/voice/aegon_voice.py

import os
import queue
import sys
import threading
from collections import deque

import numpy as np
import riva.client
import sounddevice as sd
import torch
from silero_vad import load_silero_vad, VADIterator

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512                # silero-vad streaming requires 512-sample chunks at 16 kHz
PRE_ROLL_CHUNKS = 16               # ~0.5 s of audio kept before detected speech onset
FLUSH_DELAY_SECONDS = 1.5          # matches MERGE_WINDOW_SECONDS in session_logger.py
MAX_UTTERANCE_SECONDS = 30         # force-cut runaway utterances
RECENT_TURNS_LIMIT = 50
MEMORY_TIMER_SECONDS = 1800

# STT — NVIDIA-hosted whisper-large-v3 (Riva gRPC, DGX Cloud). Runs off-machine;
# no local model to load. Key read from NVIDIA_STT_API_KEY — never hardcoded.
RIVA_SERVER = "grpc.nvcf.nvidia.com:443"
ASR_FUNCTION_ID = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"  # whisper-large-v3
ASR_LANGUAGE_CODE = "en"

VAD_THRESHOLD = 0.5
VAD_MIN_SILENCE_MS = 700           # silence that ends an utterance


class AegonLoop:

    def __init__(self, input_queue=None, log_queue=None, task_worker=None):
        self.input_queue = input_queue
        self.log_queue = log_queue
        self.task_worker = task_worker
        self.is_speaking = False
        self.recent_turns = deque(maxlen=RECENT_TURNS_LIMIT)
        self.shutdown_event = threading.Event()
        self.audio_queue = queue.Queue()
        self.utterance_queue = queue.Queue()
        self.asr_service = None
        self.asr_config = None
        self.vad_iterator = None
        self.flush_timer = None
        self.flush_lock = threading.Lock()

    def get_recent_turns(self) -> list:
        return list(self.recent_turns)

    def request_shutdown(self):
        if self.shutdown_event.is_set():
            return
        self.shutdown_event.set()
        self.audio_queue.put(None)
        self.utterance_queue.put(None)
        self._cancel_flush()

    # ─────────────────────────────────────────
    # MODEL LOADING — once, at startup
    # ─────────────────────────────────────────

    def load_models(self):
        if self.asr_service is not None:
            return  # idempotent — already set up at startup
        print("[STT] Connecting to NVIDIA whisper-large-v3 (Riva)...")
        auth = riva.client.Auth(
            uri=RIVA_SERVER,
            use_ssl=True,
            metadata_args=[
                ["function-id", ASR_FUNCTION_ID],
                ["authorization", f"Bearer {os.environ.get('NVIDIA_STT_API_KEY')}"],
            ],
        )
        self.asr_service = riva.client.ASRService(auth)
        self.asr_config = riva.client.RecognitionConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=SAMPLE_RATE,
            language_code=ASR_LANGUAGE_CODE,
            audio_channel_count=1,
            max_alternatives=1,
            enable_automatic_punctuation=True,
        )
        print("[STT] Whisper (NVIDIA) ready.")
        vad_model = load_silero_vad()
        self.vad_iterator = VADIterator(
            vad_model,
            threshold=VAD_THRESHOLD,
            sampling_rate=SAMPLE_RATE,
            min_silence_duration_ms=VAD_MIN_SILENCE_MS,
        )
        print("[STT] silero-vad ready.")

    # ─────────────────────────────────────────
    # AUDIO CAPTURE
    # ─────────────────────────────────────────

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[STT] Audio status: {status}")
        if not self.is_speaking:
            self.audio_queue.put(indata[:, 0].copy())

    # ─────────────────────────────────────────
    # FLUSH SCHEDULING
    # Fires the session_logger flush 1.5 s after the last
    # transcribed turn, unless Sir starts speaking again.
    # ─────────────────────────────────────────

    def _schedule_flush(self):
        with self.flush_lock:
            if self.flush_timer is not None:
                self.flush_timer.cancel()
            self.flush_timer = threading.Timer(FLUSH_DELAY_SECONDS, self._fire_flush)
            self.flush_timer.daemon = True
            self.flush_timer.start()

    def _cancel_flush(self):
        with self.flush_lock:
            if self.flush_timer is not None:
                self.flush_timer.cancel()
                self.flush_timer = None

    def _fire_flush(self):
        if self.log_queue is not None:
            self.log_queue.put_nowait({"action": "flush", "speaker": "user"})

    # ─────────────────────────────────────────
    # TRANSCRIPTION WORKER
    # ─────────────────────────────────────────

    def transcribe_loop(self):
        while True:
            try:
                audio = self.utterance_queue.get(timeout=0.5)
            except queue.Empty:
                if self.shutdown_event.is_set():
                    return
                continue
            if audio is None:
                return
            try:
                pcm_bytes = np.clip(audio, -1.0, 1.0)
                pcm_bytes = (pcm_bytes * 32767).astype(np.int16).tobytes()
                response = self.asr_service.offline_recognize(pcm_bytes, self.asr_config)
                text = "".join(
                    res.alternatives[0].transcript for res in response.results
                ).strip()
            except Exception as e:
                print(f"[STT] Transcription error: {e}")
                continue
            if not text:
                continue
            print(f"You: {text}")
            self.recent_turns.append({"type": "turn", "speaker": "user", "text": text})
            if self.log_queue is not None:
                self.log_queue.put_nowait({"action": "turn", "speaker": "user", "text": text})
            self._schedule_flush()

    # ─────────────────────────────────────────
    # VAD LOOP — main thread
    # ─────────────────────────────────────────

    def vad_loop(self):
        pre_roll = deque(maxlen=PRE_ROLL_CHUNKS)
        speech_chunks = []
        in_speech = False
        max_chunks = int(MAX_UTTERANCE_SECONDS * SAMPLE_RATE / CHUNK_SAMPLES)

        while not self.shutdown_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if chunk is None:
                return

            try:
                event = self.vad_iterator(torch.from_numpy(chunk))
            except Exception as e:
                print(f"[STT] VAD error: {e}")
                continue

            if in_speech:
                speech_chunks.append(chunk)
                if (event and "end" in event) or len(speech_chunks) >= max_chunks:
                    utterance = np.concatenate(list(pre_roll) + speech_chunks)
                    pre_roll.clear()
                    speech_chunks = []
                    in_speech = False
                    self.utterance_queue.put(utterance)
            else:
                if event and "start" in event:
                    in_speech = True
                    speech_chunks = [chunk]
                    self._cancel_flush()
                else:
                    pre_roll.append(chunk)

    # ─────────────────────────────────────────
    # MEMORY TIMER
    # ─────────────────────────────────────────

    def memory_timer_loop(self):
        while not self.shutdown_event.wait(MEMORY_TIMER_SECONDS):
            if self.task_worker is not None and self.recent_turns:
                print("[Memory] 30-minute timer — triggering memory update.")
                if self.input_queue is not None:
                    self.input_queue.put_nowait("__memory_update__")

    # ─────────────────────────────────────────
    # MAIN
    # ─────────────────────────────────────────

    def run(self):
        self.load_models()

        transcriber = threading.Thread(
            target=self.transcribe_loop, daemon=True, name="whisper-transcriber"
        )
        transcriber.start()

        if self.task_worker is not None:
            threading.Thread(
                target=self.memory_timer_loop, daemon=True, name="memory-timer"
            ).start()

        print("\n" + "=" * 50)
        print("AEGON — Online (cloud STT)")
        print("Speak naturally. Ctrl+C to exit.")
        print("=" * 50 + "\n")

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SAMPLES,
                callback=self._audio_callback,
            ):
                self.vad_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.request_shutdown()
            transcriber.join(timeout=30)


if __name__ == "__main__":
    import uuid
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from apps.orchestrator.aegon_orchestrator import on_user_turn_complete as orchestrator_callback, _active_mode
    from core.memory.session_logger import create_session_logger
    from core.modes.morning_briefing import start_briefing_async
    from core.memory.vault_sync import sync_vault_to_memory
    from core.sentinel import sentinel
    from core.sentinel.proactive_queue import drain as drain_sentinel_queue, format_findings_for_speech
    from core.voice.speak import speak

    # Generate one thread_id for the entire voice session
    SESSION_THREAD_ID = str(uuid.uuid4())

    def on_user_turn_complete(text: str):
        """
        Called by session_logger when a complete user turn is ready.
        Runs the orchestrator in a separate thread so the
        voice loop is never blocked.
        """
        print(f"[Routing] '{text}'")

        def run_orchestrator():
            try:
                response = orchestrator_callback(text, thread_id=SESSION_THREAD_ID)
                print(f"Aegon: {response}")
            except Exception as e:
                print(f"[Routing] Orchestrator error: {e}")

        thread = threading.Thread(target=run_orchestrator, daemon=True)
        thread.start()

    log_queue, log_worker = create_session_logger(
        on_user_turn_complete=on_user_turn_complete
    )
    log_worker.start()
    sentinel.start()
    sync_vault_to_memory()

    # Connect ASR before any briefing fires. Both STT and TTS are cloud now —
    # no local GPU model to warm, no concurrent-CUDA concern.
    loop = AegonLoop(
        input_queue=None,
        log_queue=log_queue,
        task_worker=None,
    )
    loop.load_models()          # NVIDIA Riva ASR client + silero-vad

    from core.modes.mode_detector import infer_mode_from_context
    _active_mode = infer_mode_from_context()
    print(f"[mode] Active mode: {_active_mode}")

    if _active_mode == "morning":
        start_briefing_async()
    else:
        findings = drain_sentinel_queue(max_items=3)
        if findings:
            speak(format_findings_for_speech(findings))

    loop.run()  # load_models() is idempotent — no reload here

    log_queue.put(None)
    log_queue.join()
