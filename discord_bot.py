import asyncio
import json
import os
import threading
import time
from datetime import date, timedelta, datetime, time as dt_time
from typing import Optional

import discord
from discord.ext import commands, tasks
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

# Configuration file path
CONFIG_FILE = "bot_config.json"

def load_bot_config():
    """Load bot configuration from JSON file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        else:
            # Return default config if file doesn't exist
            return {
                "update_message": "📢 **Office Hours Updated**\n{user} {action} office hours: {details}",
                "update_channel_id": None,
                "update_role_id": None
            }
    except Exception as e:
        return {
            "update_message": "📢 **Office Hours Updated**\n{user} {action} office hours: {details}",
            "update_channel_id": None,
            "update_role_id": None
        }

def save_bot_config():
    """Save bot configuration to JSON file."""
    try:
        config = {
            "update_message": bot.update_message,
            "update_channel_id": bot.update_channel_id,
            "update_role_id": bot.update_role_id
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        pass  # Silently fail on config save errors

# Load configuration on startup
config = load_bot_config()
bot.update_message = config["update_message"]
bot.update_channel_id = config["update_channel_id"]
bot.update_role_id = config["update_role_id"]

# Track if we've already updated for this week
bot.week_updated = False
bot.last_update_week = None

# Background task to check for Monday and update website
@tasks.loop(minutes=5)  # Check every 5 minutes
async def check_week_update():
    """Check if it's Monday and update website to new week."""
    try:
        now = datetime.now()
        current_week = start_of_week_monday(now.date())
        
        # Check if it's Monday
        is_monday = now.weekday() == 0  # Monday = 0
        
        # Only update once per week
        if is_monday and (not bot.week_updated or bot.last_update_week != current_week):
            # Update the website by triggering a refresh
            await update_website_to_new_week()
            
            # Mark as updated for this week
            bot.week_updated = True
            bot.last_update_week = current_week
            
    except Exception as e:
        pass  # Silently handle week update errors

# Sync commands tree
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    # Start the background task
    if not check_week_update.is_running():
        check_week_update.start()

# Helper function to format schedule for Discord
def format_schedule_for_discord(rows):
    """Format schedule rows for Discord display."""
    lines = ["**GMU Esports Office Hours Schedule**", "```"]
    for day_name, date_str, time_str in rows:
        status = time_str if time_str else "—"
        lines.append(f"{day_name} ({date_str}): {status}")
    lines.append("```")
    return "\n".join(lines)

# Helper function to send update notifications
async def send_update_notification(user: str, action: str, details: str):
    """Send an update notification to the configured channel."""
    if not bot.update_channel_id:
        return  # No channel configured
    
    try:
        channel = bot.get_channel(bot.update_channel_id)
        if not channel:
            return
        
        # Format the simple change message
        change_message = bot.update_message.format(
            user=user,
            action=action,
            details=details
        )
        
        # Get current week's schedule (or next week if Friday after 5PM)
        from datetime import date, datetime, time, timedelta
        now = datetime.now()
        is_friday_after_5pm = now.weekday() == 4 and now.time() >= time(17, 0)  # Friday = 4, 5PM = 17:00
        
        if is_friday_after_5pm:
            week_monday = start_of_week_monday(date.today()) + timedelta(days=7)
        else:
            week_monday = start_of_week_monday(date.today())
        
        rows = effective_week_schedule(week_monday)
        schedule_text = format_schedule_for_discord(rows)
        
        # Combine change message with schedule
        full_message = f"{change_message}\n\n{schedule_text}"
        
        # Add role ping if configured
        if bot.update_role_id:
            role_mention = f"<@&{bot.update_role_id}>"
            full_message = f"{role_mention} {full_message}"
        
        await channel.send(full_message)
    except Exception as e:
        pass  # Silently handle notification errors

# Helper function to update website to new week
async def update_website_to_new_week():
    """Update the website to show new week's schedule."""
    try:
        # Force reload the schedule model to ensure it's up to date
        from app import load_schedule_model
        load_schedule_model()
        
    except Exception as e:
        pass  # Silently handle website update errors

