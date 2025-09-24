#!/usr/bin/env python3
"""
Simple script to run the Discord bot with token input
"""
import os
import sys
from discord_bot import bot

def main():
    print("🤖 GMU Esports Schedule Discord Bot")
    print("=" * 40)
    
    # Get token from user input
    token = input("Enter your Discord bot token: ").strip()
    
    if not token:
        print("❌ No token provided. Exiting.")
        sys.exit(1)
    
    # Set the token as environment variable
    os.environ['DISCORD_TOKEN'] = token
    
    print("✅ Token set. Starting bot...")
    print("Press Ctrl+C to stop the bot")
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")
    except Exception as e:
        print(f"❌ Error: {e}")
# MTQxNzYyNjk0MjkzNjcxMTE4OQ.GeSrb-.Ixg8QCFPhmkCrHbd75tqZzo_OY9AY5ptrWOlKo
if __name__ == "__main__":
    main()
