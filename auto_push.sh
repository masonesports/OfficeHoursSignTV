#!/bin/bash
# Auto-push script to run whenever code is executed

echo "🔄 Auto-pushing code changes..."

# Add all changes
git add .

# Commit with timestamp
git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S') - Code execution update"

# Push to remote
git push

echo "✅ Code pushed successfully!"