# Slash Commands with autocomplete
@bot.tree.command(name="hours", description="Show the current week's office hours schedule")
async def show_schedule(interaction: discord.Interaction):
    """Show the current week's schedule."""
    try:
        from datetime import datetime, time
        
        # Check if it's Friday at 5PM or later
        now = datetime.now()
        is_friday_after_5pm = now.weekday() == 4 and now.time() >= time(17, 0)  # Friday = 4, 5PM = 17:00
        
        if is_friday_after_5pm:
            # Show next week's schedule
            week_monday = start_of_week_monday(date.today()) + timedelta(days=7)
            rows = effective_week_schedule(week_monday)
            title = "**Next Week's Schedule**"
        else:
            # Show current week's schedule
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
    start_time="Start time in 24-hour format (e.g., 14:00) - optional, defaults to 9:00 AM",
    end_time="End time in 24-hour format (e.g., 17:00) - optional, defaults to 5:00 PM"
)
@app_commands.choices(day=[
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday")
])
async def set_default_command(interaction: discord.Interaction, day: str, start_time: str = "9:00AM", end_time: str = "5:00PM"):
    """Set default time for a weekday."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        from app import _format_time_range, set_default_time
        
        # Update default schedule for the weekday
        set_default_time(day, start_time, end_time)
        formatted_time = _format_time_range(start_time, end_time)
        await interaction.response.send_message(f"✅ Set default for {day}: {formatted_time}")
        
        # Send notification
        await send_update_notification(
            user=interaction.user.display_name,
            action="updated default hours for",
            details=f"{day}: {formatted_time}"
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="change_hours", description="Change hours for a weekday")
@app_commands.describe(
    day="Day of the week",
    start_time="Start time in 24-hour format (e.g., 14:00) - optional, defaults to 9:00 AM",
    end_time="End time in 24-hour format (e.g., 17:00) - optional, defaults to 5:00 PM",
    reason="Optional reason for the change"
)
@app_commands.choices(day=[
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday")
])
async def change_hours_command(interaction: discord.Interaction, day: str, start_time: str = "9:00AM", end_time: str = "5:00PM", reason: str = ""):
    """Change hours for a weekday."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        from app import _format_time_range, _model, save_schedule_model, set_default_time
        
        # Update default schedule for the weekday
        formatted_time = _format_time_range(start_time, end_time)
        status_text = formatted_time
        
        if reason:
            status_text = f"{formatted_time} ({reason})"
            _model["default"][day] = status_text
        else:
            set_default_time(day, start_time, end_time)
        
        await interaction.response.send_message(f"✅ Updated hours for {day}: {status_text}")
        
        # Send notification
        await send_update_notification(
            user=interaction.user.display_name,
            action="updated hours for",
            details=f"{day}: {status_text}"
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)




@bot.tree.command(name="help", description="Show help information for all commands")
async def help_command(interaction: discord.Interaction):
    """Show help information for all commands."""
    help_text = """
# 🤖 GMU Esports Office Hours Bot - Help

## 📋 **Viewing Commands**
- `/hours` - Show the current week's office hours schedule

## ⚙️ **Administrator Commands**

### **Setting Hours**
- `/set_default` - Set default hours for a weekday
  - `day`: Monday, Tuesday, Wednesday, Thursday, or Friday
  - `start_time`: Start time (optional, defaults to 9:00 AM)
  - `end_time`: End time (optional, defaults to 5:00 PM)

### **Changing Hours**
- `/change_hours` - Change hours for a weekday
  - `day`: Monday, Tuesday, Wednesday, Thursday, or Friday
  - `start_time`: Start time (optional, defaults to 9:00 AM)
  - `end_time`: End time (optional, defaults to 5:00 PM)
  - `reason`: Optional reason for the change

### **Opening Days**
- `/open_day` - Open a weekday with custom hours
  - `day`: Monday, Tuesday, Wednesday, Thursday, or Friday
  - `start_time`: Start time (optional, defaults to 9:00 AM)
  - `end_time`: End time (optional, defaults to 5:00 PM)
  - `reason`: Optional reason for opening

### **Closing Days**
- `/close_day` - Close a weekday with a reason
  - `day`: Monday, Tuesday, Wednesday, Thursday, or Friday
  - `reason`: Reason for closing

### **Notification Settings**
- `/change_message` - Set custom message template for updates
- `/set_channel` - Set channel for update notifications
- `/set_role` - Set role to ping for updates

## 🕐 **Time Format Examples**
- **12-hour**: `9:00AM`, `2:30PM`, `12:00PM`, `12:00AM`
- **24-hour**: `09:00`, `14:30`, `12:00`, `00:00`
- **Without colon**: `9AM`, `2PM`, `12PM`

## 📅 **Date Format Examples**
- **With zeros**: `09/16`, `01/01`, `12/25`
- **Without zeros**: `9/16`, `1/1`, `12/25`

## 🔧 **Test Command**
- `/test` - Test if the bot is working (admin only)

---
*All time and date formats are flexible and will be automatically converted to the proper format.*
"""
    
    await interaction.response.send_message(help_text, ephemeral=True)

@bot.tree.command(name="test", description="Test if the bot is working")
async def test_command(interaction: discord.Interaction):
    """Test command to verify bot is working."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    await interaction.response.send_message("🤖 Bot is working! Use `/hours` to see the current schedule.")

@bot.tree.command(name="week_status", description="Check the current week update status")
async def week_status_command(interaction: discord.Interaction):
    """Check the current week update status."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        now = datetime.now()
        current_week = start_of_week_monday(now.date())
        is_friday_after_8pm = now.weekday() == 4 and now.time() >= dt_time(20, 0)
        
        status_message = f"""**Week Update Status**
        
**Current Time:** {now.strftime('%A, %Y-%m-%d %H:%M')}
**Current Week:** {current_week}
**Is Friday 8PM+:** {'Yes' if is_friday_after_8pm else 'No'}
**Week Updated:** {'Yes' if bot.week_updated else 'No'}
**Last Update Week:** {bot.last_update_week if bot.last_update_week else 'Never'}
**Background Task:** {'Running' if check_week_update.is_running() else 'Stopped'}

**Next Check:** Every 5 minutes
**Update Time:** Friday 8:00 PM"""
        
        await interaction.response.send_message(status_message, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="reset_week", description="Reset the week update flag (admin only)")
