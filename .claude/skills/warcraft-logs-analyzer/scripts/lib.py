"""lib.py - shared helpers for the Warcraft Logs Analyzer skill.

Import this from the sibling scripts (they live in the same folder, which Python
puts on sys.path automatically when you run one of them):

    import lib
    data = lib.invoke_query(query, {"code": "aBcD1234"})

Provides:
    get_config()    -> reads client_id/secret from env vars or repo .env
    get_token()     -> fetches + caches a client-credentials bearer token
    invoke_query()  -> POSTs a GraphQL query to the public v2/client endpoint

Stdlib only (urllib/json/base64) so it runs on macOS' system python3 with nothing
to install.
"""

import base64
import json
import os
import time
import urllib.parse
import urllib.request

TOKEN_URI = "https://www.warcraftlogs.com/oauth/token"
API_URI = "https://www.warcraftlogs.com/api/v2/client"


def find_repo_root(start=None):
    """Walk up from `start` (default cwd) looking for a .git directory."""
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.abspath(start or os.getcwd())
        d = parent


def get_config():
    """Precedence: explicit env vars win, otherwise parse repo-root/.env."""
    cid = os.environ.get("WCL_CLIENT_ID")
    secret = os.environ.get("WCL_CLIENT_SECRET")

    if not cid or not secret:
        env_file = os.path.join(find_repo_root(), ".env")
        if os.path.isfile(env_file):
            with open(env_file, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#"):
                        continue
                    eq = trimmed.find("=")
                    if eq < 1:
                        continue
                    key = trimmed[:eq].strip()
                    val = trimmed[eq + 1:].strip().strip('"').strip("'")
                    if key == "WCL_CLIENT_ID" and not cid:
                        cid = val
                    elif key == "WCL_CLIENT_SECRET" and not secret:
                        secret = val

    if not cid or not secret:
        raise RuntimeError(
            "Missing credentials. Set WCL_CLIENT_ID and WCL_CLIENT_SECRET as env "
            "vars or in a .env file at the repo root (copy .env.example)."
        )
    return {"client_id": cid, "client_secret": secret}


def _token_cache_path():
    return os.path.join(find_repo_root(), ".wcl-token.json")


def get_token(force=False):
    """Fetch a client-credentials bearer token, caching it until ~a day before expiry."""
    cache_file = _token_cache_path()

    if not force and os.path.isfile(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8-sig") as fh:
                cached = json.load(fh)
            # Refresh a day early to be safe. expires_at is a Unix timestamp.
            if cached.get("access_token") and float(cached["expires_at"]) > time.time() + 86400:
                return cached["access_token"]
        except Exception:
            pass  # fall through to refetch on any cache problem

    cfg = get_config()
    pair = "{}:{}".format(cfg["client_id"], cfg["client_secret"])
    basic = base64.b64encode(pair.encode("ascii")).decode("ascii")

    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("ascii")
    req = urllib.request.Request(
        TOKEN_URI,
        data=body,
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    expires_at = time.time() + int(payload["expires_in"])
    with open(cache_file, "w", encoding="utf-8") as fh:
        json.dump({"access_token": payload["access_token"], "expires_at": expires_at}, fh)

    return payload["access_token"]


def invoke_query(query, variables=None):
    """POST a GraphQL query to the public v2/client endpoint; return the `data` object.

    Raises RuntimeError on GraphQL errors (mirrors Invoke-WclQuery).
    """
    token = get_token()
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        API_URI,
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    if result.get("errors"):
        raise RuntimeError("GraphQL errors: " + json.dumps(result["errors"], indent=2))
    return result["data"]
