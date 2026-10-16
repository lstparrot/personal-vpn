# Verification checklist

Run this on a new VPS and on each client device. Create a test device with `vpnctl.py add`. When you share results, leave out IP addresses, keys and screenshots of profiles.

## Server

1. Keep the original SSH session open and log in again in a **second** session with your key.
2. On the VPS, check that `wg-quick@wg0`, `unbound` and `nftables` are active and that the WireGuard UDP port is listening. From outside, confirm that port 53 is closed on the public address.
3. Reboot the VPS from the provider console. Check SSH and the services again.
4. Run `python scripts/vpnctl.py deploy` again. The server key must not change and access must keep working.
5. Revoke the test device. Confirm it can no longer complete a handshake.

## Client (full tunnel)

1. Before you connect, note your public IPv4 and check that a normal website opens.
2. Connect. Your public IPv4 must now be the VPS address. Check the apps and sites you need, one by one.
3. Run DNS and IPv6 leak tests on the same device. The server has no IPv6 exit, so your local IPv6 address must not appear while you're connected. IPv6-only sites may not load.
4. Block UDP to the VPS, then stop the WireGuard client. Write down what apps and DNS actually do. Without this test, don't treat the full tunnel as a kill switch.
5. Repeat after switching Wi-Fi networks and after rebooting the OS. After you disconnect on purpose, your normal address must come back.

## Billing and IP reputation

Set a traffic usage alert in the provider panel well below your plan's limit, and check the overage price. During any trial period, test the services you care about from this specific IP: a US geolocation alone doesn't mean every service will accept the address.
