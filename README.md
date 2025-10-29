# GitBackup

Sistema di backup automatico per tutte le repository GitHub di un utente.

## Features

- 🔄 Clone o pull automatico di tutte le tue repo GitHub
- 📱 Notifiche Telegram (opzionali)
- 📝 Logging completo su file
- ⚙️ Setup interattivo
- 🔐 Token sicuro in env.json (non versionato)
- 💾 **Storage tracking**: dimensione totale e repo più grande
- ⚠️ **Large repos warning**: alert se repo > 500 MB
- 🕐 **Stale repos detection**: repo non aggiornate da 6+ mesi

## Quick Start

```bash
cd /home/web/gitbackup

# 1. Setup (chiede GitHub token + opzionale Telegram)
./setup.sh

# 2. Esegui backup manuale
./backup.sh

# 3. Aggiungi a crontab per backup automatico
crontab -e
# Aggiungi:
# 0 2 * * * cd /home/web/gitbackup && ./backup.sh
```

## Setup Interattivo

Lo script `setup.sh` ti chiederà:

1. **GitHub Token** (OBBLIGATORIO)
   - Crea su https://github.com/settings/tokens
   - Scopes richiesti: `repo` (full control)

2. **GitHub Username** (default: `giobi`)

3. **Backup Directory** (default: `./backup`)

4. **Telegram Bot Token** (OPZIONALE - premi Enter per saltare)

5. **Telegram Chat ID** (OPZIONALE)

6. **Log File** (default: `./logs/gitbackup.log`)

Il setup genera `env.json` con permessi 600 (solo owner read/write).

## Integrations

### Telegram (Opzionale)

Se configuri Telegram, riceverai:
- ✅ Notifica inizio backup
- 📊 Summary finale (repos clonate/aggiornate/failed)
- ❌ Alert se ci sono errori

### Logging

Tutti i backup sono loggati in `logs/gitbackup.log`:
```
[2025-10-29 21:00:00] 🚀 GitBackup started
[2025-10-29 21:00:01] 📡 Fetching repositories for user: giobi
[2025-10-29 21:00:02] 📦 Found 25 repositories
[2025-10-29 21:00:03] 🔄 Updating: circus
[2025-10-29 21:00:04] ✅ Updated: circus
...
[2025-10-29 21:05:00] 📊 Backup completed: 25 success, 0 failed
```

## Idee di Integrazione Avanzate

### 🎯 Già Implementate
- ✅ Telegram notifications
- ✅ File logging
- ✅ Clone + pull automatico
- ✅ Setup interattivo

### 🔮 Idee Future

**1. Selective Backup**
- Blacklist/whitelist di repo specifiche via config
- Backup solo repo aggiornate negli ultimi N giorni
- Esclusione automatica di fork
- Filtro per size (esclude repo > X GB)

**2. Advanced Reporting**
- Report settimanale via email con statistiche
- Diff summary delle modifiche da ultimo backup
- Alert se una repo non viene aggiornata da X giorni
- Healthcheck.io ping per monitoraggio uptime

**3. Multi-Platform Support**
- GitLab API integration
- Bitbucket support
- Self-hosted Gitea/Gogs

**4. Compression & Archiving**
- Tar.gz automatico delle repo dopo backup
- Rotation automatica (mantieni ultimi N backup)
- Upload su S3/Backblaze per offsite backup
- Incremental backup con rsync

**5. Web Dashboard**
- Interfaccia web per vedere stato backup
- Trigger manuale backup da UI
- Log viewer integrato
- Timeline visuale backup history

**6. Monitoring Integration**
- New Relic custom events
- Cronitor integration
- Prometheus metrics export
- Slack/Discord webhooks

**7. Smart Backup**
- Deduplicazione con Git bundle
- Backup metadata (issues, PRs, wiki, releases)
- Parallel cloning (speed up con GNU parallel)
- Resume interrupted backups

**8. Security Enhancements**
- Encrypted backup con GPG
- Verify Git signatures
- Audit log modifiche ai backup
- 2FA-aware GitHub token refresh

**9. Database Integration**
- SQLite database per tracking backup history
- Query su quando una repo è stata backuppata l'ultima volta
- Detect repos eliminate da GitHub

**10. Pre/Post Hooks**
- Custom scripts before/after backup
- Webhook notifications (generic HTTP POST)
- Integration con altri sistemi (Ansible, etc)

## Structure

```
gitbackup/
├── backup.sh           # Main backup script
├── setup.sh            # Setup interattivo
├── env.json            # Config (gitignored, permissions 600)
├── env.json.example    # Template
├── .gitignore
├── README.md
├── backup/             # Repo backupped (gitignored)
│   ├── repo1/
│   ├── repo2/
│   └── ...
└── logs/               # Log files (gitignored)
    └── gitbackup.log
```

## Requirements

- `bash`
- `git`
- `python3` (JSON parsing)
- `curl` (per GitHub API + Telegram notifications)

Già installato su tutti i sistemi moderni! Zero dipendenze extra.

## Cron Setup

Backup automatico ogni notte alle 2:00 AM:

```bash
crontab -e
```

Aggiungi:
```cron
0 2 * * * cd /home/web/gitbackup && ./backup.sh >> ./logs/cron.log 2>&1
```

## Security

- ✅ `env.json` ha permessi 600 (solo owner read/write)
- ✅ `env.json` in `.gitignore` (mai committato)
- ✅ GitHub token usato via HTTPS (non esposto in process list)
- ⚠️ Backup directory locale - considera encryption at rest

## Troubleshooting

**"No repositories found or API error"**
- Verifica GitHub token valido
- Check scopes: deve avere `repo` (full control)
- Verifica username corretto

**Permission denied su /home/web/gitbackup**
```bash
sudo chown -R $USER:$USER /home/web/gitbackup
```

**Repo non aggiornate**
- Check `logs/gitbackup.log` per errori specifici
- Verifica token non scaduto
- Check network connectivity

## License

MIT

---

**IMPORTANTE**: NON committare mai `env.json`! Contiene il tuo GitHub token.

---

Co-Authored-By: Claude <noreply@anthropic.com>
