from http.server import BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

# Add root directory to sys.path for kessel.py resolution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import kessel

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "kesselflow online",
            "service": "candyland",
            "kessel_file": str(Path(kessel.__file__).name)
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
            
            # Map incoming payload to your kessel.py execution logic here
            response = {
                "status": "success",
                "received_payload": payload,
                "engine": "kessel.py"
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
