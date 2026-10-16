import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import vpnctl


class VpnCtlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        example = vpnctl.PROJECT_ROOT / "config.example.json"
        (self.root / "config.json").write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "peers.json").write_text("[]\n", encoding="utf-8")
        (self.root / "state").mkdir()
        (self.root / "state" / "server.pub").write_text("A" * 43 + "=\n", encoding="ascii")

    def test_add_keeps_private_key_out_of_public_peer_registry(self):
        with patch.object(vpnctl, "generate_keypair", return_value=("private-secret", "B" * 43 + "=")):
            profile_path = vpnctl.add_peer(self.root, "work_mac", deploy_now=False)

        peers = json.loads((self.root / "peers.json").read_text(encoding="utf-8"))
        self.assertEqual(peers[0]["ipv4"], "10.91.0.2")
        self.assertEqual(peers[0]["ipv6"], "fd42:91:0:1::2")
        self.assertNotIn("private-secret", (self.root / "peers.json").read_text(encoding="utf-8"))
        self.assertIn("PrivateKey = private-secret", profile_path.read_text(encoding="utf-8"))
        self.assertEqual(profile_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(profile_path.parent.stat().st_mode & 0o777, 0o700)

    def test_revoke_marks_peer_and_prevents_name_reuse(self):
        with patch.object(vpnctl, "generate_keypair", return_value=("private-secret", "B" * 43 + "=")):
            vpnctl.add_peer(self.root, "work_mac", deploy_now=False)
        vpnctl.revoke_peer(self.root, "work_mac", deploy_now=False)

        peers = json.loads((self.root / "peers.json").read_text(encoding="utf-8"))
        self.assertIs(peers[0]["revoked"], True)
        self.assertTrue((self.root / "secrets" / "peers" / "work_mac.conf").exists())
        with self.assertRaisesRegex(vpnctl.VpnError, "already exists or was revoked"):
            vpnctl.add_peer(self.root, "work_mac", deploy_now=False)

    def test_invalid_endpoint_is_rejected_before_profile_generation(self):
        config_path = self.root / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["endpoint"] = "example.com\nPrivateKey = injected"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        with self.assertRaisesRegex(vpnctl.VpnError, "endpoint"):
            vpnctl.load_config(self.root)

    def test_duplicate_address_is_rejected(self):
        peers = [
            {"name": "one", "public_key": "A" * 43 + "=", "ipv4": "10.91.0.2", "ipv6": "fd42:91:0:1::2"},
            {"name": "two", "public_key": "B" * 43 + "=", "ipv4": "10.91.0.2", "ipv6": "fd42:91:0:1::3"},
        ]
        (self.root / "peers.json").write_text(json.dumps(peers), encoding="utf-8")
        with self.assertRaisesRegex(vpnctl.VpnError, "Duplicate VPN address"):
            vpnctl.load_peers(self.root, vpnctl.load_config(self.root))

    def test_invalid_ssh_port_is_rejected(self):
        config_path = self.root / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["ssh_port"] = 0
        config_path.write_text(json.dumps(config), encoding="utf-8")

        with self.assertRaisesRegex(vpnctl.VpnError, "ssh_port"):
            vpnctl.load_config(self.root)


class InitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        example = vpnctl.PROJECT_ROOT / "config.example.json"
        (self.root / "config.example.json").write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "peers.json").write_text("[]\n", encoding="utf-8")

    def test_init_writes_matching_config_and_inventory(self):
        vpnctl.init_config(self.root, "198.51.100.7", "admin", 2222)

        config = vpnctl.load_config(self.root)
        inventory = (self.root / "inventory" / "hosts.yml").read_text(encoding="utf-8")
        self.assertEqual(config["endpoint"], "198.51.100.7")
        self.assertEqual(config["ssh_port"], 2222)
        self.assertIn("ansible_host: 198.51.100.7\n", inventory)
        self.assertIn("ansible_user: admin\n", inventory)
        self.assertIn("ansible_port: 2222\n", inventory)

    def test_init_refuses_to_overwrite_without_force(self):
        vpnctl.init_config(self.root, "198.51.100.7", "admin")

        with self.assertRaisesRegex(vpnctl.VpnError, "already exists"):
            vpnctl.init_config(self.root, "198.51.100.8", "admin")
        vpnctl.init_config(self.root, "198.51.100.8", "admin", force=True)
        self.assertEqual(vpnctl.load_config(self.root)["endpoint"], "198.51.100.8")

    def test_init_rejects_root_and_unsafe_user(self):
        for user in ("root", "admin\nansible_become: false", "-oProxyCommand"):
            with self.assertRaisesRegex(vpnctl.VpnError, "SSH user"):
                vpnctl.init_config(self.root, "198.51.100.7", user)
        self.assertFalse((self.root / "config.json").exists())

    def test_init_rejects_invalid_endpoint(self):
        with self.assertRaisesRegex(vpnctl.VpnError, "endpoint"):
            vpnctl.init_config(self.root, "bad host", "admin")
        self.assertFalse((self.root / "inventory" / "hosts.yml").exists())


if __name__ == "__main__":
    unittest.main()
