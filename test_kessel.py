import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import requests
from kessel import Kessel


class TestKessel(unittest.TestCase):
    def setUp(self):
        self.kessel = Kessel("TEST")

    def test_is_truth_valid_content(self):
        response = MagicMock()
        response.content = b"[git]\n\tautocrlf = input\n"
        self.assertTrue(self.kessel.is_truth(response))

    def test_is_truth_doctype_html(self):
        response = MagicMock()
        response.content = b"<!DOCTYPE html><html><body>404 Not Found</body></html>"
        self.assertFalse(self.kessel.is_truth(response))

    def test_is_truth_html_tag(self):
        response = MagicMock()
        response.content = b"<html><body>Error</body></html>"
        self.assertFalse(self.kessel.is_truth(response))

    def test_is_truth_body_tag(self):
        response = MagicMock()
        response.content = b"<body>Page missing</body>"
        self.assertFalse(self.kessel.is_truth(response))

    def test_is_truth_empty_or_whitespace(self):
        response = MagicMock()
        response.content = b"   \n\t  "
        self.assertFalse(self.kessel.is_truth(response))

    def test_kessel_initialization(self):
        kessel = Kessel("CUSTOM")
        self.assertEqual(kessel.db_path, Path("kessel_CUSTOM.db"))
        self.assertIn("/.git/config", kessel.paths)

    @patch('requests.Session.request')
    def test_audit_node_connect_timeout(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectTimeout("Timeout")
        result = self.kessel.audit_node("example.com")
        self.assertEqual(result, [])

    @patch('requests.Session.request')
    def test_audit_node_connection_error(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection Error")
        result = self.kessel.audit_node("example.com")
        self.assertEqual(result, [])

    @patch('requests.Session.request')
    def test_audit_node_request_exception(self, mock_request):
        mock_request.side_effect = requests.exceptions.RequestException("Request Exception")
        result = self.kessel.audit_node("example.com")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
