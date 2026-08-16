"""NVIDIA AI provider adapter.

Implements the AI provider port using NVIDIA's API
(default provider: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning).
"""

import json
import logging
from typing import Any, Optional

import httpx

from src.ports.ai_provider import AIProviderPort

logger = logging.getLogger(__name__)


class NvidiaProvider(AIProviderPort):
    """NVIDIA AI provider implementation.

    Uses the NVIDIA Integrate API with the nemotron model by default.
    API key is user-configurable at runtime.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        base_url: str = "https://integrate.api.nvidia.com/v1",
        max_tokens: int = 65536,
        reasoning_budget: int = 16384,
        temperature: float = 0.6,
        top_p: float = 0.95,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._max_tokens = max_tokens
        self._reasoning_budget = reasoning_budget
        self._temperature = temperature
        self._top_p = top_p

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._api_key = value

    async def analyze_play(self, prompt: str, context: str = "") -> str:
        """Analyze a play using NVIDIA's API."""
        content = f"{prompt}\n\nContext: {context}" if context else prompt
        response = await self._make_request(content)
        return response

    async def analyze_positioning(
        self, frame_data: dict[str, Any], player_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze player positioning using NVIDIA's API."""
        prompt = (
            "Analyze the following rugby player positioning data and provide "
            "tactical insights:\n\n"
            f"Frame data: {json.dumps(frame_data)}\n"
            f"Player data: {json.dumps(player_data)}"
        )
        response = await self._make_request(prompt)
        return {"analysis": response, "provider": "nvidia"}

    async def generate_report(self, analysis_data: dict[str, Any]) -> str:
        """Generate a comprehensive report using NVIDIA's API."""
        prompt = (
            "Generate a comprehensive rugby match analysis report based on "
            f"the following data:\n\n{json.dumps(analysis_data)}"
        )
        return await self._make_request(prompt)

    def get_provider_name(self) -> str:
        return "nvidia"

    def is_configured(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0

    async def _make_request(self, content: str) -> str:
        """Make a request to the NVIDIA API.

        Formats the request exactly as specified in the NVIDIA API reference:
        - Authorization: Bearer nvapi-...
        - Accept: application/json
        - Model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
        - Includes reasoning_budget parameter
        """
        if not self.is_configured():
            raise ValueError("NVIDIA API key not configured")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        payload = {
            "messages": [{"role": "user", "content": content}],
            "model": self._model,
            "max_tokens": self._max_tokens,
            "reasoning_budget": self._reasoning_budget,
            "stream": False,
            "temperature": self._temperature,
            "top_p": self._top_p,
        }

        url = f"{self._base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                logger.error(f"NVIDIA API error: {e.response.status_code} - {e.response.text}")
                raise
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected NVIDIA API response format: {e}")
                raise ValueError(f"Unexpected response format from NVIDIA API: {e}")
