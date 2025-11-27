#!/usr/bin/env python3
"""
spawn_node.py - One-click backup node deployment

Usage:
    python3 spawn_node.py b1              # Create node b1
    python3 spawn_node.py b2 --provider hetzner
    python3 spawn_node.py b1 --destroy    # Destroy node (with notification)

Creates a fully configured backup node:
1. Spins up VM on provider (Scaleway/Hetzner)
2. Creates DNS bN.giobi.com via Cloudflare
3. Bootstraps via SSH:
   - User giobi with sudo
   - SSH keys from github.com/giobi.keys
   - .env with tokens (GitHub, Discord webhook)
   - gitbackup configured and running
   - Daily cron for backup + heartbeat
   - /env and /system endpoints
4. Sends Discord notification on completion
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Load .env
def load_env():
    env = {}
    locations = [
        Path(__file__).parent / '.env',
        Path('/home/claude/brain/.env'),
    ]
    for loc in locations:
        if loc.exists():
            with open(loc) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, val = line.split('=', 1)
                        env[key] = val.strip('"\'')
    return env

ENV = load_env()

# Config
CLOUDFLARE_ZONE_ID = "6d62ba1a288b65f07599ec938315ff12"  # giobi.com
GITHUB_KEYS_URL = "https://github.com/giobi.keys"

# Provider configs
PROVIDERS = {
    'scaleway': {
        'script': 'providers/scaleway.py',
        'cost': 1.80,
        'zone': 'fr-par-1',
        'type': 'STARDUST1-S',
    },
    'hetzner': {
        'script': 'providers/hetzner.py',
        'cost': 3.49,
        'zone': 'fsn1',
        'type': 'CX22',
    }
}


def discord_notify(message, webhook_url=None):
    """Send Discord notification via webhook"""
    webhook = webhook_url or ENV.get('DISCORD_BACKUP_WEBHOOK')
    if not webhook:
        print(f"⚠️  No Discord webhook configured, skipping notification")
        return False

    import requests
    try:
        r = requests.post(webhook, json={"content": message})
        return r.status_code == 204
    except Exception as e:
        print(f"⚠️  Discord notification failed: {e}")
        return False


def run_provider_cmd(provider, cmd, *args):
    """Run provider script command"""
    script = Path(__file__).parent / PROVIDERS[provider]['script']
    result = subprocess.run(
        ['python3', str(script), cmd] + list(args),
        capture_output=True, text=True
    )
    return result.stdout, result.stderr, result.returncode


def get_vm_ip(provider, name):
    """Get IP of VM by name"""
    stdout, _, _ = run_provider_cmd(provider, 'list')
    for line in stdout.split('\n'):
        if name in line:
            parts = line.split()
            for part in parts:
                if part.count('.') == 3:  # IP address
                    return part
    return None


def create_dns(name, ip):
    """Create DNS record via Cloudflare"""
    import requests

    token = ENV.get('CLOUDFLARE_API_TOKEN')
    if not token:
        print("❌ CLOUDFLARE_API_TOKEN not found")
        return False

    # Check if exists
    r = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records?name={name}.giobi.com",
        headers={"Authorization": f"Bearer {token}"}
    )
    existing = r.json().get('result', [])

    if existing:
        # Update
        record_id = existing[0]['id']
        r = requests.put(
            f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"type": "A", "name": name, "content": ip, "ttl": 300, "proxied": False}
        )
    else:
        # Create
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"type": "A", "name": name, "content": ip, "ttl": 300, "proxied": False}
        )

    return r.json().get('success', False)


def delete_dns(name):
    """Delete DNS record via Cloudflare"""
    import requests

    token = ENV.get('CLOUDFLARE_API_TOKEN')
    r = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records?name={name}.giobi.com",
        headers={"Authorization": f"Bearer {token}"}
    )
    existing = r.json().get('result', [])

    if existing:
        record_id = existing[0]['id']
        requests.delete(
            f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        return True
    return False


def wait_for_ssh(host, timeout=120):
    """Wait for SSH to be available"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, 22))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(5)
    return False


def ssh_run(host, cmd, user='root'):
    """Run command via SSH"""
    result = subprocess.run(
        ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
         f'{user}@{host}', cmd],
        capture_output=True, text=True
    )
    return result.stdout, result.stderr, result.returncode


