import asyncio
import os
from datetime import date, timedelta
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from app import (
    set_default_time, set_default_bulk, temp_change, 
    temp_change_week, load_schedule_model, effective_week_schedule,
    start_of_week_monday
)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Sync commands tree
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# Helper function to format schedule for Discord
def format_schedule_for_discord(rows):
    """Format schedule rows for Discord display."""
    lines = ["**GMU Esports Office Hours Schedule**", "```"]
    for day_name, date_str, time_str in rows:
        status = time_str if time_str else "—"
        lines.append(f"{day_name} ({date_str}): {status}")
    lines.append("```")
    return "\n".join(lines)

# Slash Commands with autocomplete
@bot.tree.command(name="hours", description="Show the current week's office hours schedule")
async def show_schedule(interaction: discord.Interaction):
    """Show the current week's schedule."""
    try:
        # Show current week
        week_monday = start_of_week_monday(date.today())
        rows = effective_week_schedule(week_monday)
        title = "**Current Week's Schedule**"
        
        schedule_text = format_schedule_for_discord(rows)
        await interaction.response.send_message(f"{title}\n{schedule_text}")
    except Exception as e:
        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="set_default", description="Set default time for a weekday")
@app_commands.describe(
    day="Day of the week",
    start_time="Start time in 24-hour format (e.g., 14:00)",
    end_time="End time in 24-hour format (e.g., 17:00)"
)
@app_commands.choices(day=[
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday")
])
async def set_default_command(interaction: discord.Interaction, day: str, start_time: str = "", end_time: str = ""):
    """Set default time for a weekday."""
    try:
        set_default_time(day, start_time, end_time)
        status = f"{start_time}-{end_time}" if start_time and end_time else "CLOSED"
        await interaction.response.send_message(f"✅ Set default for {day}: {status}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="change_day", description="Change hours for a specific date")
@app_commands.describe(
    date_mmdd="Date in MM/DD format (e.g., 09/16)",
    status="Is the office open or closed?",
    start_time="Start time in 24-hour format (e.g., 14:00) - only if open",
    end_time="End time in 24-hour format (e.g., 17:00) - only if open",
    reason="Reason for closing - only if closed"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Open", value="open"),
    app_commands.Choice(name="Closed", value="closed")
])
async def change_day_command(interaction: discord.Interaction, date_mmdd: str, status: str, start_time: str = "", end_time: str = "", reason: str = "Closed"):
    """Change hours for a specific date."""
    try:
        if status == "open":
            if not start_time or not end_time:
                await interaction.response.send_message("❌ Please provide both start_time and end_time when status is open", ephemeral=True)
                return
            temp_change(date_mmdd, start_time, end_time)
            status_text = f"{start_time}-{end_time}"
        else:  # closed
            from app import _model, save_schedule_model
            _d = date_mmdd
            _model["overrides"][_d] = f"CLOSED ({reason})"
            save_schedule_model(_model)
            status_text = f"CLOSED ({reason})"
        
        await interaction.response.send_message(f"✅ Set override for {date_mmdd}: {status_text}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)




@bot.tree.command(name="test", description="Test if the bot is working")
async def test_command(interaction: discord.Interaction):
    """Test command to verify bot is working."""
    await interaction.response.send_message("🤖 Bot is working! Use `/hours` to see the current schedule.")

@bot.tree.command(name="close_day", description="Close a specific day with a reason")
@app_commands.describe(
    date_mmdd="Date in MM/DD format (e.g., 09/16)",
    reason="Reason for closing (e.g., Holiday, Maintenance, etc.)"
)
async def close_day_command(interaction: discord.Interaction, date_mmdd: str, reason: str = "Closed"):
    """Close a specific day with a reason."""
    try:
        temp_change(date_mmdd, "", "")  # This sets it to CLOSED
        # Update the override to include the reason
        from app import _model, save_schedule_model
        _d = date_mmdd  # Use the date as-is for simplicity
        _model["overrides"][_d] = f"CLOSED ({reason})"
        save_schedule_model(_model)
        await interaction.response.send_message(f"✅ Closed {date_mmdd}: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="close_weekday", description="Close a weekday with a reason")
@app_commands.describe(
    day="Day of the week to close",
    reason="Reason for closing (e.g., Holiday, Maintenance, etc.)"
)
@app_commands.choices(day=[
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday")
])
async def close_weekday_command(interaction: discord.Interaction, day: str, reason: str = "Closed"):
    """Close a weekday with a reason."""
    try:
        set_default_time(day, "", "")  # This sets it to CLOSED
        # Update the default to include the reason
        from app import _model, save_schedule_model
        _model["default"][day] = f"CLOSED ({reason})"
        save_schedule_model(_model)
        await interaction.response.send_message(f"✅ Closed {day}: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


if __name__ == "__main__":
    # Try to get token from bot_config file first, then environment
    token = None
    try:
        from bot_config import DISCORD_TOKEN
        token = DISCORD_TOKEN
        print("✅ Token loaded from bot_config.py")
    except ImportError:
        token = os.getenv('DISCORD_TOKEN')
        if token:
            print("✅ Token loaded from environment variable")
    
    if not token:
        print("❌ Please set DISCORD_TOKEN in secrets.py, config.py, or environment variable")
        print("Create secrets.py with: DISCORD_TOKEN = 'your_token_here'")
        exit(1)
    
    print("🤖 Starting Discord bot...")
    bot.run(token)
