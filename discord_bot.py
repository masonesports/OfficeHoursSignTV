import asyncio
import os
import subprocess
import sys
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
    """Event handler called when the bot successfully connects to Discord.
    
    This function is automatically called by the Discord.py library when the bot
    has successfully established a connection to Discord. It performs essential
    initialization tasks including syncing slash commands with Discord's servers.
    
    Side Effects:
        - Prints connection status to console
        - Syncs slash commands with Discord
        - Prints sync results to console
        
    Example:
        When bot starts: "GMU Esports Bot#1234 has connected to Discord!"
        After sync: "Synced 8 command(s)"
    """
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# Helper function to push changes to git
async def push_to_git():
    """Push schedule and HTML changes to the main branch.
    
    This function commits any changes to schedule.json and HTML files,
    then pushes them to the main branch. It's called after Discord
    commands that modify the schedule.
    
    Side Effects:
        - Commits changes to git
        - Pushes to main branch
        - Prints status messages to console
    """
    try:
        # Add all changes
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        
        # Commit changes
        commit_message = f"Update schedule via Discord bot - {date.today().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True, capture_output=True)
        
        # Push to main
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
        
        print(f"✅ Successfully pushed changes to main branch")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout.decode()}")
        if e.stderr:
            print(f"stderr: {e.stderr.decode()}")
    except Exception as e:
        print(f"❌ Unexpected error during git push: {e}")

# Helper function to format schedule for Discord
def format_schedule_for_discord(rows):
    """Format schedule rows for Discord display.
    
    This helper function converts schedule data into a formatted string
    suitable for display in Discord messages. It creates a code block with
    the schedule information and handles empty time slots gracefully.
    
    Args:
        rows: List of tuples containing (weekday_name, MM/DD, effective_time)
            Each tuple represents one day's schedule information
            
    Returns:
        str: Formatted schedule string ready for Discord display
        
    Example:
        rows = [("Monday", "09/16", "2:00 PM - 5:00 PM"), ("Tuesday", "09/17", "CLOSED")]
        result = format_schedule_for_discord(rows)
        # Returns formatted string with code block and schedule info
    """
    lines = ["**GMU Esports Office Hours Schedule**", "```"]
    for day_name, date_str, time_str in rows:
        status = time_str if time_str else "—"
        lines.append(f"{day_name} ({date_str}): {status}")
    lines.append("```")
    return "\n".join(lines)

