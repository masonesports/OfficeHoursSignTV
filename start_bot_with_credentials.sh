#!/bin/bash
# Startup script for Discord bot with GitHub credentials

echo "🤖 Starting Discord Bot with GitHub credentials..."

# Check if environment variables are set
if [ -z "$GITHUB_USERNAME" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GitHub credentials not found!"
    echo "Please set these environment variables:"
    echo "export GITHUB_USERNAME='your-username'"
    echo "export GITHUB_TOKEN='your-token'"
    echo ""
    echo "Or run: ./setup_credentials.sh"
    exit 1
fi

echo "✅ GitHub credentials found"
echo "Username: $GITHUB_USERNAME"
echo "Token: ${GITHUB_TOKEN:0:10}..."

# Configure git credentials
git config credential.helper store
echo "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com" > ~/.git-credentials

echo "🔐 Git credentials configured"

# Start the Discord bot
echo "🚀 Starting Discord bot..."
python3 discord_bot.py
