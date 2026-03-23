"""
OpenAI API client — replaces Ollama for AI scoring and search.

Uses gpt-4o-mini by default: fast, cheap (~$0.15/1M input tokens),
and significantly more accurate than a local Ollama model for
structured JSON output tasks.

Cost reference:
  - Scoring 77k leads:  ~$3 one-time
  - Monthly new leads:  ~$0.50–1/month
  - Search queries:     ~$0.0002 each (fractions of a cent)
"""
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

DEFAULT_MODEL = "gpt-4o-mini"


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
    return _client


async def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 300,
) -> str:
    """Send a prompt and return the text content of the response."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def is_available() -> bool:
    """Returns True when an OpenAI API key is configured."""
    return bool(settings.openai_api_key)