def bootstrap_node(name, ip, provider):
    """Bootstrap node via SSH"""
    hostname = f"{name}.giobi.com"
    provider_info = PROVIDERS[provider]

    print(f"🔧 Bootstrapping {hostname}...")

    # Create user giobi with sudo
    setup_user = """
useradd -m -s /bin/bash giobi 2>/dev/null || true
usermod -aG sudo giobi
echo 'giobi ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/giobi
chmod 440 /etc/sudoers.d/giobi
mkdir -p /home/giobi/.ssh
curl -s https://github.com/giobi.keys > /home/giobi/.ssh/authorized_keys
chmod 700 /home/giobi/.ssh
chmod 600 /home/giobi/.ssh/authorized_keys
chown -R giobi:giobi /home/giobi/.ssh
"""
    ssh_run(ip, setup_user)
    print("  ✅ User giobi created")

    # Install packages
    ssh_run(ip, "apt-get update -qq && apt-get install -y -qq git curl nginx python3-requests")
    print("  ✅ Packages installed")

    # Set hostname
    ssh_run(ip, f"hostnamectl set-hostname {name}")

    # Create .env with tokens
    discord_webhook = ENV.get('DISCORD_BACKUP_WEBHOOK', '')
    github_token = ENV.get('GITHUB_TOKEN', '')

    env_content = f"""# {name} backup node config
NODE_NAME={name}
HOSTNAME={hostname}
PROVIDER={provider}
GITHUB_TOKEN={github_token}
DISCORD_WEBHOOK_URL={discord_webhook}
CREATED={datetime.now().isoformat()}
"""
    ssh_run(ip, f"cat > /home/giobi/.env << 'EOF'\n{env_content}\nEOF")
    ssh_run(ip, "chown giobi:giobi /home/giobi/.env && chmod 600 /home/giobi/.env")
    print("  ✅ .env configured")

    # Clone gitbackup
    ssh_run(ip, "sudo -u giobi git clone https://github.com/giobi/gitbackup.git /home/giobi/gitbackup 2>/dev/null || true")
    ssh_run(ip, "mkdir -p /home/giobi/backup && chown giobi:giobi /home/giobi/backup")
    print("  ✅ gitbackup cloned")

    # Create daily backup script with Discord notification
    daily_script = f'''#!/bin/bash
source /home/giobi/.env

# Run backup
cd /home/giobi/gitbackup
./backup.sh > /tmp/backup.log 2>&1
RESULT=$?

# Count repos
REPOS=$(ls -1 /home/giobi/backup 2>/dev/null | wc -l)
DISK=$(df -h / | awk 'NR==2 {{print $3 "/" $2}}')
UPTIME=$(uptime -p)

# Send heartbeat to Discord
if [ -n "$DISCORD_WEBHOOK_URL" ]; then
    if [ $RESULT -eq 0 ]; then
        MSG="💚 **$NODE_NAME** heartbeat | $REPOS repos | Disk: $DISK | $UPTIME"
    else
        MSG="💔 **$NODE_NAME** backup FAILED | Check logs"
    fi
    curl -s -H "Content-Type: application/json" -d "{{\\"content\\": \\"$MSG\\"}}" "$DISCORD_WEBHOOK_URL"
fi
'''
    ssh_run(ip, f"cat > /home/giobi/daily-backup.sh << 'EOF'\n{daily_script}\nEOF")
    ssh_run(ip, "chmod +x /home/giobi/daily-backup.sh && chown giobi:giobi /home/giobi/daily-backup.sh")

    # Setup cron
    ssh_run(ip, '(crontab -u giobi -l 2>/dev/null; echo "0 3 * * * /home/giobi/daily-backup.sh") | crontab -u giobi -')
    print("  ✅ Daily backup cron configured")

    # Setup /env and /system endpoints
    env_json = json.dumps({
        "node": name,
        "hostname": hostname,
        "provider": provider,
        "zone": provider_info['zone'],
        "type": provider_info['type'],
        "purpose": "gitbackup-node",
        "cost_monthly_eur": provider_info['cost'],
        "created": datetime.now().strftime('%Y-%m-%d'),
        "owner": "giobi",
        "ssh": f"giobi@{hostname}",
        "services": ["gitbackup", "heartbeat"],
        "status": "active"
    }, indent=2)

    ssh_run(ip, f"cat > /var/www/html/env.json << 'EOF'\n{env_json}\nEOF")

    # System JSON update script
    system_script = '''#!/bin/bash
cat << EOFJ > /var/www/html/system.json
{
  "hostname": "$(hostname)",
  "uptime": "$(uptime -p)",
  "load": "$(cat /proc/loadavg | cut -d' ' -f1-3)",
  "memory_mb": {
    "total": $(free -m | awk '/Mem:/ {print $2}'),
    "used": $(free -m | awk '/Mem:/ {print $3}'),
    "free": $(free -m | awk '/Mem:/ {print $4}')
  },
  "disk_gb": {
    "total": $(df -BG / | awk 'NR==2 {print $2}' | tr -d 'G'),
    "used": $(df -BG / | awk 'NR==2 {print $3}' | tr -d 'G'),
    "free": $(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
  },
  "repos": $(ls -1 /home/giobi/backup 2>/dev/null | wc -l),
  "ip": "$(hostname -I | awk '{print $1}')",
  "updated": "$(date -Iseconds)"
}
EOFJ
'''
    ssh_run(ip, f"cat > /usr/local/bin/update-system-json.sh << 'EOF'\n{system_script}\nEOF")
    ssh_run(ip, "chmod +x /usr/local/bin/update-system-json.sh && /usr/local/bin/update-system-json.sh")
    ssh_run(ip, '(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/update-system-json.sh") | crontab -')

    # Nginx config
    nginx_conf = '''server {
    listen 80 default_server;
    root /var/www/html;
    server_name _;

    location /env { alias /var/www/html/env.json; default_type application/json; }
    location /system { alias /var/www/html/system.json; default_type application/json; }
    location / { return 200 '{"node": "''' + name + '''", "endpoints": ["/env", "/system"]}'; default_type application/json; }
}'''
    ssh_run(ip, f"cat > /etc/nginx/sites-available/default << 'EOF'\n{nginx_conf}\nEOF")
    ssh_run(ip, "nginx -t && systemctl reload nginx")
    print("  ✅ Nginx endpoints configured")

    # Configure gitbackup
    gitbackup_config = json.dumps({
        "github_token": github_token,
        "github_username": "giobi",
        "backup_dir": "/home/giobi/backup"
    })
    ssh_run(ip, f"cat > /home/giobi/gitbackup/env.json << 'EOF'\n{gitbackup_config}\nEOF")
    ssh_run(ip, "chown giobi:giobi /home/giobi/gitbackup/env.json && chmod 600 /home/giobi/gitbackup/env.json")
    print("  ✅ gitbackup configured")

    return True


