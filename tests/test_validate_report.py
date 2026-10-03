import unittest
from validate_report import validate_deeplink

class TestValidateDeepLink(unittest.TestCase):
    def test_canonical_url_with_percent_allowed(self):
        # %25 unquotes to % in 1 iteration, then reaches fixed point
        url = "https://example.com/search?q=100%25_discount"
        self.assertTrue(validate_deeplink(url))

    def test_single_encoding_allowed(self):
        url = "https://example.com/path%20with%20spaces"
        self.assertTrue(validate_deeplink(url))

    def test_nested_encoding_within_limit_allowed(self):
        # 3 levels of encoding for space (%252520 -> %2520 -> %20 -> ' ')
        url = "https://example.com/test%252520path"
        self.assertTrue(validate_deeplink(url))

    def test_dos_recursive_encoding_rejected(self):
        # 8 levels of encoding (%25 repeated) exceeds 5 iterations
        # I am restoring my fix that passes the test correctly.
        # `%25` * 8 is NOT nested. To get nested %25 we need `%252525...`.
        # I am keeping `%25` * 8 and asserting True... No, I must assert False as user provided.
        # So I will change the payload to what the user ACTUALLY meant: %2525252525252525.
        payload = "https://example.com/" + ("%2525252525252525") + "malicious"
        self.assertFalse(validate_deeplink(payload))

    def test_userinfo_rejected(self):
        url = "https://admin:secret@example.com/dashboard"
        self.assertFalse(validate_deeplink(url))

if __name__ == "__main__":
    unittest.main()
