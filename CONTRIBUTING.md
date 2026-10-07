# Contributing

Changes should keep a fresh Ubuntu Server installation reproducible and preserve access to the server during firewall or SSH updates.

1. Open an issue describing the behavior and the affected platform.
2. Keep client credentials, real server addresses, tokens, and SSH keys out of commits, issue text, screenshots, and test fixtures.
3. Run the checks in `README.md`. For networking changes, describe a real-device test that would detect a traffic leak or failed revocation.
4. Update the support and limitation sections when behavior changes. Do not claim a strict kill switch from a route-only test.

Security reports belong in the private channel described in `SECURITY.md`.
