"""Ollama (local) AI provider adapter.

Implements the AI provider port using the local Ollama HTTP API.
No API key required - runs on local hardware.
"""

import json
import logging
from typing import Any, Optional

import httpx

from src.ports.ai_provider import AIProviderPort

logger = logging.getLogger(__name__)


class OllamaProvider(AIProviderPort):
    """Ollama local AI provider implementation.

    Connects to a locally running Ollama instance.
    No API key required.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        temperature: float = 0.7,
        api_key: Optional[str] = None,
    ):
        self._base_url = base_url
        self._model = model
        self._temperature = temperature
        self._api_key = api_key

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._api_key = value

    async def analyze_play(self, prompt: str, context: str = "") -> str:
        """Analyze a play using local Ollama model."""
        content = f"{prompt}\n\nContext: {context}" if context else prompt
        return await self._make_request(content)

    async def analyze_positioning(
        self, frame_data: dict[str, Any], player_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze player positioning using local Ollama model."""
        prompt = (
            "Analyze the following rugby player positioning data and provide "
            "tactical insights:\n\n"
            f"Frame data: {json.dumps(frame_data)}\n"
            f"Player data: {json.dumps(player_data)}"
        )
        response = await self._make_request(prompt)
        return {"analysis": response, "provider": "ollama"}

    async def generate_report(self, analysis_data: dict[str, Any]) -> str:
        """Generate a comprehensive report using local Ollama model."""
        prompt = (
            "Generate a comprehensive rugby match analysis report based on "
            f"the following data:\n\n{json.dumps(analysis_data)}"
        )
        return await self._make_request(prompt)

    def get_provider_name(self) -> str:
        return "ollama"

    def is_configured(self) -> bool:
        return True

    async def _make_request(self, content: str) -> str:
        """Make a request to the local Ollama API."""
        url = f"{self._base_url}/api/generate"

        payload = {
            "model": self._model,
            "prompt": content,
            "stream": False,
            "options": {
                "temperature": self._temperature,
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["response"]
            except httpx.ConnectError:
                logger.error("Cannot connect to Ollama. Is it running locally?")
                raise ConnectionError(
                    "Cannot connect to Ollama. Please ensure Ollama is running "
                    f"at {self._base_url}"
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
                raise
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected Ollama API response format: {e}")
                raise ValueError(f"Unexpected response format from Ollama API: {e}")
