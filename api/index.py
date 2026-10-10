from http.server import BaseHTTPRequestHandler
import json
import hmac
import hashlib
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import kessel

# ⚡ Bolt Optimization: Pre-encode HMAC secret bytes at module load
# to avoid string allocation and decoding overhead on every inbound POST request.
_HMAC_SECRET_BYTES = os.getenv("KESSEL_HMAC_SECRET", "").encode("utf-8")

def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
    if not _HMAC_SECRET_BYTES or not signature_header:
        return False
    expected_signature = hmac.new(_HMAC_SECRET_BYTES, payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        api_key_set = os.getenv("KESSEL_API_KEY") is not None

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "online",
            "system": "kesselflow",
            "file": str(Path(kessel.__file__).name),
            "env_configured": api_key_set,
            "auth_type": "HMAC-SHA256"
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return

    def do_POST(self):
        # Read exact raw payload bytes before parsing JSON
        content_length = int(self.headers.get('Content-Length', 0))
        post_bytes = self.rfile.read(content_length) if content_length > 0 else b''
        
        # Extract client signature and timestamp headers
        provided_sig = self.headers.get("X-Signature-SHA256", "").strip()
        provided_ts = self.headers.get("X-Request-Timestamp", "").strip()
        
        if not provided_sig:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "unauthorized",
                "message": "Missing HMAC SHA256 signature"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        # SHA256 hex digest should be exactly 64 characters
        if len(provided_sig) != 64 or not all(c in '0123456789abcdefABCDEF' for c in provided_sig):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "unauthorized",
                "message": "Malformed HMAC SHA256 signature"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        if not provided_ts:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "unauthorized",
                "message": "Missing X-Request-Timestamp"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        # Validate timestamp drift
        try:
            req_ts = float(provided_ts)
            current_ts = time.time()
            if abs(current_ts - req_ts) > 300:
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "status": "unauthorized",
                    "message": "Request timestamp stale"
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
        except ValueError:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "unauthorized",
                "message": "Malformed X-Request-Timestamp"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        # Timing-safe signature comparison
        if not verify_signature(post_bytes, provided_sig.lower()):
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "forbidden",
                "message": "Invalid HMAC SHA256 signature"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        try:
            # ⚡ Bolt Optimization: Avoid unnecessary string decoding overhead.
            # json.loads natively supports byte arrays and decodes them to UTF-8 much faster than manual decoding.
            payload = json.loads(post_bytes) if post_bytes else {}
            action = payload.get("action", "default")

            if hasattr(kessel, action) and callable(getattr(kessel, action)):
                func = getattr(kessel, action)
                result = func(payload)
            else:
                result = f"Action '{action}' processed via kessel engine"

            response = {
                "status": "success",
                "action": action,
                "result": result,
                "authenticated": True
            }
            status_code = 200
            
        except json.JSONDecodeError:
            response = {"status": "error", "message": "Invalid JSON payload"}
            status_code = 400
        except Exception as e:
            response = {"status": "error", "message": str(e)}
            status_code = 500

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return
