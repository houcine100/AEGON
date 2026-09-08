import asyncio
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

from websockets.exceptions import ConnectionClosedError


MODULE_PATH = Path(__file__).resolve().parents[1] / "apps" / "voice" / "aegon_voice.py"
SPEC = importlib.util.spec_from_file_location("aegon_voice", MODULE_PATH)
aegon_voice = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aegon_voice)


class FakeSession:
    def __init__(self):
        self.receive_calls = 0

    async def receive(self):
        self.receive_calls += 1
        if self.receive_calls == 1:
            yield SimpleNamespace(
                data=b"chunk-1",
                server_content=SimpleNamespace(
                    input_transcription=None,
                    output_transcription=None,
                    interrupted=False,
                ),
            )
            return

        if self.receive_calls == 2:
            yield SimpleNamespace(
                data=b"chunk-2",
                server_content=SimpleNamespace(
                    input_transcription=None,
                    output_transcription=None,
                    interrupted=False,
                ),
            )
            return

        raise ConnectionClosedError(None, None)


class VoiceLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_receive_audio_continues_across_turns(self):
        loop = aegon_voice.AegonLoop()
        loop.audio_in_queue = asyncio.Queue()
        loop.out_queue = asyncio.Queue()
        loop.session = FakeSession()

        with self.assertRaises(ConnectionClosedError):
            await loop.receive_audio()

        self.assertEqual(loop.session.receive_calls, 3)
        self.assertEqual(await loop.audio_in_queue.get(), b"chunk-1")
        self.assertEqual(await loop.audio_in_queue.get(), b"chunk-2")


if __name__ == "__main__":
    unittest.main()
