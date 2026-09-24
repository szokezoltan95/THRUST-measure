import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("install_host_alias", Path(__file__).with_name("install_host_alias.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HostsTests(unittest.TestCase):
    def test_windows_and_linux_paths(self):
        self.assertEqual(module.system_hosts_path("Linux"), Path("/etc/hosts"))
        self.assertEqual(module.system_hosts_path("Windows").name, "hosts")

    def test_preserves_unrelated_aliases_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            hosts = Path(folder) / "hosts"
            original = b"127.0.0.1 localhost\r\n10.0.0.1 other THRUST.test # office\r\n"
            hosts.write_bytes(original)
            self.assertTrue(module.install_alias(hosts, "192.0.2.1", "thrust.test"))
            expected = b"127.0.0.1 localhost\r\n10.0.0.1\tother  # office\r\n192.0.2.1\tthrust.test  # THRUST\r\n"
            self.assertEqual(hosts.read_bytes(), expected)
            self.assertEqual(Path(folder, "hosts.thrust-backup").read_bytes(), original)
            self.assertFalse(module.install_alias(hosts, "192.0.2.1", "thrust.test"))
            self.assertTrue(module.install_alias(hosts, "192.0.2.2", "thrust.test"))
            self.assertIn(b"192.0.2.2\tthrust.test", hosts.read_bytes())
            self.assertEqual(Path(folder, "hosts.thrust-backup-1").read_bytes(), expected)

    def test_rejects_protocol_port_and_injection(self):
        for value in ("http://example.test", "host.test:8080", "host\nother", "-host"):
            with self.assertRaises(ValueError):
                module.validated_alias(value)
        with self.assertRaises(ValueError):
            module.validated_ip("1.2.3.4 other")


if __name__ == "__main__":
    unittest.main()
