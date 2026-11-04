"""Tiny dev server: serves ebilal_web/ and proxies /api/* to the backend on :8000,
mirroring what nginx does on the Pi.   python other/devserver.py [port]"""
import http.server, os, sys, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ebilal_web")
API = "http://127.0.0.1:8000"


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def _proxy(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) or None
        req = urllib.request.Request(API + self.path[4:], data=body, method=self.command,
                                     headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
        try:
            r = urllib.request.urlopen(req, timeout=15)
            code, data, ctype = r.status, r.read(), r.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            code, data, ctype = e.code, e.read(), "application/json"
        except Exception as e:
            code, data, ctype = 502, str(e).encode(), "text/plain"
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        return self._proxy() if self.path.startswith("/api/") else super().do_GET()

    def do_POST(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(405)


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8080), H).serve_forever()
