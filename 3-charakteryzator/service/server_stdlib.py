"""The same /characterize endpoint without any dependencies (standard library only), for local testing.
Run:  python3 service/server_stdlib.py            -> http://localhost:8001/characterize
"""
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract import characterize_spec, RequestError

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, allow_nan=False).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b)))
        self.send_header('Access-Control-Allow-Origin', '*'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._send(200, {'status': 'ok'}) if self.path == '/health' else self._send(404, {'detail': 'not found'})
    def do_POST(self):
        if self.path != '/characterize': return self._send(404, {'detail': 'not found'})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            self._send(200, characterize_spec(req))
        except RequestError as e: self._send(e.status, {'detail': str(e)})
        except json.JSONDecodeError: self._send(400, {'detail': 'body is not valid JSON'})
    def log_message(self, *a): pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    print(f'Charakteryzator on http://0.0.0.0:{port}/characterize'); ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()
