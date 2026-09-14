from http.server import BaseHTTPRequestHandler
import json
import hmac
import hashlib
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import kessel

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
        secret_key = os.getenv("KESSEL_API_KEY", "").encode('utf-8')
        
        # Read exact raw payload bytes before parsing JSON
        content_length = int(self.headers.get('Content-Length', 0))
        post_bytes = self.rfile.read(content_length) if content_length > 0 else b''
        
        # Extract client signature header
        provided_sig = self.headers.get("X-Signature-256", "").strip()
        
        # Compute HMAC SHA256 signature over raw bytes
        computed_sig = hmac.new(secret_key, post_bytes, hashlib.sha256).hexdigest()
        
        # Timing-safe signature comparison
        if not secret_key or not provided_sig or not hmac.compare_digest(provided_sig.lower(), computed_sig.lower()):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "unauthorized",
                "message": "Invalid or missing HMAC SHA256 signature"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        try:
            payload = json.loads(post_bytes.decode('utf-8')) if post_bytes else {}
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
