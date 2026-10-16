# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Deployment kit for a personal self-hosted WireGuard gateway on an Ubuntu 24.04 VPS. Two halves: a stdlib-only Python CLI (`scripts/vpnctl.py`) that manages peers and local state on the controller, and an Ansible playbook (`playbooks/site.yml` + `roles/gateway`) that configures the VPS (WireGuard, nftables, Unbound, SSH hardening, unattended-upgrades). All docs are in English; `docs/VERIFY.md` is the live acceptance checklist.

## Commands

Setup (one time): `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`, then `python scripts/vpnctl.py init <ip> --user <ssh-user> [--ssh-port N]`, which writes gitignored `config.json` (from `config.example.json`) and `inventory/hosts.yml` with matching endpoint and SSH port. `wg` (wireguard-tools) is needed locally for `add`.

CI (`.github/workflows/checks.yml`) runs exactly these, with the example files copied in place:

```sh
python -m unittest discover -s tests -v
python scripts/vpnctl.py check
ansible-playbook --syntax-check playbooks/site.yml
```

Single test: `python -m unittest tests.test_vpnctl.VpnCtlTests.test_duplicate_address_is_rejected -v` (run from repo root; tests import `scripts.vpnctl` as a package path).

CLI: `vpnctl.py init | check | deploy | list | add <name> [--no-deploy] | revoke <name> [--no-deploy]`. `deploy`, `add`, and `revoke` (without `--no-deploy`) run `ansible-playbook` against a real VPS — don't run them unless asked.

## Architecture and data flow

- **Shared state files are the contract between Python and Ansible.** The playbook reads `config.json` and `peers.json` directly via `lookup('file', ...) | from_json`, so any field added/renamed in `vpnctl.py` validation must also match the Jinja templates (`roles/gateway/templates/*.j2`) and the playbook's `pre_tasks` asserts.
- **`peers.json` is committed and public**: name, public key, IPv4/IPv6, optional `revoked: true`. Revoked peers stay in the registry forever (names and addresses are never reused); templates filter them with `rejectattr('revoked', 'defined')`. Private client keys/profiles live only in gitignored `secrets/peers/<name>.conf` (mode 0600, dir 0700).
- **Server private key never leaves the VPS.** Ansible generates `/etc/wireguard/wg0.key` there and writes only the public key back to the controller at `state/server.pub`, which `add` needs to build profiles. The playbook aborts if the server key changed while non-revoked peers exist.
- **Address allocation**: `/24` IPv4 and `/64` IPv6; server is `.1`/`::1`; peers get the same slot number in both (`next_slot`, slots 2–254). `load_config` adds derived `_ipv4_network`/`_ipv6_network` keys used by other functions.
- **Deploy semantics**: `add`/`revoke` write `peers.json` first, then deploy; on Ansible failure the change is saved locally but not confirmed on the VPS. Revoked profiles are deleted locally only after a successful deploy.
- **Ordering in `roles/gateway/tasks/main.yml` matters**: firewall is applied (handlers flushed) before WireGuard starts, WireGuard before Unbound (Unbound binds to the VPN address, with a systemd `Requires/After=wg-quick@wg0` override). nftables config does `flush ruleset` — the deployment owns the whole host firewall.
- Endpoint, names, and keys are regex-validated in `vpnctl.py` to prevent injection into generated WireGuard configs (see `test_invalid_endpoint_is_rejected_before_profile_generation`).

## Constraints to respect

- **Never lose SSH access**: changes to nftables or `sshd_config.d` must keep the configured `ssh_port` open on the public interface; the playbook asserts `config.ssh_port == ansible_port` and validates configs (`nft -c`, `sshd -t`, `unbound-checkconf`) before install.
- **Oracle Cloud is unsupported**: OCI images rely on iptables boot-volume rules (169.254.0.2 / 169.254.2.x) that `flush ruleset` would destroy. A pre-task detects them and stops. See `docs/ORACLE.md`.
- Forwarded IPv6 is intentionally dropped (no IPv6 exit); only IPv4 is NATed.
- Don't claim kill-switch or selective (per-app) routing behavior — both are planned, not implemented. Docs must not overstate verified behavior (CONTRIBUTING.md).
- Use only fictional addresses (`203.0.113.10`, documentation ranges) in examples and tests; never commit `config.json`, `inventory/hosts.yml`, `secrets/`, or `state/`.
