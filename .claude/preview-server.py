"""Minimal static file server for previewing generated HTML reports.

Cross-platform replacement for preview-server.ps1 - stdlib only.

    python .claude/preview-server.py [--port 8753] [--root reports] [--default <file.html>]
"""

import argparse
import functools
import http.server
import os
import socket
import socketserver


class DualStackServer(socketserver.TCPServer):
    """Listen on IPv6 with IPV6_V6ONLY disabled so the one socket also accepts IPv4.

    Without this the server binds IPv4-only (127.0.0.1), but modern browsers resolve
    `localhost` to IPv6 `::1` first and get ERR_CONNECTION_REFUSED instead of falling back.
    Dual-stack makes http://localhost, http://127.0.0.1, and http://[::1] all reach the
    server. Mirrors what `python -m http.server` does."""

    address_family = socket.AF_INET6
    allow_reuse_address = True

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass  # platform without dual-stack support — falls back to IPv6-only
        super().server_bind()


def main():
    p = argparse.ArgumentParser(description="Static file server for HTML reports.")
    p.add_argument("--port", type=int, default=8753)
    p.add_argument("--root", default="reports")
    p.add_argument("--default", default="ssc-comparison.html",
                   help="file served for the bare '/' path")
    args = p.parse_args()

    root_full = os.path.abspath(args.root)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root_full, **kw)

        def do_GET(self):
            if self.path == "/" or self.path == "":
                self.path = "/" + args.default
            return super().do_GET()

        def log_message(self, fmt, *a):
            pass  # quiet

    # Bind to "" (all interfaces) on a dual-stack socket so both IPv4 and IPv6 loopback work.
    with DualStackServer(("", args.port), Handler) as httpd:
        print("Serving {} on http://localhost:{}/ (dual-stack IPv4+IPv6)".format(root_full, args.port))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
