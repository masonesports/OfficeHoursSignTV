#!/bin/bash
# Auto-push script to run whenever code is executed

echo "🔄 Auto-pushing code changes..."

# Check if we have changes to commit
if git diff --quiet && git diff --cached --quiet; then
    echo "ℹ️ No changes to commit"
    exit 0
fi

# Add all changes
git add .

# Commit with timestamp
git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S') - Schedule update"

# Configure git credentials if environment variables are set
if [ ! -z "$GITHUB_USERNAME" ] && [ ! -z "$GITHUB_TOKEN" ]; then
    echo "🔐 Using environment variables for authentication"
    git config credential.helper store
    echo "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com" > ~/.git-credentials
fi

# Push to remote with error handling
if git push; then
    echo "✅ Code pushed successfully!"
else
    echo "❌ Push failed. This might be due to:"
    echo "   - Missing GitHub credentials"
    echo "   - Network connectivity issues"
    echo "   - Repository permissions"
    echo ""
    echo "💡 Run ./setup_credentials.sh for credential setup instructions"
    exit 1
fi
