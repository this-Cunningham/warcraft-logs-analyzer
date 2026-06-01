"""Minimal static file server for previewing generated HTML reports.

Cross-platform replacement for preview-server.ps1 - stdlib only.

    python .claude/preview-server.py [--port 8753] [--root reports] [--default <file.html>]
"""

import argparse
import functools
import http.server
import os
import socketserver


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

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("localhost", args.port), Handler) as httpd:
        print("Serving {} on http://localhost:{}/".format(root_full, args.port))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
