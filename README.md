# Personal VPN gateway

Open-source deployment kit for a small self-hosted WireGuard gateway on a US VPS. It provisions the server, creates one profile per device, and can revoke an individual device. The default profile routes all traffic through the VPS.

**Provider compatibility:** do not run the current playbook on a standard Oracle Cloud image. OCI requires preserving boot-volume firewall rules that this playbook currently replaces. See [Oracle account and VM setup](docs/ORACLE.md); OCI deployment support still needs implementation and live validation.

**Current status:** server automation and full-tunnel profile management are implemented. Selective routing for Claude Desktop, Claude Code, and Cursor on Windows/macOS is a planned client prototype. Strict per-app kill switch is **not implemented or verified**. See [the project plan](PLAN.md) for requirements and acceptance tests.

## Requirements

- A fresh **Ubuntu Server 24.04 LTS** VPS in the desired US location with a dedicated public IPv4 address, SSH access for a non-root sudo user, and a provider console for recovery. The VPS should have no other hosted services: this deployment owns `/etc/nftables.conf` and replaces its ruleset.
- A computer with Python 3.10+, Ansible Core, and `wg` from WireGuard tools. On macOS, `brew install wireguard-tools`; on Ubuntu, `sudo apt install wireguard-tools`.
- A working SSH public-key login to the VPS. Verify a new login and passwordless `sudo` before deployment; the current command does not prompt for a sudo password. The playbook disables password and root SSH login by default.
- A plan with at least 1 TB of **outbound** traffic included, and a known overage price. This is the initial target, not a traffic cap enforced by the software.

## Deploy

1. Create the VPS, add your SSH public key in the provider console, and log in once from your computer. Keep the provider's recovery console available.
2. Prepare the local configuration:

   ```sh
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install -r requirements.txt
   cp config.example.json config.json
   cp inventory/hosts.example.yml inventory/hosts.yml
   ```

3. Replace `203.0.113.10` in both local files with the VPS IPv4 address. Set `ansible_user` to the tested non-root sudo account. For a nonstandard SSH port, update both `ssh_port` in `config.json` and `ansible_port` in `inventory/hosts.yml`. Keep the VPN subnet defaults unless they conflict with a network you use.
4. Validate and deploy:

   ```sh
   python scripts/vpnctl.py check
   python scripts/vpnctl.py deploy
   ```

5. Test a **new SSH session** before closing the original one. Confirm the provider console still works.
6. Add one device and import its profile into the official WireGuard client:

   ```sh
   python scripts/vpnctl.py add work-mac
   ```

   The private profile is created at `secrets/peers/work-mac.conf`. Treat it as a credential. On Windows and macOS, install [the official WireGuard client](https://www.wireguard.com/install/), import the profile once, then use its connection switch. Do not share the profile through a public issue, screenshot, or repository.

After connection, verify that the visible IPv4 matches the VPS, DNS uses the VPN resolver, and IPv6 does not reveal the local network. The first release intentionally drops forwarded IPv6 rather than providing an IPv6 Internet exit; IPv6-only destinations will not work. Client OS behavior after the tunnel stops is separate from this server setting and must be tested before treating it as a kill switch.

## Device management

```sh
python scripts/vpnctl.py list
python scripts/vpnctl.py add second-device
python scripts/vpnctl.py revoke work-mac
```

`add` and `revoke` apply the server change immediately through Ansible. If deployment fails, the command returns an error and the change is **not confirmed on the VPS**. Fix the problem and run `python scripts/vpnctl.py deploy` again. `--no-deploy` prepares changes offline; always deploy before assuming a revoked device has lost access. A revoked profile is deleted locally after a successful deployment, but copies on the device or in backups must also be removed by the owner.

The public peer registry is `peers.json`. Client private keys and profiles live only in ignored `secrets/`. The server private key is generated and stored only on the VPS. Back up `secrets/` securely; do not commit it. If the server key is lost when replacing the VPS, the playbook stops while active peers still reference the old key. Revoke them offline with `--no-deploy`, deploy the new server, then issue fresh profiles under new names.

## Connectivity and recovery

- Firewall permits the configured SSH port on the public interface, the WireGuard UDP port, and DNS from the VPN network. It blocks VPN clients from reaching each other or SSH through the tunnel.
- The gateway uses Unbound for VPN DNS and nftables for firewall and IPv4 NAT. It enables automatic security updates without automatic reboot.
- If SSH stops working, use the provider console to inspect `/etc/nftables.conf`, `/etc/ssh/sshd_config.d/00-personal-vpn.conf`, and service status. Never disable the provider console before testing an SSH login after deployment.
- When a client cannot connect from a particular ISP, first verify UDP reachability and the server port. The optional AmneziaWG transport in [the plan](PLAN.md) is **not implemented** in this release.
- If DNS fails, check `wg-quick@wg0` and `unbound` on the VPS. DNS binds to the VPN address and starts after the WireGuard interface.

## Open-source safety

The repo excludes `config.json`, inventory with real addresses, generated profiles, and local state. Keep provider tokens and SSH keys outside this directory. Before making a repository public, inspect its entire history for secrets and follow [SECURITY.md](SECURITY.md). The project code is licensed under Apache-2.0; WireGuard and other installed packages retain their own licenses.

## Local checks

```sh
python -m unittest discover -s tests -v
ansible-playbook --syntax-check playbooks/site.yml
```

These checks do not prove a successful installation or kill switch on a real VPS and desktop. The live acceptance checks in [PLAN.md](PLAN.md) remain required.

Use [the verification checklist](docs/VERIFY.md) when testing a new VPS and each desktop platform.
