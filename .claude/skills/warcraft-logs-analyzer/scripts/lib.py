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
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

TOKEN_URI = "https://www.warcraftlogs.com/oauth/token"
API_URI = "https://www.warcraftlogs.com/api/v2/client"

# The fetch stage is almost entirely network wait (one blocking POST per query), so the pipeline runs
# its independent queries concurrently (see parallel_map). Two module-level guards keep that safe and
# polite without changing any response:
#   * _REQUEST_SEMA caps how many POSTs are ever in flight at once — protects the WCL API's rate limit
#     and keeps us a good citizen no matter how many nested pools are running. Override via env.
#   * _TOKEN_LOCK serializes the (rare) token refetch so concurrent first-callers don't stampede the
#     OAuth endpoint and clobber the cache file.
_MAX_CONCURRENCY = max(1, int(os.environ.get("WCL_MAX_CONCURRENCY", "5")))
_REQUEST_SEMA = threading.BoundedSemaphore(_MAX_CONCURRENCY)
_TOKEN_LOCK = threading.Lock()

# Every HTTP call gets a hard timeout. Without one, urllib blocks forever, so a single connection the
# server holds open under load (a soft rate-limit) would hang the whole pipeline indefinitely. A timed-
# out request is treated as transient and retried with backoff (see invoke_query).
_REQUEST_TIMEOUT = float(os.environ.get("WCL_REQUEST_TIMEOUT", "45"))


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


def _read_cached_token(cache_file):
    """Return a still-valid cached access token, or None. Refreshes a day early to be safe."""
    if not os.path.isfile(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8-sig") as fh:
            cached = json.load(fh)
        if cached.get("access_token") and float(cached["expires_at"]) > time.time() + 86400:
            return cached["access_token"]
    except Exception:
        pass  # fall through to refetch on any cache problem
    return None


def get_token(force=False):
    """Fetch a client-credentials bearer token, caching it until ~a day before expiry.

    Thread-safe: the network refetch is serialized under _TOKEN_LOCK and re-checks the cache inside the
    lock, so when many parallel workers find no token only the first hits the OAuth endpoint."""
    cache_file = _token_cache_path()

    if not force:
        tok = _read_cached_token(cache_file)
        if tok:
            return tok

    with _TOKEN_LOCK:
        # Re-check inside the lock: another thread may have refreshed while we waited.
        if not force:
            tok = _read_cached_token(cache_file)
            if tok:
                return tok
        return _refetch_token(cache_file)


def _refetch_token(cache_file):
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
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    expires_at = time.time() + int(payload["expires_in"])
    with open(cache_file, "w", encoding="utf-8") as fh:
        json.dump({"access_token": payload["access_token"], "expires_at": expires_at}, fh)

    return payload["access_token"]


def invoke_query(query, variables=None, _max_retries=4):
    """POST a GraphQL query to the public v2/client endpoint; return the `data` object.

    Raises RuntimeError on GraphQL errors (mirrors Invoke-WclQuery).

    Concurrency-aware: every POST passes through _REQUEST_SEMA so no more than _MAX_CONCURRENCY are ever
    in flight at once, and transient failures (HTTP 429 rate-limit, 5xx, network blips) are retried with
    exponential backoff. Neither changes a successful response — they just let the parallel fetch run
    safely against the API's rate limit. A 429 honors the server's Retry-After header when present."""
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

    attempt = 0
    while True:
        try:
            with _REQUEST_SEMA:
                with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            # Retry rate-limits (429) and server errors (5xx); anything else is a real failure.
            if exc.code != 429 and exc.code < 500:
                raise
            if attempt >= _max_retries:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if (retry_after and retry_after.isdigit()) else 2 ** attempt
            time.sleep(delay)
            attempt += 1
        except (urllib.error.URLError, TimeoutError):
            # Transient: DNS hiccup, dropped connection, or a request that timed out because the server
            # held it open under load (a soft rate-limit). Back off and retry rather than hang.
            if attempt >= _max_retries:
                raise
            time.sleep(2 ** attempt)
            attempt += 1

    if result.get("errors"):
        raise RuntimeError("GraphQL errors: " + json.dumps(result["errors"], indent=2))
    return result["data"]


def parallel_map(fn, items, workers=None):
    """Run `fn` over `items` concurrently and return results IN INPUT ORDER (like map()).

    The whole fetch stage is I/O-bound — each task just blocks on a WCL POST — so threads give a near-
    linear speedup despite the GIL, while _REQUEST_SEMA still caps total in-flight requests. Order is
    preserved so callers can build deterministic, byte-identical output regardless of completion order.
    The bearer token is fetched once up front so workers don't race on the first call (get_token is
    already thread-safe; this just avoids a thundering herd). Empty input returns [] without a pool."""
    items = list(items)
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]
    get_token()  # warm the cache before fanning out
    with ThreadPoolExecutor(max_workers=workers or min(_MAX_CONCURRENCY, len(items))) as ex:
        return list(ex.map(fn, items))
