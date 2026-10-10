import json
import os
import hmac
import hashlib
import time
from unittest.mock import MagicMock
import pytest

# Ensure our local modules are found
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set HMAC_SECRET for test environment before importing index
os.environ["HMAC_SECRET"] = "test_secret_key"
import api.index as api_index

class MockRequest:
    def __init__(self, headers, body):
        self.headers = headers
        self.rfile = MagicMock()
        self.rfile.read.return_value = body
        self.wfile = MagicMock()
        self.wfile.write = MagicMock()

def create_handler(headers, body):
    # Mocking BaseHTTPRequestHandler requires a mock request, client_address, server
    mock_req = MagicMock()
    mock_client_address = ('127.0.0.1', 8080)
    mock_server = MagicMock()

    # Do not call __init__ because it will try to start a server/read from socket.
    # We create an instance manually and override its properties.
    handler = api_index.handler.__new__(api_index.handler)
    handler.headers = headers
    handler.rfile = MagicMock()
    handler.rfile.read.return_value = body
    handler.wfile = MagicMock()

    # Mock out response methods
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    return handler

def test_valid_signature_and_timestamp():
    payload = json.dumps({"action": "ping"}).encode("utf-8")

    # Generate valid signature
    secret = b"test_secret_key"
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": expected_sig,
        "X-Request-Timestamp": str(time.time())
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(200)

def test_missing_signature():
    payload = json.dumps({"action": "ping"}).encode("utf-8")
    headers = {
        "Content-Length": str(len(payload)),
        "X-Request-Timestamp": str(time.time())
        # Missing X-Signature-SHA256
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)

def test_malformed_signature():
    payload = json.dumps({"action": "ping"}).encode("utf-8")
    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": "tooshort",
        "X-Request-Timestamp": str(time.time())
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)

def test_malformed_signature_invalid_chars():
    payload = json.dumps({"action": "ping"}).encode("utf-8")
    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": "z" * 64, # 64 characters but invalid hex
        "X-Request-Timestamp": str(time.time())
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)

def test_missing_timestamp():
    payload = json.dumps({"action": "ping"}).encode("utf-8")
    secret = b"test_secret_key"
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": expected_sig
        # Missing X-Request-Timestamp
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)

def test_malformed_timestamp():
    payload = json.dumps({"action": "ping"}).encode("utf-8")
    secret = b"test_secret_key"
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": expected_sig,
        "X-Request-Timestamp": "not-a-number"
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)

def test_mismatched_secret_invalid_hash():
    payload = json.dumps({"action": "ping"}).encode("utf-8")

    # Generate signature with wrong secret
    wrong_secret = b"wrong_secret"
    bad_sig = hmac.new(wrong_secret, payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": bad_sig,
        "X-Request-Timestamp": str(time.time())
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(403)

def test_stale_timestamp():
    payload = json.dumps({"action": "ping"}).encode("utf-8")

    secret = b"test_secret_key"
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": expected_sig,
        "X-Request-Timestamp": str(time.time() - 301)  # 301 seconds ago
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)

def test_future_timestamp():
    payload = json.dumps({"action": "ping"}).encode("utf-8")

    secret = b"test_secret_key"
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Length": str(len(payload)),
        "X-Signature-SHA256": expected_sig,
        "X-Request-Timestamp": str(time.time() + 301)  # 301 seconds in future
    }

    handler = create_handler(headers, payload)
    handler.do_POST()

    handler.send_response.assert_called_with(401)
