"""Claude (Anthropic) AI provider adapter.

Implements the AI provider port using Anthropic's Messages API.
"""

import json
import logging
from typing import Any, Optional

import httpx

from src.ports.ai_provider import AIProviderPort

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProviderPort):
    """Claude (Anthropic) AI provider implementation using Messages API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
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
        """Analyze a play using Anthropic's API."""
        content = f"{prompt}\n\nContext: {context}" if context else prompt
        return await self._make_request(content)

    async def analyze_positioning(
        self, frame_data: dict[str, Any], player_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze player positioning using Anthropic's API."""
        prompt = (
            "Analyze the following rugby player positioning data and provide "
            "tactical insights:\n\n"
            f"Frame data: {json.dumps(frame_data)}\n"
            f"Player data: {json.dumps(player_data)}"
        )
        response = await self._make_request(prompt)
        return {"analysis": response, "provider": "claude"}

    async def generate_report(self, analysis_data: dict[str, Any]) -> str:
        """Generate a comprehensive report using Anthropic's API."""
        prompt = (
            "Generate a comprehensive rugby match analysis report based on "
            f"the following data:\n\n{json.dumps(analysis_data)}"
        )
        return await self._make_request(prompt)

    def get_provider_name(self) -> str:
        return "claude"

    def is_configured(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0

    async def _make_request(self, content: str) -> str:
        """Make a request to Anthropic's Messages API."""
        if not self.is_configured():
            raise ValueError("Claude API key not configured")

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": content}],
            "temperature": self._temperature,
        }

        url = f"{self._base_url}/messages"

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["content"][0]["text"]
            except httpx.HTTPStatusError as e:
                logger.error(f"Claude API error: {e.response.status_code} - {e.response.text}")
                raise
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected Claude API response format: {e}")
                raise ValueError(f"Unexpected response format from Claude API: {e}")