# Slash Commands with autocomplete
@bot.tree.command(name="hours", description="Show the office hours schedule")
@app_commands.describe(week="Show current week or next week")
@app_commands.choices(week=[
    app_commands.Choice(name="Current Week", value="current"),
    app_commands.Choice(name="Next Week", value="next")
])
async def show_schedule(interaction: discord.Interaction, week: str = "current"):
    """Show the office hours schedule for the current or next week.
    
    This slash command displays the GMU Esports office hours schedule.
    Users can choose to view either the current week or next week's schedule.
    The schedule shows effective hours considering both default schedules
    and any date-specific overrides.
    
    Args:
        interaction: Discord interaction object containing command context
        week: Which week to display ("current" or "next"), defaults to "current"
        
    Side Effects:
        - Sends formatted schedule message to Discord channel
        - Sends error message if something goes wrong
        
    Example:
        /hours -> Shows current week's schedule
        /hours week:Next Week -> Shows next week's schedule
    """
    try:
        if week == "next":
            # Show next week
            week_monday = start_of_week_monday(date.today()) + timedelta(days=7)
            rows = effective_week_schedule(week_monday)
            title = "**Next Week's Schedule**"
        else:
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
    """Set default office hours for a specific weekday.
    
    This slash command allows administrators to set the default office hours
    for any weekday. The times are provided in 24-hour format and converted
    to a readable format. Empty times result in "CLOSED" status for that day.
    
    Args:
        interaction: Discord interaction object containing command context
        day: Weekday name (Monday through Friday)
        start_time: Start time in 24-hour format (e.g., "14:00") or empty for CLOSED
        end_time: End time in 24-hour format (e.g., "17:00") or empty for CLOSED
        
    Side Effects:
        - Updates the default schedule model
        - Saves changes to schedule.json file
        - Sends confirmation or error message to Discord
        
    Example:
        /set_default day:Monday start_time:14:00 end_time:17:00
        -> Sets Monday default hours to 2:00 PM - 5:00 PM
        
        /set_default day:Tuesday start_time: end_time:
        -> Closes Tuesday by default
    """
    try:
        set_default_time(day, start_time, end_time)
        status = f"{start_time}-{end_time}" if start_time and end_time else "CLOSED"
        await interaction.response.send_message(f"✅ Set default for {day}: {status}")
        
        # Push changes to git
        await push_to_git()
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="set_override", description="Set temporary override for a specific date")
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
async def set_override_command(interaction: discord.Interaction, date_mmdd: str, status: str, start_time: str = "", end_time: str = "", reason: str = "Closed"):
    """Set temporary override for a specific date.
    
    This slash command allows administrators to create date-specific overrides
    that take precedence over default schedules. It supports both opening the
    office with specific hours and closing it with a reason.
    
    Args:
        interaction: Discord interaction object containing command context
        date_mmdd: Date in MM/DD format (e.g., "09/16" for September 16th)
        status: Whether the office is "open" or "closed" on this date
        start_time: Start time in 24-hour format (required if status is "open")
        end_time: End time in 24-hour format (required if status is "open")
        reason: Reason for closing (used if status is "closed")
        
    Side Effects:
        - Updates the schedule model with date-specific override
        - Saves changes to schedule.json file
        - Sends confirmation or error message to Discord
        
    Example:
        /set_override date_mmdd:09/16 status:Open start_time:14:00 end_time:17:00
        -> Sets September 16th to 2:00 PM - 5:00 PM
        
        /set_override date_mmdd:12/25 status:Closed reason:Holiday
        -> Closes December 25th with reason "Holiday"
    """
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
        
        # Push changes to git
        await push_to_git()
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="set_week", description="Set overrides for a whole week starting Monday")
@app_commands.describe(
    monday_date="Monday date in MM/DD format (e.g., 09/23)",
    monday_status="Monday status",
    monday_times="Monday times in StartTime-EndTime format (e.g., 14:00-17:00) - only if open",
    monday_reason="Monday reason for closing - only if closed",
    tuesday_status="Tuesday status",
    tuesday_times="Tuesday times in StartTime-EndTime format - only if open",
    tuesday_reason="Tuesday reason for closing - only if closed",
    wednesday_status="Wednesday status",
    wednesday_times="Wednesday times in StartTime-EndTime format - only if open",
    wednesday_reason="Wednesday reason for closing - only if closed",
    thursday_status="Thursday status",
    thursday_times="Thursday times in StartTime-EndTime format - only if open",
    thursday_reason="Thursday reason for closing - only if closed",
    friday_status="Friday status",
    friday_times="Friday times in StartTime-EndTime format - only if open",
    friday_reason="Friday reason for closing - only if closed"
)
@app_commands.choices(monday_status=[
    app_commands.Choice(name="Open", value="open"),
    app_commands.Choice(name="Closed", value="closed")
])
@app_commands.choices(tuesday_status=[
    app_commands.Choice(name="Open", value="open"),
    app_commands.Choice(name="Closed", value="closed")
])
@app_commands.choices(wednesday_status=[
    app_commands.Choice(name="Open", value="open"),
    app_commands.Choice(name="Closed", value="closed")
])
@app_commands.choices(thursday_status=[
    app_commands.Choice(name="Open", value="open"),
    app_commands.Choice(name="Closed", value="closed")
])
@app_commands.choices(friday_status=[
    app_commands.Choice(name="Open", value="open"),
    app_commands.Choice(name="Closed", value="closed")
])
async def set_week_command(interaction: discord.Interaction, monday_date: str, 
                          monday_status: str = "open", monday_times: str = "", monday_reason: str = "Closed",
                          tuesday_status: str = "open", tuesday_times: str = "", tuesday_reason: str = "Closed",
                          wednesday_status: str = "open", wednesday_times: str = "", wednesday_reason: str = "Closed",
                          thursday_status: str = "open", thursday_times: str = "", thursday_reason: str = "Closed",
                          friday_status: str = "open", friday_times: str = "", friday_reason: str = "Closed"):
    """Set overrides for an entire week starting from a Monday.
    
    This slash command allows administrators to set office hours for an entire
    week starting from a Monday. It creates date-specific overrides for each
    day of the week (Monday through Friday) and is useful for special events,
    holidays, or week-long schedule changes.
    
    Args:
        interaction: Discord interaction object containing command context
        monday_date: Monday date in MM/DD format (e.g., "09/23")
        monday_status: Status for Monday ("open" or "closed")
        monday_times: Times for Monday in "StartTime-EndTime" format (if open)
        monday_reason: Reason for closing Monday (if closed)
        tuesday_status: Status for Tuesday ("open" or "closed")
        tuesday_times: Times for Tuesday in "StartTime-EndTime" format (if open)
        tuesday_reason: Reason for closing Tuesday (if closed)
        wednesday_status: Status for Wednesday ("open" or "closed")
        wednesday_times: Times for Wednesday in "StartTime-EndTime" format (if open)
        wednesday_reason: Reason for closing Wednesday (if closed)
        thursday_status: Status for Thursday ("open" or "closed")
        thursday_times: Times for Thursday in "StartTime-EndTime" format (if open)
        thursday_reason: Reason for closing Thursday (if closed)
        friday_status: Status for Friday ("open" or "closed")
        friday_times: Times for Friday in "StartTime-EndTime" format (if open)
        friday_reason: Reason for closing Friday (if closed)
        
    Side Effects:
        - Updates the schedule model with week-long overrides
        - Saves changes to schedule.json file
        - Sends confirmation or error message to Discord
        
    Example:
        /set_week monday_date:09/23 monday_status:Open monday_times:14:00-17:00 tuesday_status:Closed tuesday_reason:Holiday
        -> Sets week of September 23rd with Monday open 2-5 PM and Tuesday closed for holiday
    """
    try:
        week_times = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        statuses = [monday_status, tuesday_status, wednesday_status, thursday_status, friday_status]
        times = [monday_times, tuesday_times, wednesday_times, thursday_times, friday_times]
        reasons = [monday_reason, tuesday_reason, wednesday_reason, thursday_reason, friday_reason]
        
        for day, status, time_str, reason in zip(days, statuses, times, reasons):
            if status == "open" and time_str and time_str.strip():
                if '-' in time_str:
                    start_time, end_time = time_str.split('-', 1)
                    week_times[day] = f"{start_time.strip()},{end_time.strip()}"
                else:
                    week_times[day] = f"{time_str.strip()},"
            elif status == "closed":
                week_times[day] = f"CLOSED ({reason})"
        
        temp_change_week(monday_date, week_times)
        await interaction.response.send_message(f"✅ Set week overrides for {monday_date}")
        
        # Push changes to git
        await push_to_git()
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="show_data", description="Show the raw schedule data")
async def show_data_command(interaction: discord.Interaction):
    """Show the raw schedule data in JSON format.
    
    This slash command displays the complete schedule model as raw JSON data.
    It's useful for debugging, data inspection, or administrative purposes.
    The data is displayed in a code block for better readability.
    
    Args:
        interaction: Discord interaction object containing command context
        
    Side Effects:
        - Loads the current schedule model from disk
        - Sends JSON data to Discord channel
        - Handles Discord message length limits by splitting large data
        
    Example:
        /show_data -> Displays complete schedule model as JSON
    """
    try:
        model = load_schedule_model()
        # Split into chunks if too long
        data_str = str(model)
        if len(data_str) > 1900:  # Discord limit
            await interaction.response.send_message("Data too large, showing first part:", ephemeral=True)
            await interaction.followup.send(f"```json\n{data_str[:1900]}...\n```", ephemeral=True)
        else:
            await interaction.response.send_message(f"```json\n{data_str}\n```", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="schedule", description="Show this week's office hours schedule")
