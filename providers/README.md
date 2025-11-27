# Multi-Cloud Providers

Scripts per gestire VM su provider cloud diversi via API.

## Provider Supportati

| Provider | Script | Status |
|----------|--------|--------|
| Hetzner | `hetzner.py` | 🚧 Da implementare |
| Scaleway | `scaleway.py` | 🚧 Da implementare |

## Requisiti

Variabili in `.env` (root del progetto o brain):

```bash
HETZNER_API_TOKEN=xxx
SCALEWAY_API_KEY=xxx
SCALEWAY_SECRET_KEY=xxx
SCALEWAY_ORGANIZATION_ID=xxx
```

## Uso

```bash
# Hetzner
python3 providers/hetzner.py create   # Crea VM
python3 providers/hetzner.py snapshot # Crea snapshot
python3 providers/hetzner.py destroy  # Distrugge VM
python3 providers/hetzner.py list     # Lista VM

# Scaleway
python3 providers/scaleway.py create
python3 providers/scaleway.py snapshot
python3 providers/scaleway.py destroy
python3 providers/scaleway.py list
```

## Cloud-init

Le VM vengono create con cloud-init che:
1. Clona brain repo
2. Esegue gitbackup
3. (Opzionale) Si autodistrugge dopo il job

Template in `providers/cloud-init/`
