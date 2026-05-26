"""
Thin wrapper so Groq can be used with the same client.messages.create() interface
that the rest of ig_brain expects from the Anthropic client.
"""
import os
from groq import Groq

# Map Anthropic model names → Groq equivalents
_MODEL_MAP = {
    "claude-sonnet-4-5":        "llama-3.3-70b-versatile",
    "claude-haiku-4-5-20251001": "llama-3.1-8b-instant",
    "claude-haiku-4-5":         "llama-3.1-8b-instant",
    "claude-opus-4-7":          "llama-3.3-70b-versatile",
}


class _Message:
    def __init__(self, text):
        self.text = text


class _Content:
    def __init__(self, text):
        self.content = [_Message(text)]


class GroqClientWrapper:
    """Drop-in replacement for anthropic.Anthropic() client."""

    def __init__(self, api_key: str = ""):
        self.messages = self
        self._groq = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY", ""))

    def create(self, model: str, max_tokens: int, messages: list,
               system: str = "", **kwargs) -> _Content:
        groq_model = _MODEL_MAP.get(model, "llama-3.3-70b-versatile")
        groq_messages = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        resp = self._groq.chat.completions.create(
            model=groq_model,
            max_tokens=max_tokens,
            messages=groq_messages,
        )
        text = resp.choices[0].message.content or ""
        return _Content(text)
