"""Google Gemini AI provider adapter.

Implements the AI provider port using Google's Generative AI API.
"""

import json
import logging
from typing import Any, Optional

import httpx

from src.ports.ai_provider import AIProviderPort

logger = logging.getLogger(__name__)


class GeminiProvider(AIProviderPort):
    """Google Gemini AI provider implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-pro",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._max_tokens = max_tokens
        self._temperature = temperature

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._api_key = value

    async def analyze_play(self, prompt: str, context: str = "") -> str:
        """Analyze a play using Google Gemini API."""
        content = f"{prompt}\n\nContext: {context}" if context else prompt
        return await self._make_request(content)

    async def analyze_positioning(
        self, frame_data: dict[str, Any], player_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze player positioning using Google Gemini API."""
        prompt = (
            "Analyze the following rugby player positioning data and provide "
            "tactical insights:\n\n"
            f"Frame data: {json.dumps(frame_data)}\n"
            f"Player data: {json.dumps(player_data)}"
        )
        response = await self._make_request(prompt)
        return {"analysis": response, "provider": "gemini"}

    async def generate_report(self, analysis_data: dict[str, Any]) -> str:
        """Generate a comprehensive report using Google Gemini API."""
        prompt = (
            "Generate a comprehensive rugby match analysis report based on "
            f"the following data:\n\n{json.dumps(analysis_data)}"
        )
        return await self._make_request(prompt)

    def get_provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0

    async def _make_request(self, content: str) -> str:
        """Make a request to Google's Generative AI API."""
        if not self.is_configured():
            raise ValueError("Gemini API key not configured")

        url = (
            f"{self._base_url}/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )

        payload = {
            "contents": [{"parts": [{"text": content}]}],
            "generationConfig": {
                "maxOutputTokens": self._max_tokens,
                "temperature": self._temperature,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as e:
                logger.error(f"Gemini API error: {e.response.status_code} - {e.response.text}")
                raise
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected Gemini API response format: {e}")
                raise ValueError(f"Unexpected response format from Gemini API: {e}")
