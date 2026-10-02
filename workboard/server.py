#!/usr/bin/env python3
"""Serve one project's samepage Workboard on loopback only."""

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from board_data import collect
from common import project_paths
from requests_store import RequestStore

STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/board.js": ("board.js", "text/javascript; charset=utf-8"),
          "/board.css": ("board.css", "text/css; charset=utf-8")}


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, brain, ui, store, token, **kwargs):
        self.brain, self.ui, self.store, self.token = brain, Path(ui), store, token
        super().__init__(*args, **kwargs)

    def local_host(self):
        return self.headers.get("Host") in (
            "127.0.0.1:" + str(self.server.server_port),
            "localhost:" + str(self.server.server_port),
        )

    def send_bytes(self, status, data, mime="application/json; charset=utf-8", head=False):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        if not head:
            self.wfile.write(data)

    def respond(self, status, payload, head=False):
        self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), head=head)

    def read(self, head=False):
        if not self.local_host():
            self.respond(403, {"error": "Local Workboard only"}, head)
            return
        route = urlsplit(self.path).path
        if route == "/favicon.ico":
            self.send_bytes(204, b"", head=head)
            return
        if route == "/api/workboard":
            try:
                board = collect(self.brain)
                board["requests"] = [entry for entry in self.store.read() if entry["status"] != "done"]
                board["csrf_token"] = self.token
                board["delivery"] = {"available": False,
                                     "message": "Replies are saved in samepage. An agent must pick them up."}
            except (OSError, UnicodeError, ValueError):
                self.respond(503, {"error": "Samepage reports are unavailable"}, head)
                return
            self.respond(200, board, head)
            return
        asset = STATIC.get(route)
        if asset is None:
            self.respond(404, {"error": "No page here"}, head)
            return
        path = self.ui / asset[0]
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self.ui.resolve():
            self.respond(404, {"error": "No page here"}, head)
            return
        try:
            self.send_bytes(200, path.read_bytes(), asset[1], head)
        except OSError:
            self.respond(503, {"error": "Workboard asset unavailable"}, head)

    def do_GET(self):
        self.read()

    def do_HEAD(self):
        self.read(head=True)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/requests":
            self.respond(404, {"error": "No action here"})
            return
        host = self.headers.get("Host", "")
        if (not self.local_host() or self.headers.get("Origin") != "http://" + host
                or not secrets.compare_digest(self.headers.get("X-Workboard-Token", ""), self.token)):
            self.respond(403, {"error": "Refresh Workboard, then try again. Your text has been kept."})
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
                raise ValueError("Instruction needs one bounded length")
            length = int(lengths[0])
            if not 0 < length <= 20_000:
                raise ValueError("Instruction is too large or incomplete")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise ValueError("Send a JSON instruction")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self.respond(200, self.store.create(payload))
        except (ValueError, TypeError, UnicodeDecodeError) as error:
            self.respond(400, {"error": str(error)})
        except (OSError, RuntimeError, TimeoutError):
            self.respond(503, {"error": "Could not confirm the save. Retry with the same instruction."})

    def log_message(self, format, *args):
        if len(args) > 1 and str(args[1]) in ("200", "204"):
            return
        super().log_message(format, *args)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".")
    parser.add_argument("--port", type=int, default=3113)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    cwd, brain = project_paths(args.project)
    if not brain.is_dir():
        parser.error("Run samepage init for this project first")
    store = RequestStore(brain, cwd)
    handler = partial(Handler, brain=brain, ui=Path(__file__).parent, store=store,
                      token=secrets.token_urlsafe(32))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server.daemon_threads = True
    print("Workboard: http://127.0.0.1:" + str(server.server_port) + "/", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
