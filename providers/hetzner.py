#!/usr/bin/env python3
"""
Hetzner Cloud API wrapper per gitbackup multi-cloud

Requisiti:
    HETZNER_API_TOKEN in .env

Uso:
    python3 hetzner.py create   # Crea VM CX22
    python3 hetzner.py list     # Lista VM
    python3 hetzner.py snapshot # Crea snapshot
    python3 hetzner.py destroy  # Distrugge VM
"""

import os
import sys
import json
import requests
from pathlib import Path

# Load env from multiple locations
def load_env():
    """Load HETZNER_API_TOKEN from .env files"""
    locations = [
        Path(__file__).parent.parent / '.env',  # gitbackup/.env
        Path('/home/claude/brain/.env'),         # brain/.env
        Path.home() / '.env'                     # ~/.env
    ]

    for loc in locations:
        if loc.exists():
            with open(loc) as f:
                for line in f:
                    if line.startswith('HETZNER_API_TOKEN='):
                        return line.strip().split('=', 1)[1].strip('"\'')

    # Fallback to environment
    return os.environ.get('HETZNER_API_TOKEN')


API_TOKEN = load_env()
BASE_URL = "https://api.hetzner.cloud/v1"

# Default VM config
VM_CONFIG = {
    "name": "gitbackup-node",
    "server_type": "cx22",  # 2 vCPU, 4GB RAM, €3.49/mo
    "image": "ubuntu-22.04",
    "location": "fsn1",  # Falkenstein, Germany
    "start_after_create": True,
}


def api_request(method, endpoint, data=None):
    """Make authenticated API request"""
    if not API_TOKEN:
        print("❌ HETZNER_API_TOKEN not found in .env")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/{endpoint}"

    if method == "GET":
        r = requests.get(url, headers=headers)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=data)
    elif method == "DELETE":
        r = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unknown method: {method}")

    if r.status_code >= 400:
        print(f"❌ API Error {r.status_code}: {r.text}")
        sys.exit(1)

    return r.json() if r.text else {}


def list_servers():
    """List all servers"""
    data = api_request("GET", "servers")
    servers = data.get("servers", [])

    if not servers:
        print("No servers found")
        return

    print(f"\n{'Name':<20} {'Status':<12} {'IP':<16} {'Type':<10}")
    print("-" * 60)
    for s in servers:
        ip = s.get("public_net", {}).get("ipv4", {}).get("ip", "N/A")
        print(f"{s['name']:<20} {s['status']:<12} {ip:<16} {s['server_type']['name']:<10}")


def create_server(cloud_init_file=None):
    """Create new server"""
    config = VM_CONFIG.copy()

    # Load cloud-init if provided
    if cloud_init_file and Path(cloud_init_file).exists():
        with open(cloud_init_file) as f:
            config["user_data"] = f.read()

    print(f"🚀 Creating server: {config['name']} ({config['server_type']})")
    data = api_request("POST", "servers", config)

    server = data.get("server", {})
    ip = server.get("public_net", {}).get("ipv4", {}).get("ip", "pending")

    print(f"✅ Server created!")
    print(f"   ID: {server['id']}")
    print(f"   IP: {ip}")
    print(f"   Root password: {data.get('root_password', 'N/A')}")

    return server


def destroy_server(server_id=None):
    """Destroy server by ID or name"""
    if not server_id:
        # Find gitbackup-node
        data = api_request("GET", "servers")
        for s in data.get("servers", []):
            if s["name"] == VM_CONFIG["name"]:
                server_id = s["id"]
                break

    if not server_id:
        print("❌ No server found to destroy")
        return

    print(f"🗑️  Destroying server {server_id}...")
    api_request("DELETE", f"servers/{server_id}")
    print("✅ Server destroyed")


def create_snapshot(server_id=None):
    """Create snapshot of server"""
    if not server_id:
        # Find gitbackup-node
        data = api_request("GET", "servers")
        for s in data.get("servers", []):
            if s["name"] == VM_CONFIG["name"]:
                server_id = s["id"]
                break

    if not server_id:
        print("❌ No server found to snapshot")
        return

    print(f"📸 Creating snapshot of server {server_id}...")
    data = api_request("POST", f"servers/{server_id}/actions/create_image", {
        "description": f"gitbackup-snapshot",
        "type": "snapshot"
    })

    print(f"✅ Snapshot created: {data.get('image', {}).get('id')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: hetzner.py <command>")
        print("Commands: list, create, destroy, snapshot")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        list_servers()
    elif cmd == "create":
        cloud_init = sys.argv[2] if len(sys.argv) > 2 else None
        create_server(cloud_init)
    elif cmd == "destroy":
        server_id = sys.argv[2] if len(sys.argv) > 2 else None
        destroy_server(server_id)
    elif cmd == "snapshot":
        server_id = sys.argv[2] if len(sys.argv) > 2 else None
        create_snapshot(server_id)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
