#!/bin/bash
# Setup script for GitHub credentials on Proxmox server

echo "🔐 Setting up GitHub credentials for auto-push..."

# Method 1: SSH Key Setup (Recommended)
echo "📋 SSH Key Setup Instructions:"
echo "1. Generate SSH key: ssh-keygen -t ed25519 -C 'your-email@example.com'"
echo "2. Add public key to GitHub: cat ~/.ssh/id_ed25519.pub"
echo "3. Change remote to SSH: git remote set-url origin git@github.com:masonesports/OfficeHoursSignTV.git"
echo ""

# Method 2: Personal Access Token Setup
echo "📋 Personal Access Token Setup Instructions:"
echo "1. Go to GitHub Settings > Developer settings > Personal access tokens"
echo "2. Generate new token with 'repo' permissions"
echo "3. Run these commands:"
echo "   git config --global credential.helper store"
echo "   git config --global user.name 'Your Name'"
echo "   git config --global user.email 'your-email@example.com'"
echo "   git push  # Enter username and token when prompted"
echo ""

# Method 3: Environment Variables (for automation)
echo "📋 Environment Variables Setup:"
echo "Add these to your Proxmox environment:"
echo "export GITHUB_USERNAME='your-username'"
echo "export GITHUB_TOKEN='your-personal-access-token'"
echo ""

echo "✅ Choose one method above and follow the instructions!"
