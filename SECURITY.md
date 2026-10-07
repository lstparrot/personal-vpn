# Security policy

This project configures a VPN gateway and handles client credentials. Do not report vulnerabilities by posting private keys, client profiles, server addresses, or exploit details in a public issue.

If this repository is hosted on GitHub, use its **Private vulnerability reporting** feature. If that feature is not enabled yet, ask the maintainer through a public issue to enable a private reporting channel, without including vulnerability details.

The current server deployment does not provide a verified per-application kill switch. The only supported release claim is the full-tunnel server and profile workflow described in `README.md`. A suspected DNS, IPv6, or direct-route leak should be treated as a security issue and tested on the affected OS before a fix is released.
