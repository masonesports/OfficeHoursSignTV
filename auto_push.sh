#!/bin/bash
# Auto-push script to run whenever code is executed

echo "🔄 Auto-pushing code changes..."

# Add all changes first
git add .

# Check if we have changes to commit
if ! git diff --cached --quiet; then
    git commit -m "Auto-commit: "
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
