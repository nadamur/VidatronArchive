"""
Tool definitions for Qwen2.5 function calling.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time and date. Use when user asks what time it is, what day it is, or current date.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather information for a location. Use when user asks about weather, temperature, or conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location (e.g., 'London', 'New York', 'Tokyo'). If not specified, use 'current location'."
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get top news headlines. Use when user asks about news, headlines, or what's happening in the world.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: business, entertainment, health, science, sports, or technology. Leave empty for general news."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Get the assistant's system health status including CPU temperature, memory, uptime. Use when user asks how you are doing, system status, or health check.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_joke",
            "description": "Tell a random joke. Use when user asks for a joke, wants to hear something funny, or asks you to make them laugh.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cloud_handoff",
            "description": "Hand off complex queries to cloud AI for better answers. Use for: creative writing, complex reasoning, coding questions, detailed explanations, anything requiring deep knowledge or nuanced responses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The full user query to send to cloud AI"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# System prompt for the router
SYSTEM_PROMPT = """You are Vidatron, a friendly healthy lifestyle AI assistant. You help users with daily tasks, answer questions, and encourage wellness.

ROUTING RULES:
1. Simple greetings (hi, hello, how are you) - respond directly
2. Time/date questions - use get_current_time
3. Weather questions - use get_weather
4. News/headlines - use get_news
5. System status ("how are you doing", health check) - use get_system_status
6. Jokes - use get_joke
7. Complex questions (facts about people, history, science, explanations, creative tasks, coding) - use cloud_handoff

When asked "who are you", say you are Vidatron, a healthy lifestyle robot and AI assistant.

Keep responses SHORT (1-2 sentences) since they will be spoken aloud."""
