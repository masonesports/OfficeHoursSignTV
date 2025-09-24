#!/usr/bin/env python3
"""
Simple script to run the Discord bot with token from secrets.py
"""
import os
import sys
from discord_bot import bot
from secrets import DISCORD_TOKEN

def main():
    print("🤖 GMU Esports Schedule Discord Bot")
    print("=" * 40)
    
    # Get token from secrets.py
    token = DISCORD_TOKEN
    
    if not token:
        print("❌ No token found in secrets.py. Exiting.")
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

if __name__ == "__main__":
    main()
