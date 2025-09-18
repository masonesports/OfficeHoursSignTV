#!/usr/bin/env python3
"""
Simple script to run the Discord bot with token input
"""
import os
import sys
from discord_bot import bot
from config import DISCORD_TOKEN

def main():
    """Main function to run the Discord bot with interactive token input.
    
    This function provides an interactive way to start the Discord bot by
    prompting the user for a bot token. It handles token validation, sets
    the environment variable, and starts the bot with proper error handling.
    
    The function will:
    1. Display a welcome message
    2. Load Discord bot token from config
    3. Validate the token is not empty
    4. Set the token as an environment variable
    5. Start the bot with graceful shutdown handling
    
    Note: The bot will automatically push schedule changes to git
    when Discord commands that modify the schedule are executed.
    
    Side Effects:
        - Prints status messages to console
        - Sets DISCORD_TOKEN environment variable
        - Starts the Discord bot (blocking operation)
        - Handles keyboard interrupts and exceptions
        
    Raises:
        SystemExit: If no token is provided (exits with code 1)
        
    Example:
        python run_bot.py
        # Prompts: "Enter your Discord bot token: "
        # User enters token
        # Bot starts and runs until Ctrl+C
    """
    print("🤖 GMU Esports Schedule Discord Bot")
    print("=" * 40)
    
    # Get token from user input
    #token = input("Enter your Discord bot token: ").strip()
    token = DISCORD_TOKEN

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

if __name__ == "__main__":
    main()
