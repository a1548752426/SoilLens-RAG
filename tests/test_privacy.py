import unittest

from starlette.requests import Request

from app.main import is_local_request


def build_request(client_host: str, hostname: str) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/assessment/samples",
        "raw_path": b"/api/assessment/samples",
        "query_string": b"",
        "headers": [(b"host", hostname.encode("ascii"))],
        "client": (client_host, 12345),
        "server": ("127.0.0.1", 8000),
    }
    return Request(scope)


class PrivacyTests(unittest.TestCase):
    def test_local_browser_can_read_private_samples(self):
        self.assertTrue(is_local_request(build_request("127.0.0.1", "127.0.0.1")))
        self.assertTrue(is_local_request(build_request("::1", "localhost")))

    def test_external_client_is_blocked(self):
        self.assertFalse(is_local_request(build_request("203.0.113.10", "example.com")))

    def test_public_reverse_proxy_host_is_blocked(self):
        self.assertFalse(is_local_request(build_request("127.0.0.1", "example.com")))


if __name__ == "__main__":
    unittest.main()
