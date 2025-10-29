#!/bin/bash

# GitBackup - Main Backup Script
# Clona o aggiorna tutte le repo GitHub dell'utente

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load config
if [ ! -f "env.json" ]; then
    echo "❌ env.json non trovato. Esegui ./setup.sh prima"
    exit 1
fi

GITHUB_TOKEN=$(jq -r '.github_token' env.json)
GITHUB_USERNAME=$(jq -r '.github_username' env.json)
BACKUP_DIR=$(jq -r '.backup_dir' env.json)
TELEGRAM_BOT_TOKEN=$(jq -r '.telegram_bot_token // ""' env.json)
TELEGRAM_CHAT_ID=$(jq -r '.telegram_chat_id // ""' env.json)
LOG_FILE=$(jq -r '.log_file' env.json)

# Create directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Telegram notification function
telegram_notify() {
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            -d text="$1" \
            -d parse_mode="Markdown" > /dev/null
    fi
}

# Start backup
log "🚀 GitBackup started"
telegram_notify "🚀 *GitBackup* started"

# Fetch all repositories
log "📡 Fetching repositories for user: $GITHUB_USERNAME"
REPOS=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    "https://api.github.com/user/repos?per_page=100&affiliation=owner" \
    | jq -r '.[].clone_url')

if [ -z "$REPOS" ]; then
    log "❌ No repositories found or API error"
    telegram_notify "❌ *GitBackup failed*: No repositories found"
    exit 1
fi

TOTAL_REPOS=$(echo "$REPOS" | wc -l)
log "📦 Found $TOTAL_REPOS repositories"

SUCCESS=0
FAILED=0
UPDATED=0
CLONED=0

# Process each repo
while IFS= read -r clone_url; do
    # Extract repo name from URL
    repo_name=$(basename "$clone_url" .git)
    repo_path="$BACKUP_DIR/$repo_name"

    # Add token to URL for authentication
    auth_url=$(echo "$clone_url" | sed "s|https://|https://$GITHUB_TOKEN@|")

    if [ -d "$repo_path" ]; then
        # Pull updates
        log "🔄 Updating: $repo_name"
        if (cd "$repo_path" && git pull --quiet); then
            log "✅ Updated: $repo_name"
            ((SUCCESS++))
            ((UPDATED++))
        else
            log "❌ Failed to update: $repo_name"
            ((FAILED++))
        fi
    else
        # Clone new repo
        log "📥 Cloning: $repo_name"
        if git clone --quiet "$auth_url" "$repo_path" 2>/dev/null; then
            log "✅ Cloned: $repo_name"
            ((SUCCESS++))
            ((CLONED++))
        else
            log "❌ Failed to clone: $repo_name"
            ((FAILED++))
        fi
    fi
done <<< "$REPOS"

# Summary
log "📊 Backup completed: $SUCCESS success, $FAILED failed (Cloned: $CLONED, Updated: $UPDATED)"
telegram_notify "✅ *GitBackup completed*

📊 Summary:
• Total repos: $TOTAL_REPOS
• Cloned: $CLONED
• Updated: $UPDATED
• Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    exit 1
fi

exit 0
