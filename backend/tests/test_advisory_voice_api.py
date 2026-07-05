from fastapi.testclient import TestClient

from app.main import app
from app.routers import advisory
from app.schemas import AdvisoryData, AdvisoryVoiceResponse
from app.services import advisory_voice


ADVISORY = {
    "current_value_rm": 82000,
    "estimated_repair_cost_rm": 12000,
    "predicted_value_after_repair_rm": 88000,
    "repair_outcome_rm": 76000,
    "trade_in_now_rm": 82000,
    "recommendation": "trade_in",
    "summary": (
        "Based on your car's current value and estimated repair cost, trading in is recommended "
        "because the repair cost is too high compared to the value recovered after repair."
    ),
}


def test_advisory_voice_falls_back_without_gemini_key(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "Should I sell my car now?", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "reply": (
            "Based on your current value of RM82,000 and estimated repair cost of RM12,000, "
            "trading in is recommended because repairing leaves an outcome of RM76,000 compared with "
            "RM82,000 if you trade in now."
        ),
        "audio_base64": None,
        "mime_type": None,
        "tts_provider": "gemini-unavailable",
        "fallback_reason": "missing_gemini_api_key",
        "text_provider": "local",
        "tts_wait_ms": 0,
        "gemini_key_detected": False,
    }


