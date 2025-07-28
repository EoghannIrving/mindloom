"""Utility functions for interacting with the OpenAI API."""

from __future__ import annotations

import openai

from config import config


async def ask_chatgpt(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """Send a prompt to OpenAI ChatGPT and return the response text."""
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")

    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    chat_completion = await client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}]
    )
    return chat_completion.choices[0].message.content