async def reset_week_command(interaction: discord.Interaction):
    """Reset the week update flag."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        bot.week_updated = False
        bot.last_update_week = None
        await interaction.response.send_message("✅ Week update flag reset. The bot will check for Friday 8PM again.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="close_day", description="Close a weekday with a reason")
@app_commands.describe(
    day="Day of the week",
    reason="Reason for closing (e.g., Holiday, Maintenance, etc.)"
)
@app_commands.choices(day=[
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday")
])
async def close_day_command(interaction: discord.Interaction, day: str, reason: str = "Closed"):
    """Close a weekday with a reason."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        from app import _model, save_schedule_model, set_default_time
        
        # Close default schedule for the weekday
        set_default_time(day, "", "")  # This sets it to CLOSED
        _model["default"][day] = f"CLOSED ({reason})"
        save_schedule_model(_model)
        
        await interaction.response.send_message(f"✅ Closed {day}: {reason}")
        
        # Send notification
        await send_update_notification(
            user=interaction.user.display_name,
            action="closed",
            details=f"{day}: {reason}"
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="open_day", description="Open a weekday with custom hours")
@app_commands.describe(
    day="Day of the week",
    start_time="Start time in 24-hour format (e.g., 14:00) - optional, defaults to 9:00 AM",
    end_time="End time in 24-hour format (e.g., 17:00) - optional, defaults to 5:00 PM",
    reason="Optional reason for opening (e.g., Special Event, Extended Hours, etc.)"
)
@app_commands.choices(day=[
    app_commands.Choice(name="Monday", value="Monday"),
    app_commands.Choice(name="Tuesday", value="Tuesday"),
    app_commands.Choice(name="Wednesday", value="Wednesday"),
    app_commands.Choice(name="Thursday", value="Thursday"),
    app_commands.Choice(name="Friday", value="Friday")
])
async def open_day_command(interaction: discord.Interaction, day: str, start_time: str = "9:00AM", end_time: str = "5:00PM", reason: str = ""):
    """Open a weekday with custom hours."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        from app import _format_time_range, _model, save_schedule_model, set_default_time
        
        # Update default schedule for the weekday
        formatted_time = _format_time_range(start_time, end_time)
        status_text = formatted_time
        
        if reason:
            status_text = f"{formatted_time} ({reason})"
            _model["default"][day] = status_text
        else:
            set_default_time(day, start_time, end_time)
        
        await interaction.response.send_message(f"✅ Opened {day}: {status_text}")
        
        # Send notification
        await send_update_notification(
            user=interaction.user.display_name,
            action="opened",
            details=f"{day}: {status_text}"
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name="change_message", description="Set the message template for office hours updates")
@app_commands.describe(
    message="Custom message template for office hours updates (use {user}, {action}, {details} as placeholders). The current week's schedule will be automatically included."
)
async def change_message_command(interaction: discord.Interaction, message: str):
    """Set the message template for office hours updates."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        # Store the message in the bot's data
        bot.update_message = message
        save_bot_config()  # Save to JSON file
        await interaction.response.send_message(f"✅ Update message set to: {message}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="set_channel", description="Set the channel for office hours update notifications")
@app_commands.describe(
    channel="The channel to post office hours updates to"
)
async def set_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the channel for office hours update notifications."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        # Store the channel ID in the bot's data
        bot.update_channel_id = channel.id
        save_bot_config()  # Save to JSON file
        await interaction.response.send_message(f"✅ Update channel set to: {channel.mention}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="set_role", description="Set the role to ping for office hours updates")
@app_commands.describe(
    role="The role to ping when office hours are updated"
)
async def set_role_command(interaction: discord.Interaction, role: discord.Role):
    """Set the role to ping for office hours updates."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        # Store the role ID in the bot's data
        bot.update_role_id = role.id
        save_bot_config()  # Save to JSON file
        await interaction.response.send_message(f"✅ Update role set to: {role.mention}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


if __name__ == "__main__":
    # Try to get token from bot_config file first, then environment
    token = None
    try:
        from bot_config import DISCORD_TOKEN
        token = DISCORD_TOKEN
    except ImportError:
        token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("❌ Please set DISCORD_TOKEN in secrets.py, config.py, or environment variable")
        print("Create secrets.py with: DISCORD_TOKEN = 'your_token_here'")
        exit(1)
    
    bot.run(token)
