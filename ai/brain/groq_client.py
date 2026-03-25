"""
Groq Cloud API client (OpenAI-compatible chat completions).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator, Optional, Union

import httpx


class GroqClient:
    """Chat completion via Groq's OpenAI-compatible endpoint."""

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        soul_path: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required (GROQ_API_KEY)")

        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        self.client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        self.soul_prompt = ""
        if soul_path and Path(soul_path).exists():
            self.soul_prompt = Path(soul_path).read_text()

    def chat(
        self,
        query: str,
        stream: bool = True,
        user_profile_context: str = "",
    ) -> Union[Generator[str, None, None], str]:
        messages = []
        system_parts: list[str] = []
        if self.soul_prompt:
            system_parts.append(self.soul_prompt)
        up = (user_profile_context or "").strip()
        if up:
            system_parts.append(
                "--- User facts (use when relevant; do not contradict) ---\n" + up
            )
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        messages.append({"role": "user", "content": query})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": stream,
        }

        if stream:
            return self._stream_chat(payload)

        response = self.client.post(
            f"{self.BASE_URL}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _stream_chat(self, payload: dict) -> Generator[str, None, None]:
        with self.client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue
