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

# Ask for crontab setup
echo "📅 Configurazione backup automatico"
read -p "Vuoi configurare backup automatico via cron? (y/N): " -n 1 -r setup_cron
echo ""

if [[ $setup_cron =~ ^[Yy]$ ]]; then
    echo ""
    echo "Scegli frequenza backup:"
    echo "  1) Ogni giorno (2:00 AM)"
    echo "  2) Ogni settimana (domenica 2:00 AM)"
    echo "  3) Personalizzato"
    read -p "Scelta [1]: " cron_choice
    cron_choice=${cron_choice:-1}

    case $cron_choice in
        1)
            cron_schedule="0 2 * * *"
            cron_desc="giornaliero alle 2:00 AM"
            ;;
        2)
            cron_schedule="0 2 * * 0"
            cron_desc="settimanale (domenica 2:00 AM)"
            ;;
        3)
            echo ""
            echo "Inserisci cron schedule (es: 0 3 * * * per ogni giorno alle 3:00):"
            read -p "Schedule: " cron_schedule
            cron_desc="personalizzato ($cron_schedule)"
            ;;
        *)
            echo "❌ Scelta non valida, skip crontab"
            setup_cron="n"
            ;;
    esac

    if [[ $setup_cron =~ ^[Yy]$ ]]; then
        # Add to crontab
        script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        cron_line="$cron_schedule cd $script_path && ./backup.sh >> ./logs/cron.log 2>&1"

        # Check if already exists
        (crontab -l 2>/dev/null | grep -F "$script_path/backup.sh") && {
            echo "⚠️  Crontab già configurato per questo script"
        } || {
            (crontab -l 2>/dev/null; echo "$cron_line") | crontab -
            echo "✅ Crontab configurato: backup $cron_desc"
        }
    fi
fi

echo ""
echo "🚀 Vuoi eseguire il primo backup adesso?"
read -p "Esegui backup? (Y/n): " -n 1 -r run_backup
echo ""

if [[ ! $run_backup =~ ^[Nn]$ ]]; then
    echo ""
    echo "🔄 Avvio primo backup..."
    echo ""
    ./backup.sh
    exit_code=$?
    echo ""
    if [ $exit_code -eq 0 ]; then
        echo "✅ Primo backup completato con successo!"
    else
        echo "❌ Backup fallito (exit code: $exit_code)"
        echo "   Controlla i log per dettagli"
    fi
else
    echo ""
    echo "📝 Setup completato!"
    echo ""
    echo "Prossimi passi:"
    echo "   ./backup.sh    - Esegui backup manuale quando vuoi"
fi

echo ""
