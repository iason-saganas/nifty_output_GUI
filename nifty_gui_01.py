#!/usr/bin/env python3
"""nifty_gui — mirror NIFTy terminal output live to a web page.

Stdlib only. Two ways to feed it:

  # 1. Run mode (recommended): nifty_gui starts your script and captures everything
  python nifty_gui.py -- python my_inference.py --some-arg

  # 2. Pipe mode: note -u (unbuffered) and 2>&1 (NIFTy logs go to stderr)
  python -u my_inference.py 2>&1 | python nifty_gui.py

Then open http://localhost:8000. Output is still echoed to the terminal.
Over SSH:  ssh -L 8000:localhost:8000 user@cluster
"""
import argparse
import errno
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
PAGE_PATH = Path(__file__).with_name("nifty_gui_01.html")

# --------------------------------------------------------------------------- #
# Line store: every captured line, kept in memory so late/refreshing clients
# get the full history.
# --------------------------------------------------------------------------- #
class LineStore:
    def __init__(self):
        self.lines = []
        self.done = False
        self.cond = threading.Condition()

    def append(self, line):
        with self.cond:
            self.lines.append(line)
            self.cond.notify_all()

    def finish(self):
        with self.cond:
            self.done = True
            self.cond.notify_all()

    def wait_from(self, i, timeout=15.0):
        """Return (lines[i:], done), blocking until there is something new."""
        with self.cond:
            if i >= len(self.lines) and not self.done:
                self.cond.wait(timeout)
            return self.lines[i:], self.done


STORE = LineStore()


def pump(stream):
    """Read raw bytes line by line, echo them to the terminal, store them."""
    out = sys.stdout.buffer
    for raw in iter(stream.readline, b""):
        out.write(raw)
        out.flush()
        STORE.append(raw.decode("utf-8", errors="replace").rstrip("\r\n"))


# --------------------------------------------------------------------------- #
# HTTP: "/" serves the page, "/stream" is a Server-Sent-Events feed of lines.
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal clean
        pass

    def do_GET(self):
        path = urlsplit(self.path).path  # ignore ?n=... (read by the page itself)
        if path in ("/", "/index.html"):
            body = PAGE_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/stream":
            self.stream()
        else:
            self.send_error(404)

    def stream(self):
        # On automatic reconnect, the browser tells us the last line it got.
        try:
            i = int(self.headers.get("Last-Event-ID", -1)) + 1
        except ValueError:
            i = 0
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                new, done = STORE.wait_from(i)
                parts = [f"id: {i + k}\ndata: {json.dumps(line)}\n\n"
                         for k, line in enumerate(new)]
                i += len(new)
                if done:
                    parts.append("event: done\ndata: {}\n\n")
                elif not new:
                    parts.append(": keepalive\n\n")
                self.wfile.write("".join(parts).encode("utf-8"))
                self.wfile.flush()
                if done:
                    return
        except (BrokenPipeError, ConnectionResetError):
            return  # tab closed


# --------------------------------------------------------------------------- #
# The page. Deliberately minimal for now: a live terminal mirror.
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description="Mirror NIFTy terminal output to a live web page.",
        usage="%(prog)s [options] [-- command ...]   (or pipe into stdin)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (default: localhost only)")
    ap.add_argument("--open", action="store_true", help="open a browser tab")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="command to run, after --")
    args = ap.parse_args()
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command

    # If the port is taken (e.g. a second GUI is running), try the next ones.
    for port in range(args.port, args.port + 100):
        try:
            server = ThreadingHTTPServer((args.host, port), Handler)
            break
        except OSError as e:
            if e.errno != errno.EADDRINUSE:
                raise
    else:
        sys.exit(f"[nifty_gui] no free port in {args.port}-{args.port + 99}")
    if port != args.port:
        print(f"[nifty_gui] port {args.port} in use, using {port} instead",
              file=sys.stderr, flush=True)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{port}"
    print(f"[nifty_gui] serving on {url}", file=sys.stderr, flush=True)
    if args.open:
        webbrowser.open(url)

    try:
        if cmd:
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=env)
            pump(proc.stdout)
            rc = proc.wait()
            STORE.append(f"[nifty_gui] process exited with code {rc}")
        else:
            if sys.stdin.isatty():
                print("[nifty_gui] waiting for piped input "
                      "(or pass a command after --)", file=sys.stderr)
            pump(sys.stdin.buffer)
        STORE.finish()
        print(f"[nifty_gui] input finished; page still at {url} — Ctrl-C to quit",
              file=sys.stderr, flush=True)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()