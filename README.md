# Personal VPN gateway

Turn a fresh VPS into your own WireGuard VPN in a few commands. One profile per device, revoke any device at any time, all traffic routed through the server.

- **WireGuard** tunnel, **Unbound** DNS resolver on the server, **nftables** firewall with IPv4 NAT.
- Server private key is generated on the VPS and never leaves it; client keys stay on your computer.
- SSH hardening (no password or root login) and automatic security updates.
- Works with the official WireGuard apps on Windows, macOS, Linux, iOS and Android.

> **Status: early release, not yet validated on a live VPS.** Unit tests and Ansible syntax checks pass in CI, but a full end-to-end run ([docs/VERIFY.md](docs/VERIFY.md)) hasn't been done yet. Deploy only to a fresh, disposable VPS with console access, and please [open an issue](../../issues) with your results, whether it worked or not.

## Requirements

**Server:** a fresh **Ubuntu Server 24.04 LTS** VPS with a public IPv4 address, used only for this VPN. The playbook replaces the whole host firewall (`/etc/nftables.conf`), so don't run it on a machine that hosts other services. You need SSH key login as a **non-root user with passwordless `sudo`**, and access to the provider's web console for recovery.

> Oracle Cloud is not supported yet: its images depend on firewall rules this playbook would remove. The playbook detects this and stops. See [docs/ORACLE.md](docs/ORACLE.md).

**Your computer:** Python 3.10+, `git`, and WireGuard tools (`brew install wireguard-tools` on macOS, `sudo apt install wireguard-tools` on Ubuntu/Debian).

## Quick start

```sh
git clone <this repository> personal-vpn && cd personal-vpn
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python scripts/vpnctl.py init 198.51.100.7 --user ubuntu   # your VPS IP and SSH user
python scripts/vpnctl.py deploy
python scripts/vpnctl.py add laptop
```

`init` takes `--ssh-port` if SSH isn't on port 22. Before `deploy`, check that `ssh ubuntu@198.51.100.7 sudo -n true` works without a password prompt.

After `deploy`, **open a new SSH session before closing the old one** to confirm you still have access.

`add` writes the device profile to `secrets/peers/laptop.conf`. Import it into the [WireGuard app](https://www.wireguard.com/install/) and switch it on. On a phone, `qrencode -t ansiutf8 < secrets/peers/laptop.conf` shows a QR code to scan. The profile is a credential: don't post it, screenshot it, or commit it.

Then check that your public IPv4 is the VPS address, and that DNS and IPv6 leak tests show nothing from your local network. [docs/VERIFY.md](docs/VERIFY.md) has the full checklist.

## Managing devices

```sh
python scripts/vpnctl.py list
python scripts/vpnctl.py add phone
python scripts/vpnctl.py revoke laptop
```

`add` and `revoke` apply the change to the server right away. If the deployment fails, the change is saved locally but **not active on the server**: fix the error and run `deploy` again. `--no-deploy` prepares a change offline. Revoked names can't be reused. After a successful revoke the local profile is deleted; remove any copies on the device yourself.

## What is stored where

| Location | Contents | In git? |
| --- | --- | --- |
| `peers.json` | device names, public keys, VPN addresses | yes (public data only) |
| `config.json`, `inventory/hosts.yml` | your server address and SSH user | no |
| `secrets/peers/*.conf` | device private keys and profiles | no |
| `state/server.pub` | server public key | no |
| VPS `/etc/wireguard/wg0.key` | server private key | never leaves the server |

Back up `secrets/` and `state/` somewhere safe. If you move to a new VPS, the server key changes and the playbook stops while old devices are active. Revoke them with `--no-deploy`, deploy, then add fresh profiles under new names. If you fork this repo to keep your own `peers.json`, keep that fork private if you don't want device names public.

## Network behavior

- Open ports on the server: SSH (on the public interface only) and the WireGuard UDP port (default `51820`). DNS answers only inside the tunnel.
- VPN clients can't reach each other or SSH through the tunnel.
- Forwarded IPv6 is dropped, so IPv6 doesn't leak, but IPv6-only sites won't load.
- The server doesn't block traffic when the tunnel drops. Whether apps fall back to your normal connection depends on the client OS. Test it yourself before relying on it as a kill switch.

## Troubleshooting

- **Lost SSH:** use the provider console and check `/etc/nftables.conf`, `/etc/ssh/sshd_config.d/00-personal-vpn.conf`, and `systemctl status ssh`.
- **No handshake:** make sure the provider's network firewall or security group allows inbound UDP on the WireGuard port. Some ISPs block WireGuard; this release has no obfuscated transport.
- **No DNS:** check `systemctl status wg-quick@wg0 unbound` on the server. Unbound listens on the VPN address and starts after WireGuard.

## Development

```sh
python -m unittest discover -s tests -v
python scripts/vpnctl.py check
ansible-playbook --syntax-check playbooks/site.yml
```

These checks don't replace a real install. For networking changes, run [docs/VERIFY.md](docs/VERIFY.md) on a real VPS and client. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

**Not implemented yet:** per-app split tunneling, a verified kill switch, an obfuscated transport such as AmneziaWG, and Oracle Cloud support.

## License

Apache-2.0. WireGuard and other installed packages keep their own licenses.
