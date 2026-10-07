#!/usr/bin/env python3
"""Manage local WireGuard peers and deploy the public server configuration."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
HOST_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}\Z")


class VpnError(Exception):
    """A user-facing configuration or deployment error."""


def atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VpnError(f"Missing {path}. Copy the example and complete it first.") from exc
    except json.JSONDecodeError as exc:
        raise VpnError(f"Invalid JSON in {path}: {exc}") from exc


def load_config(root: Path) -> dict:
    config = load_json(root / "config.json")
    if not isinstance(config, dict):
        raise VpnError("config.json must contain an object")
    required = ("endpoint", "port", "ssh_port", "ipv4_network", "server_ipv4", "ipv6_network", "server_ipv6")
    missing = [key for key in required if key not in config]
    if missing:
        raise VpnError(f"Missing config fields: {', '.join(missing)}")
    endpoint = config["endpoint"]
    if not isinstance(endpoint, str) or not HOST_RE.fullmatch(endpoint) or ".." in endpoint:
        raise VpnError("endpoint must be a public IPv4 address or DNS hostname")
    try:
        port = int(config["port"])
        ssh_port = int(config["ssh_port"])
        ipv4_net = ipaddress.ip_network(config["ipv4_network"], strict=True)
        ipv6_net = ipaddress.ip_network(config["ipv6_network"], strict=True)
        server_ipv4 = ipaddress.ip_address(config["server_ipv4"])
        server_ipv6 = ipaddress.ip_address(config["server_ipv6"])
    except (TypeError, ValueError) as exc:
        raise VpnError(f"Invalid network setting: {exc}") from exc
    if not 1 <= port <= 65535:
        raise VpnError("port must be between 1 and 65535")
    if not 1 <= ssh_port <= 65535:
        raise VpnError("ssh_port must be between 1 and 65535")
    if ipv4_net.version != 4 or ipv4_net.prefixlen != 24:
        raise VpnError("ipv4_network must be a /24 IPv4 network")
    if ipv6_net.version != 6 or ipv6_net.prefixlen != 64:
        raise VpnError("ipv6_network must be a /64 IPv6 network")
    if server_ipv4 not in ipv4_net or server_ipv6 not in ipv6_net:
        raise VpnError("server addresses must belong to the configured networks")
    if server_ipv4 != ipv4_net.network_address + 1 or server_ipv6 != ipv6_net.network_address + 1:
        raise VpnError("server addresses must be the first host address in each network")
    config["port"] = port
    config["ssh_port"] = ssh_port
    config["_ipv4_network"] = ipv4_net
    config["_ipv6_network"] = ipv6_net
    return config


def load_peers(root: Path, config: dict) -> list[dict]:
    peers = load_json(root / "peers.json")
    if not isinstance(peers, list):
        raise VpnError("peers.json must contain an array")
    names: set[str] = set()
    addresses: set[str] = set()
    for peer in peers:
        if not isinstance(peer, dict) or not all(
            key in peer for key in ("name", "public_key", "ipv4", "ipv6")
        ):
            raise VpnError("Every peer needs name, public_key, ipv4 and ipv6")
        name = peer["name"]
        if not isinstance(name, str) or not NAME_RE.fullmatch(name) or name in names:
            raise VpnError(f"Invalid or duplicate peer name: {name}")
        names.add(name)
        if not isinstance(peer["public_key"], str) or not re.fullmatch(r"[A-Za-z0-9+/]{43}=", peer["public_key"]):
            raise VpnError(f"Invalid public key for {name}")
        try:
            ipv4 = ipaddress.ip_address(peer["ipv4"])
            ipv6 = ipaddress.ip_address(peer["ipv6"])
        except ValueError as exc:
            raise VpnError(f"Invalid address for {name}: {exc}") from exc
        if ipv4 not in config["_ipv4_network"] or ipv6 not in config["_ipv6_network"]:
            raise VpnError(f"Peer {name} is outside the configured VPN networks")
        if str(ipv4) in addresses or str(ipv6) in addresses:
            raise VpnError(f"Duplicate VPN address for {name}")
        addresses.update((str(ipv4), str(ipv6)))
        if "revoked" in peer and peer["revoked"] is not True:
            raise VpnError(f"revoked must be true or absent for {name}")
    return peers


def save_peers(root: Path, peers: list[dict]) -> None:
    atomic_write(root / "peers.json", json.dumps(peers, indent=2, ensure_ascii=False) + "\n", 0o644)


def generate_keypair() -> tuple[str, str]:
    if shutil.which("wg") is None:
        raise VpnError("Install WireGuard tools so the 'wg' command is available")
    try:
        private = subprocess.run(["wg", "genkey"], check=True, capture_output=True, text=True).stdout.strip()
        public = subprocess.run(
            ["wg", "pubkey"], input=private + "\n", check=True, capture_output=True, text=True
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise VpnError(f"WireGuard key generation failed: {exc.stderr.strip()}") from exc
    return private, public


def next_slot(peers: list[dict], config: dict) -> int:
    occupied = {int(ipaddress.ip_address(peer["ipv4"])) for peer in peers}
    base = int(config["_ipv4_network"].network_address)
    for slot in range(2, 255):
        if base + slot not in occupied:
            return slot
    raise VpnError("The VPN address pool is full")


def profile(name: str, private_key: str, server_public_key: str, ipv4: str, ipv6: str, config: dict) -> str:
    return (
        f"# Personal VPN profile: {name}\n"
        "[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {ipv4}/32, {ipv6}/128\n"
        f"DNS = {config['server_ipv4']}\n\n"
        "[Peer]\n"
        f"PublicKey = {server_public_key}\n"
        f"Endpoint = {config['endpoint']}:{config['port']}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        "PersistentKeepalive = 25\n"
    )


def deploy(root: Path) -> None:
    if shutil.which("ansible-playbook") is None:
        raise VpnError("Install requirements.txt and activate the virtual environment before deploying")
    result = subprocess.run(["ansible-playbook", "playbooks/site.yml"], cwd=root, check=False)
    if result.returncode != 0:
        raise VpnError("Deployment failed. Peer changes may not be active on the VPS; fix the error and run 'deploy'.")
    for peer in load_json(root / "peers.json"):
        if peer.get("revoked") is True:
            (root / "secrets" / "peers" / f"{peer['name']}.conf").unlink(missing_ok=True)


def add_peer(root: Path, name: str, deploy_now: bool = True) -> Path:
    if not NAME_RE.fullmatch(name):
        raise VpnError("Peer name must start with a lowercase letter and use up to 32 letters, digits, '-' or '_'")
    config = load_config(root)
    peers = load_peers(root, config)
    if any(peer["name"] == name for peer in peers):
        raise VpnError(f"Peer {name} already exists or was revoked; choose a new name")
    server_key_path = root / "state" / "server.pub"
    try:
        server_public_key = server_key_path.read_text(encoding="ascii").strip()
    except FileNotFoundError as exc:
        raise VpnError("Deploy the server first to obtain state/server.pub") from exc
    if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", server_public_key):
        raise VpnError("Invalid server public key in state/server.pub")
    private_key, public_key = generate_keypair()
    slot = next_slot(peers, config)
    ipv4 = str(config["_ipv4_network"].network_address + slot)
    ipv6 = str(config["_ipv6_network"].network_address + slot)
    path = root / "secrets" / "peers" / f"{name}.conf"
    if path.exists():
        raise VpnError(f"Profile already exists: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent.parent, 0o700)
    os.chmod(path.parent, 0o700)
    atomic_write(path, profile(name, private_key, server_public_key, ipv4, ipv6, config), 0o600)
    peers.append({"name": name, "public_key": public_key, "ipv4": ipv4, "ipv6": ipv6})
    save_peers(root, peers)
    if deploy_now:
        deploy(root)
    return path


def revoke_peer(root: Path, name: str, deploy_now: bool = True) -> None:
    config = load_config(root)
    peers = load_peers(root, config)
    peer = next((item for item in peers if item["name"] == name), None)
    if peer is None or peer.get("revoked") is True:
        raise VpnError(f"Active peer not found: {name}")
    peer["revoked"] = True
    save_peers(root, peers)
    if deploy_now:
        deploy(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate local public configuration")
    subparsers.add_parser("deploy", help="configure the VPS from local state")
    subparsers.add_parser("list", help="list peers without showing keys")
    add_parser = subparsers.add_parser("add", help="create a profile and grant access")
    add_parser.add_argument("name")
    add_parser.add_argument("--no-deploy", action="store_true", help="prepare changes offline")
    revoke_parser = subparsers.add_parser("revoke", help="remove a peer from the server")
    revoke_parser.add_argument("name")
    revoke_parser.add_argument("--no-deploy", action="store_true", help="prepare changes offline")
    args = parser.parse_args()
    try:
        if args.command == "deploy":
            load_peers(PROJECT_ROOT, load_config(PROJECT_ROOT))
            deploy(PROJECT_ROOT)
            print("VPS configuration applied")
        elif args.command == "check":
            peers = load_peers(PROJECT_ROOT, load_config(PROJECT_ROOT))
            print(f"Configuration valid; {sum(not peer.get('revoked', False) for peer in peers)} active peers")
        elif args.command == "list":
            peers = load_peers(PROJECT_ROOT, load_config(PROJECT_ROOT))
            for peer in peers:
                status = "revoked" if peer.get("revoked") else "active"
                print(f"{peer['name']}: {status} ({peer['ipv4']})")
        elif args.command == "add":
            path = add_peer(PROJECT_ROOT, args.name, deploy_now=not args.no_deploy)
            print(f"Profile: {path}")
            if args.no_deploy:
                print("Run 'deploy' before using the profile")
        elif args.command == "revoke":
            revoke_peer(PROJECT_ROOT, args.name, deploy_now=not args.no_deploy)
            print(f"Revocation prepared for {args.name}" if args.no_deploy else f"Revoked {args.name}")
    except VpnError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
