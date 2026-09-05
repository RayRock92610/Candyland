import unittest
from unittest.mock import MagicMock
from pathlib import Path
from kessel import Kessel


class TestKessel(unittest.TestCase):
    def setUp(self):
        self.kessel = Kessel("TEST")

    def test_is_truth_valid_content(self):
        response = MagicMock()
        response.text = "[git]\n\tautocrlf = input\n"
        self.assertTrue(self.kessel.is_truth(response))

    def test_is_truth_doctype_html(self):
        response = MagicMock()
        response.text = "<!DOCTYPE html><html><body>404 Not Found</body></html>"
        self.assertFalse(self.kessel.is_truth(response))

    def test_is_truth_html_tag(self):
        response = MagicMock()
        response.text = "<html><body>Error</body></html>"
        self.assertFalse(self.kessel.is_truth(response))

    def test_is_truth_body_tag(self):
        response = MagicMock()
        response.text = "<body>Page missing</body>"
        self.assertFalse(self.kessel.is_truth(response))

    def test_is_truth_empty_or_whitespace(self):
        response = MagicMock()
        response.text = "   \n\t  "
        self.assertFalse(self.kessel.is_truth(response))

    def test_kessel_initialization(self):
        kessel = Kessel("CUSTOM")
        self.assertEqual(kessel.db_path, Path("kessel_CUSTOM.db"))
        self.assertIn("/.git/config", kessel.paths)


if __name__ == "__main__":
    unittest.main()
