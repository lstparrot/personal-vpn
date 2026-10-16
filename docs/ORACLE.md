# Oracle Cloud Always Free

Checked against Oracle documentation on 7 October 2026.

**The playbook does not support standard OCI images yet.** It replaces the host firewall, and OCI requires keeping the rules that allow iSCSI traffic to `169.254.0.2:3260` and `169.254.2.0/24:3260` for the boot volume. The playbook detects these rules and stops before changing anything. Don't try to bypass that check. The notes below are for when OCI support is added.

## Shape

- Free option: one `VM.Standard.A1.Flex` with **1 OCPU and 4 GB RAM**, Ubuntu 24.04 LTS (aarch64), a 50 GB boot volume and a public IPv4. Check that both the image and the shape are marked **Always Free Eligible**. The Always Free limit for all A1 instances on an account is 2 OCPU and 12 GB RAM in total.
- Fallback if A1 has no capacity: `VM.Standard.E2.1.Micro` with Ubuntu 24.04. It has 1 GB RAM and public bandwidth capped at 50 Mbps, so measure speed and stability first.
- Always Free includes **10 TB of outbound traffic per month**. That is an egress allowance, not a promise of speed or IP quality.

## Account

1. Sign up at [signup.oraclecloud.com](https://signup.oraclecloud.com/) with real details, and confirm your email and phone.
2. Pick a US region, such as **US East (Ashburn)**, as the Home Region. You can't change the Home Region later, and Always Free VMs can only be created there.
3. Add a card for identity verification. Virtual, single-use and prepaid cards are rejected. Adding a card doesn't upgrade you to a paid account.
4. Don't upgrade the account, and don't create resources without the Always Free Eligible mark. Free resources remain after the 30-day trial ends; paid trial resources are deleted.

## VM

1. Create a compartment. Under **Networking → Virtual Cloud Networks → Start VCN Wizard → Create VCN with Internet Connectivity**, create a VCN with a public subnet.
2. Under **Compute → Instances → Create Instance**, choose Ubuntu 24.04, `VM.Standard.A1.Flex`, 1 OCPU, 4 GB RAM and a 50 GB boot volume.
3. Put the instance in the public subnet, enable **Assign a public IPv4 address**, and add your SSH **public** key.
4. In the subnet's Security List, add a stateful ingress rule for `UDP` port `51820` from `0.0.0.0/0`. Keep `TCP 22` for SSH, limited to your own IP if you can. Don't open port 53.
5. Check that `ssh ubuntu@<public-ip>` and `sudo -n true` both work, and that the serial console is available.

If creating an A1 instance fails with **Out of host capacity**, try another availability domain or try again later. Oracle may reclaim idle Always Free VMs, so keep your `secrets/` and `state/` backed up.

## Sources

- [Free Tier sign-up](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm)
- [Always Free resources and limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Creating your first Linux instance](https://docs.oracle.com/en-us/iaas/Content/Compute/tutorials/first-linux-instance/overview.htm)
- [Required boot-volume firewall rules](https://docs.oracle.com/en-us/iaas/Content/Compute/References/images.htm)
- [Security lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/creating-securitylist.htm)
