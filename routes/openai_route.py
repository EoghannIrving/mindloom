"""FastAPI router for interacting with the OpenAI API."""

from fastapi import APIRouter, Body

from openai_client import ask_chatgpt

router = APIRouter()


@router.post("/ask")
async def ask_endpoint(data: dict = Body(...)):
    """Send the provided prompt to ChatGPT and return the response."""
    prompt: str = data.get("prompt", "")
    if not prompt:
        return {"error": "Prompt is required"}

    response = await ask_chatgpt(prompt)
    return {"response": response}
