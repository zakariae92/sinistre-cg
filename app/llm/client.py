"""LLM behind a small interface: structured output only (Pydantic schema in, validated model out)."""

import asyncio
import logging
from pathlib import Path
from typing import Protocol, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
PROMPTS = Path(__file__).with_name("prompts")
PROMPT_VERSION = "v1"  # part of the analysis cache key: bump when a prompt changes


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


class LLMClient(Protocol):
    model: str

    async def structured(self, system: str, user: str, schema: type[T]) -> T: ...


class GeminiClient:
    def __init__(self, model: str, api_key: str | None = None, thinking: str | None = None) -> None:
        self.model = model
        self._thinking = types.ThinkingConfig(thinking_level=thinking) if thinking else None  # type: ignore[arg-type]
        self._client = genai.Client(api_key=api_key or get_settings().gemini_api_key)

    async def structured(self, system: str, user: str, schema: type[T]) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
            thinking_config=self._thinking,
        )
        last: Exception | None = None
        for attempt in range(4):
            try:
                r = await self._client.aio.models.generate_content(model=self.model, contents=user, config=config)
                return schema.model_validate_json(r.text or "")
            except ValidationError as e:  # invalid JSON: retry once with the same input
                last = e
                log.warning("JSON invalide (%s), nouvel essai", self.model)
            except errors.APIError as e:
                if e.code not in (429, 500, 503):
                    raise
                last = e
                await asyncio.sleep(5 * 2**attempt)  # quota or overload: back off
        raise RuntimeError(f"LLM {self.model} : échec après plusieurs essais") from last


def get_llm(model: str | None = None, thinking: str | None = None) -> LLMClient:
    return GeminiClient(model or get_settings().llm_model, thinking=thinking)
