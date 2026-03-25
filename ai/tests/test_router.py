#!/usr/bin/env python3
"""
Test the router and LLM integration.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.ollama_client import OllamaClient
from brain.router import Router, ToolType


def test_router():
    """Test routing decisions."""
    
    client = OllamaClient(model="qwen2.5:1.5b")
    
    if not client.is_available():
        print("✗ Ollama not running!")
        print("  Start with: ollama serve")
        return False
    
    print("✓ Ollama is running")
    
    router = Router(client)
    
    test_cases = [
        # (input, expected_tool)
        ("Hello, how are you?", ToolType.CLOUD),  # FORCE_GROQ_FOR_ALL in router
        ("What time is it?", ToolType.TIME),
        ("What's the weather in London?", ToolType.WEATHER),
        ("Write me a poem about stars", ToolType.CLOUD),
        ("Tell me a joke", ToolType.JOKE),
        ("play bohemian rhapsody", ToolType.SPOTIFY_PLAY),
        ("Hey Vidatron, play nevermind", ToolType.SPOTIFY_PLAY),
        ("Can we play Bohemian Rhapsody", ToolType.SPOTIFY_PLAY),
        ("I want to play Greedy by Tate McRae", ToolType.SPOTIFY_PLAY),
        ("I'd like to hear blurred lines", ToolType.SPOTIFY_PLAY),
        ("bohemian rhapsody on Spotify", ToolType.SPOTIFY_PLAY),
        ("pause music", ToolType.SPOTIFY_PAUSE),
    ]
    
    print("\nTesting router decisions...\n")
    
    passed = 0
    for user_input, expected in test_cases:
        result = router.route(user_input)
        status = "✓" if result.tool == expected else "✗"
        if result.tool == expected:
            passed += 1
        
        print(f"{status} Input: '{user_input}'")
        print(f"   Expected: {expected.value}, Got: {result.tool.value}")
        if result.response:
            print(f"   Response: {result.response[:80]}...")
        print()
    
    print(f"Router test complete: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


if __name__ == "__main__":
    success = test_router()
    sys.exit(0 if success else 1)