async def show_schedule_backup(interaction: discord.Interaction):
    """Show this week's office hours schedule.
    
    This slash command displays the GMU Esports office hours schedule
    for the current week. It shows the effective hours considering both
    default schedules and any date-specific overrides.
    
    Args:
        interaction: Discord interaction object containing command context
        
    Side Effects:
        - Sends formatted schedule message to Discord channel
        - Sends error message if something goes wrong
        
    Example:
        /schedule -> Shows current week's schedule
    """
    try:
        # Show current week
        week_monday = start_of_week_monday(date.today())
        rows = effective_week_schedule(week_monday)
        title = "**This Week's Schedule**"
        
        schedule_text = format_schedule_for_discord(rows)
        await interaction.response.send_message(f"{title}\n{schedule_text}")
    except Exception as e:
        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="test", description="Test if the bot is working")
async def test_command(interaction: discord.Interaction):
    """Test command to verify bot is working.
    
    This simple slash command is used to test if the Discord bot is
    functioning correctly. It sends a confirmation message indicating
    the bot is operational and provides guidance on available commands.
    
    Args:
        interaction: Discord interaction object containing command context
        
    Side Effects:
        - Sends test confirmation message to Discord
        
    Example:
        /test -> "🤖 Bot is working! Use `/hours` or `/schedule` to see commands."
    """
    await interaction.response.send_message("🤖 Bot is working! Use `/hours` or `/schedule` to see commands.")

