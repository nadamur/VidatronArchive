"""
Cloud API client for Kimi K2 (Moonshot).

TEMPORARILY DISABLED for cloud routing: Vidatron uses ``GroqClient`` from
``brain.groq_client`` instead of Moonshot/Kimi here.
Restore by renaming ``_KimiClientDisabled`` back to ``KimiClient`` and
wiring ``test_ui`` to instantiate it again.
"""

import httpx
import json
from typing import Generator, Optional, Union
from pathlib import Path
import os
class _KimiClientDisabled:
    """
    Moonshot Kimi (OpenAI-compatible /v1/chat/completions).

    Unused in the app while cloud routing uses ``GroqClient``.
    Rename to ``KimiClient`` and wire imports to re-enable.
    """
    
    BASE_URL = "https://api.moonshot.ai/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        soul_path: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        if not self.api_key:
            raise ValueError("Moonshot API key required")
        
        self.client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
        # Load cloud soul/personality
        self.soul_prompt = ""
        if soul_path and Path(soul_path).exists():
            self.soul_prompt = Path(soul_path).read_text()
    
    def chat(
        self,
        query: str,
        stream: bool = True
    ) -> Union[Generator[str, None, None], str]:
        """
        Send query to Kimi K2.
        
        Args:
            query: User query
            stream: Whether to stream response
        
        Returns:
            Generated response (streamed or complete)
        """
        messages = []
        
        # Add soul/personality if available
        if self.soul_prompt:
            messages.append({
                "role": "system",
                "content": self.soul_prompt
            })
        
        messages.append({
            "role": "user",
            "content": query
        })
        
        payload = {
            "model": "kimi-k2-0905-preview",
            "messages": messages,
            "temperature": 0.7,
            "stream": stream
        }
        
        if stream:
            return self._stream_chat(payload)
        else:
            response = self.client.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    
    def _stream_chat(self, payload: dict) -> Generator[str, None, None]:
        """Stream chat response."""
        with self.client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            json=payload
        ) as response:
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
