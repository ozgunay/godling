"""A Clawblox world over HTTP, as far as the mind's client and the guest panel see one (tests only)."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DualStackServer(ThreadingHTTPServer):
    """Listens on IPv6 and IPv4 at once: run_godling talks to "localhost", which Windows tries as ::1 first."""
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


class FakeWorldServer:
    """A Clawblox world over HTTP, as far as the mind's client sees one: canned replies, and every request kept."""

    def __init__(self):
        self.requests = []
        self.replies = {}  # (method, path without query) -> reply body (dict) or a callable(request) -> dict
        self.status = {}
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _serve(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                path, _, query = self.path.partition("?")
                request = {"method": method, "path": path, "query": query, "headers": dict(self.headers),
                           "body": json.loads(body) if body else None}
                server.requests.append(request)
                reply = server.replies.get((method, path))
                if callable(reply):
                    reply = reply(request)
                status = server.status.get((method, path), 200 if reply is not None else 404)
                data = b"" if reply is None else (reply if isinstance(reply, bytes) else json.dumps(reply).encode())
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._serve("GET")

            def do_POST(self):
                self._serve("POST")

        try:
            self.httpd = DualStackServer(("::", 0), Handler)
        except OSError:  # no IPv6 on this machine: IPv4 is all "localhost" can mean
            self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
