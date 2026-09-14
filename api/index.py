from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path

# Add root directory to sys.path for kessel.py resolution
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
            "env_configured": api_key_set
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return

    def do_POST(self):
        expected_key = os.getenv("KESSEL_API_KEY", "")
        
        # Extract Authorization header
        auth_header = self.headers.get("Authorization", "")
        provided_token = ""
        
        if auth_header.startswith("Bearer "):
            provided_token = auth_header.split("Bearer ", 1)[1].strip()
            
        # Security Guard: Validate token match
        if not expected_key or provided_token != expected_key:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "unauthorized",
                "message": "Invalid or missing Bearer token"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        # Read and process payload if authenticated
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
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
