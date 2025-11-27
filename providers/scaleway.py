#!/usr/bin/env python3
"""
Scaleway API wrapper per gitbackup multi-cloud

Requisiti in .env:
    SCALEWAY_ACCESS_KEY
    SCALEWAY_SECRET_KEY
    SCALEWAY_ORGANIZATION_ID
    SCALEWAY_PROJECT_ID

Uso:
    python3 scaleway.py create   # Crea VM Stardust
    python3 scaleway.py list     # Lista VM
    python3 scaleway.py snapshot # Crea snapshot
    python3 scaleway.py destroy  # Distrugge VM
"""

import os
import sys
import json
import requests
from pathlib import Path

# Load env from multiple locations
def load_env():
    """Load Scaleway credentials from .env files"""
    locations = [
        Path(__file__).parent.parent / '.env',  # gitbackup/.env
        Path('/home/claude/brain/.env'),         # brain/.env
        Path.home() / '.env'                     # ~/.env
    ]

    creds = {}
    keys = ['SCALEWAY_ACCESS_KEY', 'SCALEWAY_SECRET_KEY', 'SCALEWAY_ORGANIZATION_ID', 'SCALEWAY_PROJECT_ID']

    for loc in locations:
        if loc.exists():
            with open(loc) as f:
                for line in f:
                    for key in keys:
                        if line.startswith(f'{key}='):
                            creds[key] = line.strip().split('=', 1)[1].strip('"\'')

    # Fallback to environment
    for key in keys:
        if key not in creds:
            creds[key] = os.environ.get(key)

    return creds


CREDS = load_env()
BASE_URL = "https://api.scaleway.com/instance/v1/zones/fr-par-1"
BLOCK_URL = "https://api.scaleway.com/block/v1/zones/fr-par-1"

# Default VM config - Stardust
VM_CONFIG = {
    "name": "gitbackup-node",
    "commercial_type": "STARDUST1-S",  # 1 vCPU, 1GB RAM, €1.80/mo
    "image": "ubuntu_jammy",  # Ubuntu 22.04
    "dynamic_ip_required": True,
}


def api_request(method, endpoint, data=None, base_url=None):
    """Make authenticated API request"""
    if not CREDS.get('SCALEWAY_SECRET_KEY'):
        print("❌ SCALEWAY_SECRET_KEY not found in .env")
        sys.exit(1)

    headers = {
        "X-Auth-Token": CREDS['SCALEWAY_SECRET_KEY'],
        "Content-Type": "application/json"
    }

    url = f"{base_url or BASE_URL}/{endpoint}"

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

    print(f"\n{'Name':<20} {'State':<12} {'IP':<16} {'Type':<15}")
    print("-" * 65)
    for s in servers:
        ip = s.get("public_ip", {}).get("address", "N/A") if s.get("public_ip") else "N/A"
        print(f"{s['name']:<20} {s['state']:<12} {ip:<16} {s['commercial_type']:<15}")


def create_server(cloud_init_file=None):
    """Create new server"""
    config = VM_CONFIG.copy()

    if CREDS.get('SCALEWAY_PROJECT_ID'):
        config['project'] = CREDS['SCALEWAY_PROJECT_ID']
    elif CREDS.get('SCALEWAY_ORGANIZATION_ID'):
        config['organization'] = CREDS['SCALEWAY_ORGANIZATION_ID']

    # Load cloud-init if provided
    if cloud_init_file and Path(cloud_init_file).exists():
        with open(cloud_init_file) as f:
            # Scaleway uses tags for cloud-init, or you can use user_data
            pass  # TODO: implement cloud-init for Scaleway

    print(f"🚀 Creating server: {config['name']} ({config['commercial_type']})")
    data = api_request("POST", "servers", config)

    server = data.get("server", {})
    print(f"✅ Server created!")
    print(f"   ID: {server.get('id')}")
    print(f"   State: {server.get('state')}")

    # Need to start the server after creation
    if server.get('id'):
        print("🔄 Starting server...")
        api_request("POST", f"servers/{server['id']}/action", {"action": "poweron"})
        print("✅ Server starting...")

    return server


def destroy_server(server_id=None, cleanup_volumes=True):
    """Destroy server by ID or name, optionally cleanup orphan volumes"""
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

    # Get volume IDs before destroying
    volume_ids = []
    if cleanup_volumes:
        server = api_request("GET", f"servers/{server_id}")
        volumes = server.get("server", {}).get("volumes", {})
        for vol in volumes.values():
            if vol.get("volume_type") == "sbs_volume":
                volume_ids.append(vol.get("id"))

    # First poweroff
    print(f"⏹️  Powering off server {server_id}...")
    try:
        api_request("POST", f"servers/{server_id}/action", {"action": "poweroff"})
    except:
        pass  # May already be off

    # Wait for poweroff to complete
    import time
    for i in range(30):  # Max 30 seconds
        time.sleep(1)
        data = api_request("GET", f"servers/{server_id}")
        state = data.get("server", {}).get("state")
        if state == "stopped":
            break
        print(f"   Waiting... ({state})")

    print(f"🗑️  Destroying server {server_id}...")
    api_request("DELETE", f"servers/{server_id}")
    print("✅ Server destroyed")

    # Cleanup orphan SBS volumes
    if cleanup_volumes and volume_ids:
        import time
        print("⏳ Waiting for volumes to detach...")
        time.sleep(5)
        for vol_id in volume_ids:
            print(f"🗑️  Deleting orphan volume {vol_id}...")
            try:
                api_request("DELETE", f"volumes/{vol_id}", base_url=BLOCK_URL)
                print(f"✅ Volume {vol_id} deleted")
            except:
                print(f"⚠️  Could not delete volume {vol_id} (may need manual cleanup)")


def create_snapshot(server_id=None):
    """Create snapshot of server volumes (supports both local and SBS volumes)"""
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

    # Get server details for volume ID
    server = api_request("GET", f"servers/{server_id}")
    volumes = server.get("server", {}).get("volumes", {})

    if not volumes:
        print("❌ No volumes found on server")
        return

    # Snapshot each volume
    for vol_key, vol in volumes.items():
        vol_id = vol.get("id")
        vol_type = vol.get("volume_type", "l_ssd")  # l_ssd = local, sbs_volume = block storage

        print(f"📸 Creating snapshot of volume {vol_id} (type: {vol_type})...")

        if vol_type == "sbs_volume":
            # Use Block Storage API for SBS volumes
            snapshot_data = {
                "volume_id": vol_id,
                "name": f"gitbackup-snapshot-{vol_key}"
            }
            if CREDS.get('SCALEWAY_PROJECT_ID'):
                snapshot_data['project_id'] = CREDS['SCALEWAY_PROJECT_ID']
            data = api_request("POST", "snapshots", snapshot_data, base_url=BLOCK_URL)
            print(f"✅ SBS Snapshot created: {data.get('snapshot', {}).get('id')}")
        else:
            # Use Instance API for local volumes
            snapshot_data = {
                "volume_id": vol_id,
                "name": f"gitbackup-snapshot-{vol_key}"
            }
            if CREDS.get('SCALEWAY_PROJECT_ID'):
                snapshot_data['project'] = CREDS['SCALEWAY_PROJECT_ID']
            data = api_request("POST", "snapshots", snapshot_data)
            print(f"✅ Local Snapshot created: {data.get('snapshot', {}).get('id')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: scaleway.py <command>")
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
