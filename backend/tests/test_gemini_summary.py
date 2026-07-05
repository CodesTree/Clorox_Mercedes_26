import json

from app.services import gemini_summary
from app.services.gemini_summary import GeminiSummaryClient


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


def test_gemini_summary_returns_none_without_key():
    client = GeminiSummaryClient(api_key="", model="gemini-3.5-flash")
    assert client.advisory_summary({"recommendation": "Sell"}) is None


def test_gemini_summary_posts_fact_packet_and_extracts_text(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": " Repair and keep is recommended "},
                                {"text": "because repair cost is lower. "},
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(gemini_summary, "urlopen", fake_urlopen)
    client = GeminiSummaryClient(api_key="test-key", model="models/gemini-test", timeout_seconds=3)

    summary = client.advisory_summary(
        {
            "recommendation": "Repair and keep",
            "depreciation_loss_rm": 118000,
            "total_repair_cost_rm": 18400,
        }
    )

    assert summary == "Repair and keep is recommended because repair cost is lower."
    assert "models/gemini-test:generateContent" in captured["url"]
    assert "key=test-key" in captured["url"]
    assert captured["timeout"] == 3
    prompt = captured["payload"]["contents"][0]["parts"][0]["text"]
    assert "Do not change the recommendation" in prompt
    assert '"depreciation_loss_rm": 118000' in prompt
