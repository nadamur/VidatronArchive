#!/usr/bin/env python3
"""
Simple text-based chat test for testing the chatbot without audio hardware.
Just type your messages and the bot will respond!
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from brain.ollama_client import OllamaClient
from brain.router import Router, ToolType
from brain.tools.time_tool import get_current_time
from brain.tools.system_tool import get_system_status
from brain.tools.joke_tool import get_joke

def main():
    print("=" * 60)
    print("  Vidatron Local AI Chatbot - Text Mode Test")
    print("=" * 60)
    print()
    
    # Check if Ollama is available
    print("Connecting to Ollama...")
    ollama = OllamaClient(model="qwen2.5:1.5b")
    
    if not ollama.is_available():
        print("ERROR: Ollama is not running!")
        print("Start it with: ollama serve")
        sys.exit(1)
    
    print("✓ Connected to Ollama")
    print()
    
    # Initialize router
    router = Router(ollama)
    
    print("Chat with your local AI! Type 'quit' or 'exit' to end.")
    print("Try asking things like:")
    print("  - What time is it?")
    print("  - Tell me a joke")
    print("  - What's the system status?")
    print("  - Hello, how are you?")
    print()
    print("-" * 60)
    
    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                print("\nGoodbye! 👋")
                break
            
            # Process through router
            result = router.route(user_input)
            
            # Handle different tool types
            if result.tool == ToolType.NONE:
                print(f"\nBot: {result.response}")
                
            elif result.tool == ToolType.TIME:
                response = get_current_time()
                print(f"\nBot (Time): {response}")
                
            elif result.tool == ToolType.SYSTEM_STATUS:
                response = get_system_status()
                print(f"\nBot (System): {response}")
                
            elif result.tool == ToolType.JOKE:
                response = get_joke()
                print(f"\nBot (Joke): {response}")
                
            elif result.tool == ToolType.WEATHER:
                location = result.arguments.get("location", "your area")
                print(f"\nBot: Weather lookup for {location} requires OPENWEATHER_API_KEY")
                print("     (Add it to .env file to enable)")
                
            elif result.tool == ToolType.NEWS:
                print("\nBot: News lookup requires NEWSAPI_KEY")
                print("     (Add it to .env file to enable)")

            elif result.tool == ToolType.SPOTIFY_PLAY:
                q = result.arguments.get("query", "")
                print(f"\nBot: Would play on Spotify (configure SPOTIFY_* in .env): {q!r}")

            elif result.tool == ToolType.SPOTIFY_PAUSE:
                print("\nBot: Would pause Spotify (configure SPOTIFY_* in .env)")

            elif result.tool == ToolType.CLOUD:
                print("\nBot: This question would be routed to cloud AI (requires GROQ_API_KEY)")
                print("     (Add it to .env file to enable)")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye! 👋")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()
