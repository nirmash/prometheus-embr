"""Reverse proxy for Prometheus — serves on port 8080, forwards to Prometheus on 9090."""

import subprocess
import threading
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

PROM_PORT = 9090
LISTEN_PORT = int(os.environ.get("PORT", 8080))
PROM_URL = f"http://127.0.0.1:{PROM_PORT}"


def start_prometheus():
    version = os.environ.get("PROM_VERSION", "3.3.0")
    tarball = f"prometheus-{version}.linux-amd64"
    url = f"https://github.com/prometheus/prometheus/releases/download/v{version}/{tarball}.tar.gz"

    print(f"Downloading Prometheus v{version}...")
    subprocess.run(f"curl -sL {url} | tar xz -C /tmp", shell=True, check=True)

    print(f"Starting Prometheus on :{PROM_PORT}...")
    return subprocess.Popen([
        f"/tmp/{tarball}/prometheus",
        "--config.file=/output/prometheus.yml",
        f"--web.listen-address=0.0.0.0:{PROM_PORT}",
        "--web.enable-otlp-receiver",
        "--storage.tsdb.path=/tmp/prometheus-data",
    ])


class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

    def do_PUT(self):
        self._proxy("PUT")

    def do_DELETE(self):
        self._proxy("DELETE")

    def _proxy(self, method):
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
                resp_body = resp.read()
                self.send_response(resp.status)
                for key, val in resp.getheaders():
                    if key.lower() not in ("transfer-encoding", "connection",
                                           "content-encoding", "content-length"):
                        self.send_header(key, val)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except URLError as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Prometheus unavailable: {e}".encode())

    def log_message(self, format, *args):
        pass  # suppress request logs


def wait_for_prometheus():
    for _ in range(30):
        try:
            urlopen(f"{PROM_URL}/-/ready")
            return True
        except Exception:
            time.sleep(1)
    return False


if __name__ == "__main__":
    proc = start_prometheus()
    print("Waiting for Prometheus to be ready...")
    if wait_for_prometheus():
        print(f"Prometheus ready. Proxy listening on :{LISTEN_PORT}")
    else:
        print("Warning: Prometheus may not be ready yet")

    server = HTTPServer(("0.0.0.0", LISTEN_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        proc.terminate()
