#!/usr/bin/env python3
"""
Test script to check if the bot can start without errors
"""

import sys
import os

def test_imports():
    """Test if all imports work correctly"""
    try:
        print("Testing imports...")
        
        # Test basic imports
        import pyrogram
        print("✅ pyrogram imported successfully")
        
        import aiohttp
        print("✅ aiohttp imported successfully")
        
        import requests
        print("✅ requests imported successfully")
        
        # Test local imports
        from vars import API_ID, API_HASH, BOT_TOKEN, OWNER, OWNER_USERNAME, CREDIT
        print("✅ vars imported successfully")
        print(f"   API_ID: {API_ID}")
        print(f"   OWNER: {OWNER}")
        print(f"   OWNER_USERNAME: {OWNER_USERNAME}")
        print(f"   CREDIT: {CREDIT}")
        
        from utils import progress_bar
        print("✅ utils imported successfully")

        import handler as helper
        print("✅ handler imported successfully")
        
        from logs import logging
        print("✅ logs imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {str(e)}")
        return False

def test_environment_variables():
    """Test environment variable handling"""
    try:
        print("\nTesting environment variables...")
        
        # Test AUTH_USERS handling
        AUTH_USER_ENV = os.environ.get('AUTH_USERS', '7527795504')
        if AUTH_USER_ENV:
            AUTH_USER = AUTH_USER_ENV.split(',')
        else:
            AUTH_USER = ['7527795504']
        
        AUTH_USER.append('5680454765')
        AUTH_USERS = [int(user_id) for user_id in AUTH_USER if user_id.strip().isdigit()]
        print(f"✅ AUTH_USERS processed: {AUTH_USERS}")
        
        # Test CHANNELS handling
        CHANNELS_ENV = os.environ.get('CHANNELS', '')
        if CHANNELS_ENV:
            CHANNELS = CHANNELS_ENV.split(',')
        else:
            CHANNELS = []
        CHANNELS_LIST = [int(channel_id) for channel_id in CHANNELS if channel_id.strip().isdigit()]
        print(f"✅ CHANNELS_LIST processed: {CHANNELS_LIST}")
        
        return True
        
    except Exception as e:
        print(f"❌ Environment variable error: {str(e)}")
        return False

def test_bot_initialization():
    """Test if bot can be initialized"""
    try:
        print("\nTesting bot initialization...")

        from vars import API_ID, API_HASH, BOT_TOKEN, OWNER_USERNAME
        from pyrogram import Client
        
        # Initialize the bot (don't start it)
        bot = Client(
            "test_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        print("✅ Bot initialized successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot initialization error: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🔍 Starting bot diagnostics...\n")
    
    tests = [
        test_imports,
        test_environment_variables,
        test_bot_initialization
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The bot should start without 'NoneType' errors.")
        print("\n📋 Available Commands:")
        print("   🌐 Public Commands:")
        print("   • /start - Bot status and welcome")
        print("   • /help - Show commands list")
        print("   • /id - Get chat/user ID")
        print("   • /info - Get user information")
        print("\n   🔒 AUTH_USERS Only Commands:")
        print("   • /drm - Extract from .txt files")
        print("   • /cookies - Update YouTube cookies")
        print("   • /y2t - YouTube to .txt converter")
        print("   • /t2t - Text to .txt generator")
        print("   • /stop - Cancel running tasks")
        print("   • /logs - View bot activity")
        print("   • /add_channel -100xxxx (or /addchnl -100xxxx)")
        print("   • /remove_channel -100xxxx (or /remchnl -100xxxx)")
        print("   • Single link processing")
        print("\n   👑 OWNER Only Commands:")
        print("   • /add_user xxxx (or /addauth xxxx)")
        print("   • /remove_user xxxx (or /remauth xxxx)")
        print("   • /users - List authorized users")
        print("   • /channels - List authorized channels")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
