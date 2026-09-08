"""
Standalone NVIDIA Riva key test — STT + TTS, isolated from the voice loop.
Run: python tests/test_nvidia_keys.py
Requires NVIDIA_STT_API_KEY and NVIDIA_TTS_API_KEY set in the environment.
"""
import os
import sys
import wave

import riva.client

RIVA_SERVER = "grpc.nvcf.nvidia.com:443"
ASR_FUNCTION_ID = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"  # whisper-large-v3
TTS_FUNCTION_ID = "ddacc747-1269-4fab-bfd9-8f593dead106"  # chatterbox-multilingual-tts
SAMPLE_RATE = 16000


def test_tts():
    print("[TTS] Connecting to NVIDIA Chatterbox-Multilingual (Riva)...")
    key = os.environ.get("NVIDIA_TTS_API_KEY")
    if not key:
        print("[TTS] FAIL — NVIDIA_TTS_API_KEY not set.")
        return False
    auth = riva.client.Auth(
        uri=RIVA_SERVER,
        use_ssl=True,
        metadata_args=[
            ["function-id", TTS_FUNCTION_ID],
            ["authorization", f"Bearer {key}"],
        ],
    )
    service = riva.client.SpeechSynthesisService(auth)
    try:
        resp = service.synthesize(
            text="This is a key test.",
            voice_name="Chatterbox-Multilingual.en-US.Male",
            language_code="en-US",
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hz=22050,
        )
    except Exception as e:
        print(f"[TTS] FAIL — {e}")
        return False

    out_path = os.path.join(os.path.dirname(__file__), "_nvidia_tts_test.wav")
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(resp.audio)
    print(f"[TTS] OK — {len(resp.audio)} bytes written to {out_path}")
    return True


def test_stt():
    print("[STT] Connecting to NVIDIA whisper-large-v3 (Riva)...")
    key = os.environ.get("NVIDIA_STT_API_KEY")
    if not key:
        print("[STT] FAIL — NVIDIA_STT_API_KEY not set.")
        return False
    auth = riva.client.Auth(
        uri=RIVA_SERVER,
        use_ssl=True,
        metadata_args=[
            ["function-id", ASR_FUNCTION_ID],
            ["authorization", f"Bearer {key}"],
        ],
    )
    asr_service = riva.client.ASRService(auth)
    config = riva.client.RecognitionConfig(
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hertz=22050,
        language_code="en",
        audio_channel_count=1,
        max_alternatives=1,
        enable_automatic_punctuation=True,
    )

    # Feed back the WAV we just synthesized via TTS — no mic needed.
    wav_path = os.path.join(os.path.dirname(__file__), "_nvidia_tts_test.wav")
    if not os.path.exists(wav_path):
        print("[STT] SKIP — no test WAV (TTS step must succeed first).")
        return False
    with wave.open(wav_path, "rb") as wf:
        audio_bytes = wf.readframes(wf.getnframes())

    try:
        response = asr_service.offline_recognize(audio_bytes, config)
    except Exception as e:
        print(f"[STT] FAIL — {e}")
        return False

    if not response.results:
        print("[STT] FAIL — empty response (no transcript returned).")
        return False
    transcript = response.results[0].alternatives[0].transcript
    print(f"[STT] OK — transcript: {transcript!r}")
    return True


if __name__ == "__main__":
    tts_ok = test_tts()
    stt_ok = test_stt()
    print("\n--- Summary ---")
    print(f"TTS: {'PASS' if tts_ok else 'FAIL'}")
    print(f"STT: {'PASS' if stt_ok else 'FAIL'}")
    sys.exit(0 if (tts_ok and stt_ok) else 1)
