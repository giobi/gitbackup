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

# Load config using Python (no jq dependency)
read_json() {
    python3 -c "import json; print(json.load(open('env.json')).get('$1', ''))"
}

GITHUB_TOKEN=$(read_json 'github_token')
GITHUB_USERNAME=$(read_json 'github_username')
BACKUP_DIR=$(read_json 'backup_dir')
TELEGRAM_BOT_TOKEN=$(read_json 'telegram_bot_token')
TELEGRAM_CHAT_ID=$(read_json 'telegram_chat_id')
LOG_FILE=$(read_json 'log_file')

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
    | python3 -c "import json, sys; [print(r['clone_url']) for r in json.load(sys.stdin)]")

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
echo "$REPOS" | while IFS= read -r clone_url; do
    # Skip empty lines
    [ -z "$clone_url" ] && continue

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
            SUCCESS=$((SUCCESS + 1))
            UPDATED=$((UPDATED + 1))
        else
            log "❌ Failed to update: $repo_name"
            FAILED=$((FAILED + 1))
        fi
    else
        # Clone new repo
        log "📥 Cloning: $repo_name"
        if git clone --quiet "$auth_url" "$repo_path" 2>/dev/null; then
            log "✅ Cloned: $repo_name"
            SUCCESS=$((SUCCESS + 1))
            CLONED=$((CLONED + 1))
        else
            log "❌ Failed to clone: $repo_name"
            FAILED=$((FAILED + 1))
        fi
    fi
done

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