def test_advisory_voice_keeps_outside_questions_in_scope(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "Can you book a service appointment?", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "I can only help explain this repair versus trade-in advisory right now."
    assert resp.json()["audio_base64"] is None
    assert resp.json()["tts_provider"] == "gemini-unavailable"


def test_advisory_voice_greets_on_wake_phrase(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "Hey AssetIQ", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "Hi, what can I help?"
    assert resp.json()["fallback_reason"] == "missing_gemini_api_key"


def test_advisory_voice_thanks_returns_polite_closing(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "thanks", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "You're welcome. Say Hey AssetIQ if you want to ask more about the advisory."


def test_advisory_voice_why_explains_trade_in_recommendation(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "why", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == (
        "Trade-in is recommended because the estimated repair cost is RM12,000, and repairing leaves an outcome "
        "of RM76,000 compared with RM82,000 if you trade in now."
    )


def test_advisory_voice_joke_returns_scope_limit(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "tell me a joke", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "I can only help explain this repair versus trade-in advisory right now."


def test_advisory_voice_sell_question_returns_advisory_answer(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: None)

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "should I sell my car now", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == (
        "Based on your current value of RM82,000 and estimated repair cost of RM12,000, "
        "trading in is recommended because repairing leaves an outcome of RM76,000 compared with "
        "RM82,000 if you trade in now."
    )


def test_advisory_voice_returns_stubbed_gemini_audio(monkeypatch):
    class StubVoiceService:
        def respond(self, question, advisory_data):
            assert question == "Should I sell my car now?"
            assert advisory_data.current_value_rm == 82000
            return AdvisoryVoiceResponse(
                reply="Trade in now.",
                audio_base64="UklGRg==",
                mime_type="audio/wav",
                tts_provider="gemini",
                fallback_reason=None,
                text_provider="gemini",
                tts_wait_ms=12,
                gemini_key_detected=True,
            )

    monkeypatch.setattr(advisory, "advisory_voice_service", StubVoiceService())

    with TestClient(app) as client:
        resp = client.post(
            "/api/advisory/voice/respond",
            json={"question": "Should I sell my car now?", "advisory": ADVISORY},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "reply": "Trade in now.",
        "audio_base64": "UklGRg==",
        "mime_type": "audio/wav",
        "tts_provider": "gemini",
        "fallback_reason": None,
        "text_provider": "gemini",
        "tts_wait_ms": 12,
        "gemini_key_detected": True,
    }


def test_advisory_voice_extracts_camel_case_tts_audio_and_wraps_wav():
    wav_base64 = advisory_voice._pcm_base64_to_wav_base64("AAAAAA==")

    assert advisory_voice._extract_output_audio_data({"outputAudio": {"data": "AAAAAA=="}}) == "AAAAAA=="
    assert wav_base64.startswith("UklGR")


def test_advisory_voice_extracts_nested_step_audio():
    interaction = {
        "steps": [
            {
                "type": "model_output",
                "output": {
                    "content": [
                        {
                            "type": "audio",
                            "data": "AAAAAA==",
                        }
                    ]
                },
            }
        ]
    }

    assert advisory_voice._extract_output_audio_data(interaction) == "AAAAAA=="


def test_advisory_voice_extracts_nested_step_text():
    interaction = {
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": "Trading in is recommended because repair recovery is weak.",
                    }
                ],
            }
        ]
    }

    assert advisory_voice._extract_output_text(interaction) == (
        "Trading in is recommended because repair recovery is weak."
    )


def test_advisory_voice_out_of_scope_clean_reply_is_fixed_scope_message():
    reply = advisory_voice._clean_reply("Sure, here is a joke.", "Tell me a joke.", AdvisoryData(**ADVISORY))

    assert reply == "I can only help explain this repair versus trade-in advisory right now."


def test_advisory_voice_retries_fallback_tts_model_on_quota(monkeypatch):
    class SettingsStub:
        gemini_tts_model = "gemini-3.1-flash-tts-preview"

    models = []

    def fake_create_interaction(api_key, payload, timeout_seconds=20):
        models.append(payload["model"])
        if payload["model"] == "gemini-3.1-flash-tts-preview":
            raise advisory_voice.GeminiRequestError(429, "quota exceeded")
        return {"outputAudio": {"data": "AAAAAA=="}}

    monkeypatch.setattr(advisory_voice, "get_settings", lambda: SettingsStub())
    monkeypatch.setattr(advisory_voice, "_tts_quota_exhausted", False)
    monkeypatch.setattr(advisory_voice, "_tts_audio_cache", {})
    monkeypatch.setattr(advisory_voice, "_create_interaction", fake_create_interaction)

    audio = advisory_voice._generate_audio("test-key", "Trade in now.")

    assert models == ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
    assert audio.mime_type == "audio/wav"
    assert audio.audio_base64.startswith("UklGR")


def test_advisory_voice_returns_quota_reason_when_all_tts_models_429(monkeypatch):
    class SettingsStub:
        gemini_tts_model = "gemini-3.1-flash-tts-preview"

    monkeypatch.setattr(advisory_voice, "get_settings", lambda: SettingsStub())
    monkeypatch.setattr(advisory_voice, "_tts_quota_exhausted", False)
    monkeypatch.setattr(advisory_voice, "_tts_audio_cache", {})
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: "test-key")
    monkeypatch.setattr(advisory_voice, "_generate_reply", lambda api_key, question, advisory: "Trade in now.")
    monkeypatch.setattr(
        advisory_voice,
        "_create_interaction",
        lambda api_key, payload, timeout_seconds=20: (_ for _ in ()).throw(
            advisory_voice.GeminiRequestError(429, "quota exceeded")
        ),
    )

    response = advisory_voice.AdvisoryVoiceService().respond("Should I sell my car now?", AdvisoryData(**ADVISORY))

    assert response.tts_provider == "gemini-unavailable"
    assert response.fallback_reason == "gemini_tts_quota_exceeded"
    assert response.audio_base64 is None


def test_advisory_voice_returns_browser_fallback_when_tts_times_out(monkeypatch):
    monkeypatch.setattr(advisory_voice, "_api_key", lambda: "test-key")
    monkeypatch.setattr(advisory_voice, "_tts_quota_exhausted", False)
    monkeypatch.setattr(advisory_voice, "_tts_audio_cache", {})

    def fake_create_interaction(api_key, payload, timeout_seconds=20):
        assert timeout_seconds == 14.0
        raise advisory_voice.httpx.TimeoutException("timed out")

    monkeypatch.setattr(advisory_voice, "_create_interaction", fake_create_interaction)

    response = advisory_voice.AdvisoryVoiceService().respond("Should I sell my car now?", AdvisoryData(**ADVISORY))

    assert response.reply.startswith("Based on your current value")
    assert response.audio_base64 is None
    assert response.mime_type is None
    assert response.tts_provider == "gemini-unavailable"
    assert response.fallback_reason == "gemini_tts_timeout"
    assert response.text_provider == "local"
    assert response.tts_wait_ms >= 0
