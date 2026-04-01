"""Reverse proxy for Prometheus — serves on port 8080, forwards to Prometheus on 9090."""

import subprocess
import threading
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

PROM_PORT = 9090
LISTEN_PORT = int(os.environ.get("PORT", 8080))
PROM_URL = f"http://127.0.0.1:{PROM_PORT}"
prom_ready = False


def start_prometheus():
    global prom_ready
    version = os.environ.get("PROM_VERSION", "3.3.0")
    tarball = f"prometheus-{version}.linux-amd64"
    url = f"https://github.com/prometheus/prometheus/releases/download/v{version}/{tarball}.tar.gz"

    dest = f"/tmp/{tarball}.tar.gz"
    print(f"Downloading Prometheus v{version}...", flush=True)
    subprocess.run(
        ["curl", "-fSL", "--retry", "3", "--connect-timeout", "30",
         "-o", dest, url],
        check=True,
    )
    print(f"Download complete, extracting...", flush=True)
    import tarfile
    with tarfile.open(dest, mode="r:gz") as tar:
        tar.extractall(path="/tmp")
    os.remove(dest)
    print("Extraction complete", flush=True)

    print(f"Starting Prometheus on :{PROM_PORT}...", flush=True)
    subprocess.Popen([
        f"/tmp/{tarball}/prometheus",
        "--config.file=/output/prometheus.yml",
        f"--web.listen-address=0.0.0.0:{PROM_PORT}",
        "--web.enable-otlp-receiver",
        "--storage.tsdb.path=/tmp/prometheus-data",
    ])

    for _ in range(60):
        try:
            urlopen(f"{PROM_URL}/-/ready")
            prom_ready = True
            print("Prometheus ready!", flush=True)
            return
        except Exception:
            time.sleep(1)
    print("Warning: Prometheus may not be ready", flush=True)


class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not prom_ready and self.path in ("/", "/health", "/-/ready"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Starting...")
            return
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

    def do_PUT(self):
        self._proxy("PUT")

    def do_DELETE(self):
        self._proxy("DELETE")

    def do_HEAD(self):
        self._proxy("HEAD")

    def do_OPTIONS(self):
        self._proxy("OPTIONS")

    def _proxy(self, method):
        if not prom_ready:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Prometheus starting...")
            return

        target = f"{PROM_URL}{self.path}"
        body = None
        if method in ("POST", "PUT"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None

        headers = {}
        for key in ("Content-Type", "Accept", "Accept-Encoding"):
            val = self.headers.get(key)
            if val:
                headers[key] = val

        try:
            req = Request(target, data=body, headers=headers, method=method)
            with urlopen(req) as resp:
                self._send_proxy_response(resp)
        except HTTPError as e:
            # Forward the actual error response from Prometheus
            self._send_proxy_response(e)
        except URLError as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Prometheus unavailable: {e}".encode())

    def _send_proxy_response(self, resp):
        resp_body = resp.read()
        status = resp.status if hasattr(resp, "status") else resp.code
        self.send_response(status)
        for key, val in resp.getheaders():
            if key.lower() not in ("transfer-encoding", "connection",
                                   "content-encoding", "content-length"):
                self.send_header(key, val)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    # Start Prometheus download in background thread
    threading.Thread(target=start_prometheus, daemon=True).start()

    # Start proxy immediately so health check passes
    print(f"Proxy listening on :{LISTEN_PORT}", flush=True)
    server = HTTPServer(("0.0.0.0", LISTEN_PORT), ProxyHandler)
    server.serve_forever()
