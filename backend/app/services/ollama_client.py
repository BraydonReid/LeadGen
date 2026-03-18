"""
Async HTTP wrapper for the local Ollama inference server.
Ollama must be running at settings.ollama_base_url (http://ollama:11434 in Docker).
"""
import httpx
from app.config import settings


async def generate(model: str, prompt: str, temperature: float = 0.1) -> str:
    """
    Send a prompt to Ollama and return the response text.
    Uses stream=False for simplicity (waits for full response).
    Raises httpx.HTTPError on failure.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()


async def is_available() -> bool:
    """Returns True if Ollama is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
