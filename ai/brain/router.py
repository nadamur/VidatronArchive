"""
Main routing logic - single LLM for routing and chat.
Includes text-based tool detection fallback for smaller models.
"""

import re
from typing import Any, Callable, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .ollama_client import OllamaClient
from .tool_definitions import TOOLS, SYSTEM_PROMPT

# Temporary: skip local Ollama for chat — send every non-tool utterance to Groq (cloud).
# Set to False to restore local model for simple chat.
FORCE_GROQ_FOR_ALL = True


class ToolType(Enum):
    TIME = "get_current_time"
    WEATHER = "get_weather"
    NEWS = "get_news"
    SYSTEM_STATUS = "get_system_status"
    JOKE = "get_joke"
    SPOTIFY_PLAY = "spotify_play"
    SPOTIFY_PAUSE = "spotify_pause"
    CLOUD = "cloud_handoff"
    NONE = "none"  # Direct chat response


@dataclass
class RouterResult:
    """Result from the router."""
    tool: ToolType
    response: Optional[str]  # Direct response if no tool
    arguments: dict  # Tool arguments if tool called


class Router:
    """Routes user queries to appropriate handlers."""

    # Keywords for text-based tool detection (using word boundary matching)
    TIME_PHRASES = ["what time", "what's the time", "current time", "what day is it", "what's the date", "what date"]
    WEATHER_PHRASES = ["weather in", "weather for", "what's the weather", "how's the weather", "temperature in", "weather now", "weather today"]
    NEWS_PHRASES = ["news", "headlines", "what's happening", "whats happening", "current events", "top stories"]
    SYSTEM_PHRASES = ["system status", "how are you doing", "how are you feeling", "your temperature", "cpu temp", "health check", "how's your health", "how you doing"]
    JOKE_PHRASES = ["tell me a joke", "joke", "make me laugh", "something funny", "say something funny"]
    SPOTIFY_PAUSE_PHRASES = [
        "pause music",
        "pause spotify",
        "stop music",
        "stop spotify",
        "stop the music",
        "pause the music",
        "pause song",
        "stop playback",
        "pause playback",
        "turn off the music",
        "turn off music",
        "stop playing music",
        "pause the song",
    ]

    # Phrases that the local model can handle — simple chat, greetings, identity
    LOCAL_PHRASES = [
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "who are you", "what are you", "what's your name",
        "thank you", "thanks", "bye", "goodbye", "see you", "good night",
        "help", "what can you do", "nice to meet you", "how's it going",
    ]
    
    # Complex/creative tasks that need cloud AI
    CLOUD_PHRASES = [
        "write", "create", "compose", "generate", "make me", "draft",
        "explain", "describe", "analyze", "compare", "summarize",
        "how does", "why does", "what causes", "tell me about",
        "who is", "who was", "what is", "what was", "when did", "where is",
        "history of", "story about", "poem", "song", "essay", "code",
        "help me with", "can you explain", "teach me", "what do you think",
        "give me ideas", "suggest", "recommend", "advice",
    ]

    def __init__(
        self,
        ollama_client: OllamaClient,
        user_profile_getter: Optional[Callable[[], str]] = None,
    ):
        self.client = ollama_client
        self.user_profile_getter = user_profile_getter
        self.conversation_history = []

    def _is_local_chat(self, user_input: str) -> bool:
        """Check if the input is simple enough for the local model."""
        user_lower = user_input.lower().strip()
        
        # Check if it's a complex/creative task that needs cloud
        for phrase in self.CLOUD_PHRASES:
            if phrase in user_lower:
                return False  # Send to cloud
        
        # Short greetings / simple chat - handle locally
        for phrase in self.LOCAL_PHRASES:
            if phrase in user_lower:
                return True
        
        # Very short inputs (1-4 words) without question marks - likely simple
        words = user_lower.split()
        if len(words) <= 4 and "?" not in user_input:
            return True
        
        # Questions with "?" that are longer than 4 words - send to cloud
        if "?" in user_input and len(words) > 4:
            return False
            
        # Default: short stuff local, long stuff cloud
        return len(words) <= 6

    def _extract_news_category(self, user_input: str) -> str:
        """Extract news category from user input."""
        user_lower = user_input.lower()
        categories = ["business", "entertainment", "health", "science", "sports", "technology"]
        # Also match common synonyms
        synonyms = {"tech": "technology", "sport": "sports", "medical": "health"}
        for synonym, category in synonyms.items():
            if synonym in user_lower:
                return category
        for cat in categories:
            if cat in user_lower:
                return cat
        return ""

    def _detect_tool_from_text(self, user_input: str, response_text: str) -> Tuple[ToolType, dict]:
        """
        Detect tool from user input keywords and/or model response text.
        Fallback for models that don't use structured tool calls.
        """
        user_lower = user_input.lower()
        response_lower = (response_text or "").lower()

        # Priority 1: Check for tool mentions in model response (e.g., "[get_current_time]")
        if "get_current_time" in response_lower:
            return ToolType.TIME, {}

        if "get_weather" in response_lower:
            location = self._extract_location(user_input, response_text)
            return ToolType.WEATHER, {"location": location}

        if "get_news" in response_lower:
            category = self._extract_news_category(user_input)
            return ToolType.NEWS, {"category": category}

        if "get_system_status" in response_lower:
            return ToolType.SYSTEM_STATUS, {}

        if "get_joke" in response_lower:
            return ToolType.JOKE, {}

        if "spotify_play" in response_lower:
            q = self._extract_spotify_play_query(user_input)
            return ToolType.SPOTIFY_PLAY, {"query": q or user_input}

        if "spotify_pause" in response_lower:
            return ToolType.SPOTIFY_PAUSE, {}

        if "cloud_handoff" in response_lower:
            return ToolType.CLOUD, {"query": user_input}

        # Priority 2: Check for specific phrases in user input
        for phrase in self.SPOTIFY_PAUSE_PHRASES:
            if phrase in user_lower:
                return ToolType.SPOTIFY_PAUSE, {}

        q_play = self._extract_spotify_play_query(user_input)
        if q_play:
            return ToolType.SPOTIFY_PLAY, {"query": q_play}

        # Heuristic: "… on Spotify" / "… in Spotify" often means play that title
        spotify_tail = re.search(
            r"(?is)^(.{2,80}?)\s+on\s+spotify\s*[.!?]*\s*$",
            self._strip_voice_command_prefix(user_input).strip(),
        )
        if spotify_tail:
            q = self._clean_spotify_query_fragment(spotify_tail.group(1))
            if len(q) >= 2 and "weather" not in q.lower():
                return ToolType.SPOTIFY_PLAY, {"query": q}

        for phrase in self.TIME_PHRASES:
            if phrase in user_lower:
                return ToolType.TIME, {}

        for phrase in self.WEATHER_PHRASES:
            if phrase in user_lower:
                location = self._extract_location(user_input, "")
                return ToolType.WEATHER, {"location": location}

        for phrase in self.NEWS_PHRASES:
            if phrase in user_lower:
                category = self._extract_news_category(user_input)
                return ToolType.NEWS, {"category": category}

        for phrase in self.JOKE_PHRASES:
            if phrase in user_lower:
                return ToolType.JOKE, {}

        for phrase in self.SYSTEM_PHRASES:
            if phrase in user_lower:
                return ToolType.SYSTEM_STATUS, {}

        # Priority 3: If it's simple chat, keep local
        if self._is_local_chat(user_input):
            return ToolType.NONE, {}

        # Priority 4: Everything else → cloud handoff
        # The local 1.5B model can't reliably answer knowledge/technical questions
        return ToolType.CLOUD, {"query": user_input}

    def _extract_location(self, user_input: str, response_text: str) -> str:
        """Extract location from user input or response."""
        # Try to find location in model response
        match = re.search(r'location["\s=:]+["\']*([^"\'\]\s,]+)', response_text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Try common patterns in user input
        patterns = [
            r"weather (?:in|for|at) ([A-Za-z\s]+)",
            r"in ([A-Za-z]+)",
            r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"  # Capitalized words
        ]

        for pattern in patterns:
            match = re.search(pattern, user_input)
            if match:
                loc = match.group(1).strip()
                # Filter out common words
                if loc.lower() not in ["the", "is", "it", "what", "how", "like"]:
                    return loc

        return ""  # No location found, orchestrator will use config default

    def _strip_voice_command_prefix(self, text: str) -> str:
        """Remove leading wake-style phrase so 'Hey Vidatron, play X' → 'play X'."""
        s = text.strip()
        s = re.sub(
            r"(?is)^\s*(?:hey|ok|okay)[,.\s]+(?:vidatron|veedatron|jansky)\b[,.\s!]*",
            "",
            s,
        )
        s = re.sub(
            r"(?is)^\s*(?:vidatron|veedatron|jansky)\b[,.\s!]+",
            "",
            s,
        )
        return s.strip()

    def _clean_spotify_query_fragment(self, raw: str) -> str:
        q = raw.strip().strip('"').strip("'").rstrip(".,!?")
        # Drop trailing "on spotify" / "in spotify"
        q = re.sub(r"(?i)\s+on\s+spotify\s*$", "", q).strip()
        q = re.sub(r"(?i)\s+in\s+spotify\s*$", "", q).strip()
        return q

    def _extract_spotify_play_query(self, user_input: str) -> str:
        """Parse natural play requests into a Spotify search string."""
        s = self._strip_voice_command_prefix(user_input.strip())
        if len(s) < 3:
            return ""
        low = s.lower()
        for bad in ("play a game", "play the game", "playing a game", "play with me", "play with us"):
            if bad in low:
                return ""

        polite = (
            r"(?:can you |could you |can we |could we |please |will you |would you )?"
        )

        m = re.search(
            r"(?is)(?:^|[.!?]\s*)" + polite
            + r"play\s+(?:me\s+)?(?:the\s+)?(?:song\s+|track\s+|music\s+)?(.+)$",
            s,
        )
        if m:
            q = self._clean_spotify_query_fragment(m.group(1))
            return q if len(q) >= 2 else ""

        m2 = re.search(r"(?is)(?:^|[.!?]\s*)" + polite + r"put\s+on\s+(.+)$", s)
        if m2:
            q = self._clean_spotify_query_fragment(m2.group(1))
            return q if len(q) >= 2 else ""

        m3 = re.match(r"(?i)^start\s+playing\s+(.+)$", s)
        if m3:
            q = self._clean_spotify_query_fragment(m3.group(1))
            return q if len(q) >= 2 else ""

        # "I'd like to hear …" / "I want to listen to …"
        m4 = re.search(
            r"(?is)^(?:i'?d|i would)\s+like\s+to\s+(?:hear|listen\s+to)\s+(.+)$",
            s,
        )
        if m4:
            q = self._clean_spotify_query_fragment(m4.group(1))
            return q if len(q) >= 2 else ""

        m5 = re.search(r"(?is)^i\s+want\s+to\s+(?:hear|listen\s+to)\s+(.+)$", s)
        if m5:
            q = self._clean_spotify_query_fragment(m5.group(1))
            return q if len(q) >= 2 else ""

        m5b = re.search(
            r"(?is)^i\s+want\s+to\s+play\s+(?:the\s+)?(?:song\s+|track\s+|music\s+)?(.+)$",
            s,
        )
        if m5b:
            q = self._clean_spotify_query_fragment(m5b.group(1))
            return q if len(q) >= 2 else ""

        m4b = re.search(
            r"(?is)^(?:i'?d|i would)\s+like\s+to\s+play\s+(?:the\s+)?(?:song\s+|track\s+|music\s+)?(.+)$",
            s,
        )
        if m4b:
            q = self._clean_spotify_query_fragment(m4b.group(1))
            return q if len(q) >= 2 else ""

        # "Play something by The Beatles" → search query (artist-style)
        m6 = re.search(
            r"(?is)^" + polite
            + r"play\s+something\s+by\s+(.+)$",
            s,
        )
        if m6:
            q = self._clean_spotify_query_fragment(m6.group(1))
            return q if len(q) >= 2 else ""

        # Last resort: "... play <title>" (e.g. "Can we play X", long wake prefix then play).
        # Skip common negations like "don't play".
        if not re.search(r"(?is)\b(?:do\s*not|don'?t|never|not)\s+play\b", low):
            m7 = re.search(
                r"(?is)\bplay\s+(?:the\s+)?(?:song\s+|track\s+|music\s+)?(.+)$",
                s,
            )
            if m7:
                q = self._clean_spotify_query_fragment(m7.group(1))
                if len(q) >= 2:
                    return q

        return ""

    def route(self, user_input: str) -> RouterResult:
        """
        Route user input to appropriate handler.
        Uses fast keyword-based routing first, then falls back to LLM for chat.
        """
        # FAST PATH: Check for tools using keywords (no LLM call needed)
        tool_type, arguments = self._detect_tool_from_text(user_input, "")
        
        if tool_type != ToolType.NONE and tool_type != ToolType.CLOUD:
            # Direct tool match (time, weather, jokes, etc.)
            print(f"  [Router] Fast match: {tool_type.name}")
            self.conversation_history.append({"role": "user", "content": user_input})
            return RouterResult(tool=tool_type, response=None, arguments=arguments)

        if FORCE_GROQ_FOR_ALL:
            print("  [Router] Temporary: all chat via Groq (skipping local model)")
            self.conversation_history.append({"role": "user", "content": user_input})
            query = arguments.get("query", user_input)
            return RouterResult(
                tool=ToolType.CLOUD,
                response=None,
                arguments={"query": query},
            )

        # Check if it's simple chat that local model can handle
        if self._is_local_chat(user_input):
            print("  [Router] Simple chat - using local model")
            # Get response from local model
            system = (
                "You are Vidatron, a friendly healthy lifestyle AI assistant. When asked who you are, "
                "say you are Vidatron, a healthy lifestyle robot and AI assistant. Keep responses SHORT (1-2 sentences)."
            )
            if self.user_profile_getter:
                ctx = (self.user_profile_getter() or "").strip()
                if ctx:
                    system += "\n\n--- User facts ---\n" + ctx
            messages = [{"role": "system", "content": system}]
            messages.extend(self.conversation_history[-4:])
            messages.append({"role": "user", "content": user_input})
            
            try:
                response = self.client.chat(messages, tools=None)
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": response.content or ""})
                return RouterResult(tool=ToolType.NONE, response=response.content, arguments={})
            except Exception as e:
                print(f"  [Router] LLM error: {e}")
                return RouterResult(tool=ToolType.NONE, response="I'm having trouble thinking right now.", arguments={})
        
        # Complex question - route to cloud
        print(f"  [Router] Complex question - routing to cloud")
        self.conversation_history.append({"role": "user", "content": user_input})
        return RouterResult(tool=ToolType.CLOUD, response=None, arguments={"query": user_input})

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