def spawn_node(name, provider='scaleway'):
    """Spawn a new backup node"""
    print(f"\n🚀 Spawning {name} on {provider}...\n")

    # 1. Create VM
    print(f"1️⃣  Creating VM...")
    stdout, stderr, code = run_provider_cmd(provider, 'create', name)
    print(stdout)
    if code != 0:
        print(f"❌ Failed to create VM: {stderr}")
        return False

    # 2. Wait for VM and get IP
    print(f"2️⃣  Waiting for VM to start...")
    time.sleep(15)  # Initial wait
    ip = None
    for _ in range(12):  # Max 1 minute
        ip = get_vm_ip(provider, name)
        if ip:
            break
        time.sleep(5)

    if not ip:
        print("❌ Could not get VM IP")
        return False
    print(f"   IP: {ip}")

    # 3. Create DNS
    print(f"3️⃣  Creating DNS {name}.giobi.com...")
    if create_dns(name, ip):
        print(f"   ✅ DNS created")
    else:
        print(f"   ⚠️  DNS creation failed (may already exist)")

    # 4. Wait for SSH
    print(f"4️⃣  Waiting for SSH...")
    if not wait_for_ssh(ip):
        print("❌ SSH timeout")
        return False
    print(f"   ✅ SSH ready")
    time.sleep(5)  # Extra wait for system to settle

    # 5. Bootstrap
    print(f"5️⃣  Bootstrapping node...")
    if not bootstrap_node(name, ip, provider):
        print("❌ Bootstrap failed")
        return False

    # 6. Notify
    hostname = f"{name}.giobi.com"
    msg = f"🟢 **{name}** is ALIVE!\n" \
          f"• Provider: {provider}\n" \
          f"• IP: {ip}\n" \
          f"• SSH: `ssh giobi@{hostname}`\n" \
          f"• Endpoints: http://{hostname}/env"
    discord_notify(msg)

    print(f"\n✅ {hostname} is ready!")
    print(f"   SSH: ssh giobi@{hostname}")
    print(f"   Web: http://{hostname}/env")

    return True


def destroy_node(name, provider='scaleway'):
    """Destroy a backup node with notification"""
    hostname = f"{name}.giobi.com"
    print(f"\n🗑️  Destroying {hostname}...\n")

    # Notify before destruction
    msg = f"🔴 **{name}** shutting down..."
    discord_notify(msg)

    # Get IP for final info
    ip = get_vm_ip(provider, name)

    # Destroy VM
    stdout, stderr, code = run_provider_cmd(provider, 'destroy')
    print(stdout)

    # Delete DNS
    delete_dns(name)
    print(f"   ✅ DNS deleted")

    # Final notification
    msg = f"💀 **{name}** destroyed\n• Was at: {ip or 'unknown'}"
    discord_notify(msg)

    print(f"\n✅ {hostname} destroyed")
    return True


def main():
    parser = argparse.ArgumentParser(description='Spawn/destroy backup nodes')
    parser.add_argument('name', help='Node name (e.g., b1, b2)')
    parser.add_argument('--provider', '-p', default='scaleway', choices=['scaleway', 'hetzner'])
    parser.add_argument('--destroy', '-d', action='store_true', help='Destroy node')

    args = parser.parse_args()

    if args.destroy:
        destroy_node(args.name, args.provider)
    else:
        spawn_node(args.name, args.provider)


if __name__ == '__main__':
    main()
