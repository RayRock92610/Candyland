from http.server import BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

# Add parent directory to path to import kessel.py
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import kessel module
import kessel

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        # Safe execution wrapper for kessel functions
        try:
            # Call functions from kessel.py (e.g. kessel.main() or custom functions)
            response = {
                "status": "kesselflow online",
                "service": "candyland",
                "kessel_file": str(Path(kessel.__file__).name)
            }
        except Exception as e:
            response = {
                "status": "error",
                "message": str(e)
            }

        self.wfile.write(json.dumps(response).encode('utf-8'))
        return
