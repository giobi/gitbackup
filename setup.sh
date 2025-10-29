#!/bin/bash

# GitBackup - Setup Script
# Popola env.json con le configurazioni necessarie

set -e

echo "🔧 GitBackup Setup"
echo "=================="
echo ""

# Check if env.json already exists
if [ -f "env.json" ]; then
    echo "⚠️  env.json già esistente!"
    read -p "Vuoi sovrascriverlo? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup annullato"
        exit 1
    fi
fi

# Prompt for GitHub token
echo "📝 Configurazione GitHub"
echo ""
echo "Crea un token su: https://github.com/settings/tokens"
echo "Scopes richiesti: repo (full control)"
echo ""
read -p "GitHub Token: " github_token

if [ -z "$github_token" ]; then
    echo "❌ GitHub token obbligatorio!"
    exit 1
fi

read -p "GitHub Username [giobi]: " github_username
github_username=${github_username:-giobi}

# Prompt for backup directory
read -p "Backup Directory [./backup]: " backup_dir
backup_dir=${backup_dir:-./backup}

# Prompt for Telegram (opzionale)
echo ""
echo "📱 Configurazione Telegram (OPZIONALE - premi Enter per saltare)"
read -p "Telegram Bot Token: " telegram_bot_token
read -p "Telegram Chat ID: " telegram_chat_id

# Log file path
read -p "Log File [./logs/gitbackup.log]: " log_file
log_file=${log_file:-./logs/gitbackup.log}

# Create directories
mkdir -p "$backup_dir"
mkdir -p "$(dirname "$log_file")"

# Generate env.json
cat > env.json <<EOF
{
  "github_token": "$github_token",
  "github_username": "$github_username",
  "backup_dir": "$backup_dir",
  "telegram_bot_token": "$telegram_bot_token",
  "telegram_chat_id": "$telegram_chat_id",
  "log_file": "$log_file"
}
EOF

chmod 600 env.json

echo ""
echo "✅ env.json creato con successo!"
echo ""
echo "🚀 Prossimi passi:"
echo "   1. ./backup.sh          - Esegui backup manuale"
echo "   2. crontab -e           - Aggiungi backup automatico"
echo "      0 2 * * * cd /home/web/gitbackup && ./backup.sh"
echo ""
