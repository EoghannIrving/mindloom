"""Utility functions for interacting with the OpenAI API."""

from __future__ import annotations

import logging
from pathlib import Path

import openai

from config import config


class OpenAIClientError(Exception):
    """Raised when the OpenAI client encounters an error."""


LOG_FILE = Path(config.LOG_DIR) / "openai_client.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


async def ask_chatgpt(
    prompt: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 500,
) -> str:
    """Send a prompt to OpenAI ChatGPT and return the response text."""
    if not config.OPENAI_API_KEY:
        raise OpenAIClientError("OPENAI_API_KEY is not configured")

    messages = [{"role": "user", "content": prompt}]
    prompt_length = len(prompt)
    logger.info(
        "Sending ChatGPT request: model=%s max_tokens=%s prompt_length=%s",
        model,
        max_tokens,
        prompt_length,
    )
    if prompt:
        preview = prompt[:200]
        if len(preview) < prompt_length:
            preview = f"{preview}…"
        logger.debug("ChatGPT prompt preview: %s", preview)
    try:
        async with openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY) as client:
            chat_completion = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            return chat_completion.choices[0].message.content
    except openai.OpenAIError as exc:
        logger.exception("OpenAI API request failed")
        raise OpenAIClientError("OpenAI API request failed") from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Unexpected error while calling OpenAI API")
        raise OpenAIClientError("Unexpected error while calling OpenAI API") from exc
