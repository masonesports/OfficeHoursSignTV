# Discord Bot Setup Guide

## 1. Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" and give it a name (e.g., "GMU Esports Schedule Bot")
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Copy the bot token (keep this secret!)

## 2. Set Bot Permissions

1. Go to the "OAuth2" > "URL Generator" section
2. Select scopes: `bot`
3. Select bot permissions:
   - Send Messages
   - Use Slash Commands
   - Read Message History
   - Add Reactions
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Set Environment Variable

```bash
export DISCORD_TOKEN='your_bot_token_here'
```

Or create a `.env` file:
```
DISCORD_TOKEN=your_bot_token_here
```

## 5. Run the Bot

```bash
python discord_bot.py
```

## 6. Available Commands

- `!schedule` - Show current week's schedule
- `!schedule next` - Show next week's schedule
- `!set_default Monday 14:00 17:00` - Set default for Monday (2-5 PM)
- `!set_default Wednesday` - Set Wednesday to CLOSED
- `!set_override 09/16 10:00 12:00` - Override specific date
- `!set_override 09/17` - Set specific date to CLOSED
- `!set_week 09/23 Monday:14:00-17:00 Tuesday:09:00-12:00` - Set whole week
- `!show_data` - Show raw schedule data
- `!help_schedule` - Show help
- `!test` - Test if bot is working

## 7. Examples

```bash
# Set Monday default to 2-5 PM
!set_default Monday 14:00 17:00

# Override next Tuesday to 10 AM - 12 PM
!set_override 09/24 10:00 12:00

# Set a whole week with different times
!set_week 09/23 Monday:14:00-17:00 Tuesday:09:00-12:00 Wednesday:13:00-16:00

# Show current schedule
!schedule

# Show next week
!schedule next
```

## 8. Running Both Flask and Discord Bot

You can run both simultaneously:

Terminal 1 (Flask web server):
```bash
python app.py
```

Terminal 2 (Discord bot):
```bash
python discord_bot.py
```

The Discord bot will automatically update the same `schedule.json` file that the web interface uses!
