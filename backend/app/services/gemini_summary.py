from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GEMINI_GENERATE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT_SECONDS = 6.0


class GeminiSummaryClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip().removeprefix("models/")
        self.timeout_seconds = timeout_seconds

    def advisory_summary(self, facts: dict[str, Any]) -> str | None:
        if not self.api_key or not self.model:
            return None

        request = Request(
            self._url(),
            data=json.dumps(self._payload(facts)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None

        return _extract_text(body)

    def _url(self) -> str:
        model = quote(self.model, safe="")
        key = quote(self.api_key, safe="")
        return f"{GEMINI_GENERATE_BASE_URL}/models/{model}:generateContent?key={key}"

    def _payload(self, facts: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Write one concise advisory summary for AssetIQ. "
            "Use the provided recommendation and numbers exactly. "
            "Do not change the recommendation. Do not invent values. "
            "Compare only total_repair_cost_rm against depreciation_loss_rm. "
            "Do not mention buying, acquiring, financing, or replacing assets. "
            "Format RM currency with a space after RM and comma separators, for example RM 18,400. "
            "Mention the 5-year depreciation comparison and repair cost. "
            "Return 1-2 complete sentences. Include the recommendation, repair cost, "
            "depreciation loss, and 5-year horizon. Return plain text only.\n\n"
            f"Facts:\n{json.dumps(facts, ensure_ascii=False, sort_keys=True)}"
        )
        return {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are AssetIQ's vehicle advisory summarizer. "
                            "You explain calculated results; you do not make new financial decisions."
                        )
                    }
                ]
            },
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 256,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }


def _extract_text(body: dict[str, Any]) -> str | None:
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None

    parts = candidates[0].get("content", {}).get("parts", [])
    if not isinstance(parts, list):
        return None

    text = " ".join(str(part.get("text", "")).strip() for part in parts if isinstance(part, dict))
    text = " ".join(text.split())

    if len(text.split()) < 12:
        return None

    return _format_rm_currency(text) or None


def _format_rm_currency(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        amount = int(match.group(1).replace(",", ""))
        return f"RM {amount:,}"

    return re.sub(r"\bRM\s*([0-9][0-9,]*)\b", replace, text)
