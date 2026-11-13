"""QA Scenarios #7, #8, #9, #10, #11: Local AI, Cloud AI + Fallback, Voice Input/Output/Interrupt & Memory."""

from __future__ import annotations

import json
from pathlib import Path
import httpx
import pytest

from nexus_ultron.runtime import NexusUltronRuntime
from nexus_ultron.storage.memory_system import SensitiveMemoryError


def test_07_and_11_local_ai_and_conversation_memory(offline_runtime: NexusUltronRuntime) -> None:
    """Tests #7 (Local AI functionality) & #11 (Conversation & FTS5/Semantic Memory + Sensitive Blocker)."""
    conv = offline_runtime.memory.create_conversation("Offline Test")
    calc_res = offline_runtime.ai_router.generate_response("calculate (128 * 4) + 88", conversation_id=conv["id"])
    assert "600" in calc_res["reply"]
    assert calc_res["provider_used"] == "ultron_local_core"

    # Store & search hybrid FTS5 + semantic memory
    m1 = offline_runtime.memory.add_memory(
        "Warehouse Tech Stack",
        "Use SQLite WAL mode with PBKDF2 authentication for offline desktop software.",
        namespace="knowledge",
        tags=["architecture", "sqlite"],
    )
    hits = offline_runtime.memory.search_memory("offline sqlite authentication")
    assert any(h["id"] == m1["id"] for h in hits)

    # Edit & delete memory
    updated = offline_runtime.memory.update_memory(m1["id"], title="Updated Tech Stack")
    assert updated["title"] == "Updated Tech Stack"
    assert offline_runtime.memory.delete_memory(m1["id"]) is True

    # Sensitive credentials / card numbers MUST be blocked from silent storage
    with pytest.raises(SensitiveMemoryError):
        offline_runtime.memory.add_memory("My API Key", "sk-abcdefghijklmnopqrstuvwxyz123456")
    with pytest.raises(SensitiveMemoryError):
        offline_runtime.memory.add_memory("Card", "4532 1111 2222 3333")


def test_08_cloud_ai_integration_and_offline_fallback(online_runtime: NexusUltronRuntime) -> None:
    """Test #8: Cloud AI provider call with secret redaction + seamless local fallback on network failure."""
    online_runtime.vault.set_secret("OPENAI_API_KEY", "sk-testcloudkey9876543210abcdef")
    captured_payloads: list[dict] = []

    def _mock_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_payloads.append(body)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Cloud model verified response."}}]},
        )

    online_runtime.ai_router.set_http_transport(httpx.MockTransport(_mock_handler))
    res = online_runtime.ai_router.generate_response("Explain modular Python architecture. otp: 918273")
    assert res["provider_used"] == "openai_compatible"
    assert res["reply"] == "Cloud model verified response."
    # Verify OTP was scrubbed before reaching cloud prompt!
    sent_user_text = captured_payloads[0]["messages"][1]["content"]
    assert "918273" not in sent_user_text

    # Simulate cloud network outage -> must fall back to local core without raising!
    def _failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Simulated cloud outage", request=request)

    online_runtime.ai_router.set_http_transport(httpx.MockTransport(_failing_handler))
    fallback_res = online_runtime.ai_router.generate_response("calculate 50 * 3")
    assert fallback_res["fallback_occurred"] is True
    assert fallback_res["provider_used"] == "ultron_local_core"
    assert "150" in fallback_res["reply"]


def test_09_and_10_voice_input_wakeword_vad_tts_and_interruption(offline_runtime: NexusUltronRuntime) -> None:
    """Tests #9 (Voice input, wake-word, VAD, PTT) & #10 (Voice output + immediate interruption)."""
    offline_runtime.voice.update_settings(wake_word="hey ultron", tts_rate=190)

    # Ignore utterance missing wake word when require_wake_word=True
    ignored = offline_runtime.voice.process_voice_turn("random background chatter", require_wake_word=True)
    assert ignored["ignored"] is True

    # Process valid wake-word command -> generates offline WAV speech
    turn = offline_runtime.voice.process_voice_turn("Hey Ultron, calculate 25 * 4", require_wake_word=True)
    assert turn["ignored"] is False
    assert turn["stt"]["wake_word_detected"] is True
    assert "100" in turn["ai"]["reply"]
    wav_path = Path(turn["tts"]["wav_path"])
    assert wav_path.exists() and wav_path.stat().st_size > 100

    # Test VAD on synthesized speech WAV
    stt_wav = offline_runtime.voice.transcribe_audio(wav_path=wav_path)
    assert stt_wav["vad"]["rms_energy"] > 0

    # Interrupt ULTRON while speaking
    interrupted = offline_runtime.voice.interrupt_speech()
    assert interrupted["interrupted"] is True
    assert offline_runtime.voice.is_speaking is False
