"""
Test script for intent detection functionality.
This script tests the detect_intent function without running the full bot.
"""
import asyncio
import os

# Set mock env vars for testing
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "mock_key")
os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "mock_token")

import ai_service

async def test_intent_detection():
    """Test various intent detection scenarios."""
    
    test_cases = [
        # Summary requests
        ("Give me a recap of yesterday", "summary", "1d"),
        ("Show me what happened in the last week", "summary", "1w"),
        ("Summarize the last hour", "summary", "1h"),
        ("What did we discuss today?", "summary", "1d"),
        
        # Chat requests
        ("Hello", "chat", None),
        ("What can you do?", "chat", None),
        ("Help me", "chat", None),
        
        # User search requests
        ("What did Alice say?", "search", None),
        ("Show messages from Bob", "search", None),
        ("Any updates from @charlie?", "search", None),
    ]
    
    print("Testing Intent Detection\n" + "="*50)
    
    for user_text, expected_action, expected_timeframe in test_cases:
        print(f"\nUser: \"{user_text}\"")
        try:
            result = await ai_service.detect_intent(user_text)
            print(f"Action: {result['action']}")
            
            if result['action'] == 'summary':
                print(f"Timeframe: {result.get('timeframe', 'N/A')}")
                if expected_timeframe:
                    match = result.get('timeframe') == expected_timeframe
                    print(f"✓ Correct" if match else f"✗ Expected {expected_timeframe}")
            elif result['action'] == 'search':
                print(f"Keywords: '{result.get('keywords', '')}'")
                print(f"Username: '{result.get('username', 'None')}'")
            elif result['action'] == 'chat':
                print(f"Reply: {result.get('reply', 'N/A')[:100]}...")
                
            print(f"Status: {'✓ PASS' if result['action'] == expected_action else '✗ FAIL'}")
            
        except Exception as e:
            print(f"✗ ERROR: {e}")
    
    print("\n" + "="*50)
    print("Testing complete!")

if __name__ == "__main__":
    # Check if API key is set
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("⚠️  GROQ_API_KEY or OPENAI_API_KEY not set. This test requires a valid API key.")
        print("Set it in your .env file or export it as an environment variable.")
    else:
        asyncio.run(test_intent_detection())
