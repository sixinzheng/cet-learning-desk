import socket
import unittest

import desktop_backend


class DesktopBackendTests(unittest.TestCase):
    def test_default_port_is_stable_for_webview_storage(self):
        args = desktop_backend._parse_args([])
        self.assertEqual(args.port, desktop_backend.DEFAULT_DESKTOP_PORT)
        self.assertGreater(args.port, 0)

    def test_explicit_random_port_remains_available_for_diagnostics(self):
        args = desktop_backend._parse_args(['--port', '0'])
        self.assertEqual(args.port, 0)
        port = desktop_backend._free_port()
        self.assertGreater(port, 0)

    def test_wait_for_port_release_accepts_a_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        desktop_backend._wait_for_port_release(port, timeout=0.1)


if __name__ == '__main__':
    unittest.main()