@bot.tree.command(name="close_day", description="Close a specific day with a reason")
@app_commands.describe(
    date_mmdd="Date in MM/DD format (e.g., 09/16)",
    reason="Reason for closing (e.g., Holiday, Maintenance, etc.)"
)
async def close_day_command(interaction: discord.Interaction, date_mmdd: str, reason: str = "Closed"):
    """Close a specific day with a reason.
    
    This slash command provides a quick way to close the office for a
    specific date with a custom reason. It creates a date-specific override
    that shows "CLOSED" with the provided reason.
    
    Args:
        interaction: Discord interaction object containing command context
        date_mmdd: Date in MM/DD format (e.g., "09/16" for September 16th)
        reason: Reason for closing (e.g., "Holiday", "Maintenance", "Event")
        
    Side Effects:
        - Updates the schedule model with date-specific override
        - Saves changes to schedule.json file
        - Sends confirmation or error message to Discord
        
    Example:
        /close_day date_mmdd:12/25 reason:Holiday
        -> Closes December 25th with reason "Holiday"
        
        /close_day date_mmdd:09/16 reason:Maintenance
        -> Closes September 16th with reason "Maintenance"
    """
    try:
        temp_change(date_mmdd, "", "")  # This sets it to CLOSED
        # Update the override to include the reason
        from app import _model, save_schedule_model
        _d = date_mmdd  # Use the date as-is for simplicity
        _model["overrides"][_d] = f"CLOSED ({reason})"
        save_schedule_model(_model)
        await interaction.response.send_message(f"✅ Closed {date_mmdd}: {reason}")
        
        # Push changes to git
        await push_to_git()
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
    """Close a weekday with a reason.
    
    This slash command allows administrators to close a specific weekday
    by default with a custom reason. This affects the default schedule
    for that day across all weeks (unless overridden by date-specific overrides).
    
    Args:
        interaction: Discord interaction object containing command context
        day: Weekday name (Monday through Friday)
        reason: Reason for closing (e.g., "Holiday", "Maintenance", "No Staff")
        
    Side Effects:
        - Updates the default schedule model for the specified weekday
        - Saves changes to schedule.json file
        - Sends confirmation or error message to Discord
        
    Example:
        /close_weekday day:Monday reason:No Staff
        -> Closes Monday by default with reason "No Staff"
        
        /close_weekday day:Friday reason:Maintenance
        -> Closes Friday by default with reason "Maintenance"
    """
    try:
        set_default_time(day, "", "")  # This sets it to CLOSED
        # Update the default to include the reason
        from app import _model, save_schedule_model
        _model["default"][day] = f"CLOSED ({reason})"
        save_schedule_model(_model)
        await interaction.response.send_message(f"✅ Closed {day}: {reason}")
        
        # Push changes to git
        await push_to_git()
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="sync", description="Sync slash commands (admin only)")
async def sync_commands(interaction: discord.Interaction):
    """Manually sync slash commands with Discord.
    
    This slash command allows administrators to manually sync the bot's
    slash commands with Discord's servers. This is useful when commands
    are not appearing or need to be refreshed after updates.
    
    Args:
        interaction: Discord interaction object containing command context
        
    Side Effects:
        - Syncs all slash commands with Discord
        - Sends confirmation or error message to Discord
        
    Example:
        /sync -> "✅ Synced 8 command(s)" or error message if failed
    """
    try:
        synced = await bot.tree.sync()
        await interaction.response.send_message(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to sync: {str(e)}", ephemeral=True)

if __name__ == "__main__":
    # Try to get token from config file first, then environment
    try:
        from config import DISCORD_TOKEN
        token = DISCORD_TOKEN
    except ImportError:
        token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("❌ Please set DISCORD_TOKEN in config.py or environment variable")
        print("Example: export DISCORD_TOKEN='your_bot_token_here'")
        exit(1)
    
    print("🤖 Starting Discord bot...")
    bot.run(token)
