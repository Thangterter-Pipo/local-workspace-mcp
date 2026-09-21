"""
Local Workspace MCP server exposing the configured workspace over streamable HTTP.

Design (see README.md):
- Python FastMCP 3.x, transport="http", bound to WORKSPACE_MCP_HOST
  (default 127.0.0.1). Public reach is Cloudflare → VPS → SSH reverse tunnel.
- Bearer API key on /mcp. OAuth DCR is public but redirect_uris are ChatGPT
  allowlisted; /authorize requires the owner PIN (no implicit consent).
- Tools are full-machine (current user ACL). ChatGPT Web Bridge (port 5005)
  is a separate local channel: Pipo → ChatGPT tab; MCP OAuth: ChatGPT → máy.
"""

from __future__ import annotations

import base64
import fnmatch
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.auth.auth import (
    ClientRegistrationOptions,
    OAuthClientInformationFull,
    OAuthProvider,
)

from register_all import register_all_tools
from security import oauth_policy
from services.process_manager import PROCESS_MANAGER
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    OAuthToken,
    RefreshToken,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    """Read the canonical variable, falling back to the legacy FlowVeo name."""
    return os.environ.get(f"WORKSPACE_MCP_{name}") or os.environ.get(f"FLOW_VEO_MCP_{name}") or default


_default_root = str(Path(__file__).resolve().parent)
ROOT = Path(_env("ROOT") or os.environ.get("ALLOWED_ROOTS") or _default_root).resolve()
API_KEY = _env("API_KEY")
HOST = _env("HOST", "127.0.0.1")
PORT = int(_env("PORT", "3080"))

if os.name == "nt":
    RUNTIME_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "LocalWorkspaceMCP"
else:
    RUNTIME_DIR = Path.home() / ".local_workspace_mcp"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_REQUEST_FILE = RUNTIME_DIR / "active_request.json"
_ACTIVE_REQUESTS = 0
_ACTIVE_REQUEST_STARTED_AT: str | None = None

# Public HTTPS base URL. Required for OAuth — the server must be reachable at
# this URL for /authorize, /token, DCR and .well-known discovery to work.
BASE_URL = os.environ.get("PUBLIC_URL") or _env("BASE_URL", "http://127.0.0.1:3080")

# Paths skipped by list_tree (never surfaced, never editable) — keeps the
# knowledge graph focused and avoids handing out huge dirs.
EXCLUDED = {".venv", ".git", "node_modules", "__pycache__", ".pytest_cache"}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".toml",
    ".md", ".mdx", ".txt", ".rst", ".csv", ".html", ".htm", ".css", ".scss",
    ".xml", ".ini", ".cfg", ".conf", ".env", ".sh", ".bat", ".ps1", ".sql",
    ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".ipynb", ".lua",
    ".rb", ".php", ".vue", ".svelte", ".lock", ".log", ".diff", ".patch",
}


# ---------------------------------------------------------------------------
# Request activity + Bearer API-key auth (ASGI middleware)
# ---------------------------------------------------------------------------

def _write_request_activity() -> None:
    """Publish MCP request activity for the external supervisor.

    The MCP server intentionally permits long-running tools. Those tools can
    occupy the asyncio loop, so /health may time out even though a valid tool is
    still running. The supervisor reads this marker and never kills legitimate
    work merely because the HTTP health probe is temporarily blocked.
    """
    try:
        if _ACTIVE_REQUESTS <= 0:
            ACTIVE_REQUEST_FILE.unlink(missing_ok=True)
            return
        payload = {
            "pid": os.getpid(),
            "active_requests": _ACTIVE_REQUESTS,
            "started_at": _ACTIVE_REQUEST_STARTED_AT,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = ACTIVE_REQUEST_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(ACTIVE_REQUEST_FILE)
    except OSError:
        # Activity reporting must never break an MCP request.
        pass


class RequestActivityMiddleware(BaseHTTPMiddleware):
    """Mark in-flight MCP requests so the watchdog preserves long tool calls."""

    async def dispatch(self, request, call_next):
        global _ACTIVE_REQUESTS, _ACTIVE_REQUEST_STARTED_AT

        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        if _ACTIVE_REQUESTS == 0:
            _ACTIVE_REQUEST_STARTED_AT = datetime.now(timezone.utc).isoformat()
        _ACTIVE_REQUESTS += 1
        _write_request_activity()
        try:
            return await call_next(request)
        finally:
            _ACTIVE_REQUESTS = max(0, _ACTIVE_REQUESTS - 1)
            if _ACTIVE_REQUESTS == 0:
                _ACTIVE_REQUEST_STARTED_AT = None
            _write_request_activity()


def _check_auth(request) -> bool:
    """Compare the Authorization header against the configured MCP API key."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return secrets.compare_digest(auth[7:].strip(), API_KEY)
    # Also accept the key directly in the header (some hosts only allow one
    # fixed header name).
    return secrets.compare_digest(auth.strip(), API_KEY)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject every request that does not carry the correct Bearer API key.

    Applied as the outermost middleware so not even the MCP endpoints are
    reachable without the key. The /health endpoint is exempt so tunnel /
    load-balancer probes can check liveness without leaking anything.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        path = request.url.path
        # Public endpoints: health probes, OAuth discovery + authorize page,
        # token endpoint (client auth is handled inside OAuth), DCR register,
        # and the OIDC/well-known metadata. These must be reachable without the
        # static API key so ChatGPT can complete the OAuth flow.
        public_paths = (
            "/health",
            "/healthz",
            "/.well-known/",
            "/authorize",
            "/consent",
            "/token",
            "/register",
            "/revoke",
            "/introspect",
            "/userinfo",
            "/jwks",
            "/.well-known/openid-configuration",
        )
        if path in ("/health", "/healthz") or any(path.startswith(p) for p in public_paths):
            return await call_next(request)
        if not API_KEY:
            # No static API key configured: let FastMCP's OAuth layer handle
            # authorization (it will reject requests without a valid token).
            return await call_next(request)
        if _check_auth(request):
            return await call_next(request)
        # Not the static API key. If the request carries an OAuth access token
        # (from the completed authorization flow), FastMCP's RequireAuthMiddleware
        # will verify it — pass through. Otherwise FastMCP rejects with 401.
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)
        return JSONResponse(
            {"error": "Unauthorized. Provide the API key in the Authorization header as 'Bearer <key>', or complete the OAuth flow to obtain an access token."},
            status_code=401,
        )


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _is_inside(path: Path, root: Path) -> bool:
    """True if `path` is at or under `root`."""
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _validate_relpath(relpath: str, for_write: bool = False) -> Path:
    """Resolve a user-supplied relative path against ROOT, rejecting escapes.

    Raises ValueError with an actionable message for anything unsafe.
    """
    if not relpath or relpath.isspace():
        raise ValueError("path must not be empty.")
    # Normalize to forward slashes, strip leading slash so it stays relative.
    rel = relpath.strip().replace("\\", "/").lstrip("/")
    candidate = (ROOT / rel).resolve()
    if not _is_inside(candidate, ROOT):
        raise ValueError(
            f"Path '{relpath}' escapes the root directory '{ROOT}'. "
            "Use a path relative to the root."
        )
    if for_write and candidate == ROOT:
        raise ValueError("Cannot write to the root directory itself.")
    return candidate


def _suggest(relpath: str) -> str | None:
    """Best-effort suggestion when a path is missing."""
    try:
        parent = _validate_relpath(str(Path(relpath).parent))
    except ValueError:
        return None
    try:
        children = [p.name for p in parent.iterdir() if not p.name.startswith(".")]
    except OSError:
        return None
    for name in sorted(children):
        if name.lower().startswith(Path(relpath).name.lower()):
            return str((parent / name).relative_to(ROOT)).replace("\\", "/")
    return None


def _render_error(err: ValueError) -> dict:
    return {
        "ok": False,
        "error": str(err),
        "root": str(ROOT),
        "hint": "Paths are relative to the root. Use list_tree / list_dir to discover valid paths.",
    }


def _file_entry(path: Path) -> dict:
    rel = path.relative_to(ROOT).as_posix()
    is_dir = path.is_dir()
    return {
        "name": path.name,
        "path": rel,
        "type": "dir" if is_dir else "file",
        "size": 0 if is_dir else path.stat().st_size,
        "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        .isoformat(),
    }


def _read_text_or_binary(path: Path, max_text_chars: int) -> dict:
    """Read a file, returning text for known-text types else base64 blob."""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS or suffix == "":
        try:
            data = path.read_text(encoding="utf-8")
            truncated = len(data) > max_text_chars
            if truncated:
                data = data[:max_text_chars] + f"\n...[truncated {len(data)} -> {max_text_chars} chars]"
            return {"encoding": "utf-8", "content": data, "truncated": truncated}
        except UnicodeDecodeError:
            pass  # fall through to binary
    size = path.stat().st_size
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"encoding": "base64", "content": b64, "truncated": False, "size": size}


# ---------------------------------------------------------------------------
# OAuth client store (persistent so a registered ChatGPT client survives restarts)
# ---------------------------------------------------------------------------

class PersistentOAuthProvider(OAuthProvider):
    """OAuthProvider with a JSON-file backed client store + full auth-code flow.

    FastMCP's OAuthProvider leaves the SDK's abstract methods (get_client,
    register_client, authorize, load/exchange authorization codes & tokens) as
    no-op stubs, so without this subclass every registered client would be
    "not found" on /authorize and /authorize would redirect to a None URL.

    This subclass implements the complete OAuth 2.1 authorization-code + PKCE
    flow:
      - Clients persisted to oauth_clients.json (register once, reuse forever).
      - /authorize generates a short-lived auth code (160-bit) bound to the
        PKCE challenge + redirect_uri, stores it, and redirects straight back
        to the client's redirect_uri (no third-party consent page — this is a
        single-owner filesystem, so consent is implicit).
      - /token exchanges the code for a Bearer access token + refresh token,
        verifying the PKCE code_verifier (done by the SDK handler) and
        redirect_uri.
      - Access/refresh tokens are stored in-memory with expiry; access tokens
        are also returned to verify_token for /mcp authorization.
    """

    def __init__(self, *args, store_path: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._store_path = Path(store_path) if store_path else Path(__file__).parent / "oauth_clients.json"
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._access_tokens: dict[str, AccessToken] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}
        if self._store_path.exists():
            try:
                import json as _json

                raw = _json.loads(self._store_path.read_text(encoding="utf-8"))
                for cid, data in raw.items():
                    self._clients[cid] = OAuthClientInformationFull.model_validate(data)
            except Exception:
                self._clients = {}

    def _save(self) -> None:
        import json as _json

        self._store_path.write_text(
            _json.dumps({cid: c.model_dump(mode="json") for cid, c in self._clients.items()}, indent=2),
            encoding="utf-8",
        )

    def _new_token(self, length: int = 48) -> str:
        """Cryptographically-random URL-safe token string (>=160 bits)."""
        return secrets.token_urlsafe(length)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        oauth_policy.assert_client_redirects(
            [str(u) for u in (client_info.redirect_uris or [])]
        )
        # Guarantee the client can request every scope we support. Some clients
        # (ChatGPT) request scopes individually during /authorize
        # (scope=filesystem+read+write) and validate_scope rejects anything the
        # client was not registered with. If the client omitted scopes or
        # registered a subset, fill in the full set so authorization succeeds.
        if not client_info.scope:
            client_info.scope = "filesystem read write"
        else:
            current = set(client_info.scope.split())
            full = {"filesystem", "read", "write"}
            if not full.issubset(current):
                client_info.scope = " ".join(sorted(full | current))
        self._clients[client_info.client_id] = client_info
        self._save()

    async def authorize(self, client: OAuthClientInformationFull, params) -> str:
        """Park the request and send the browser to the owner PIN page.

        ChatGPT can still complete OAuth; a random internet client cannot
        silently mint tokens. After PIN confirmation, issue_code() redirects
        to the allowlisted ChatGPT callback.
        """
        try:
            ticket = oauth_policy.park_consent(
                client_id=client.client_id,
                client_name=getattr(client, "client_name", None) or "ChatGPT",
                params=params,
            )
        except ValueError:
            return f"{BASE_URL}/consent?error=redirect_not_allowed"
        return f"{BASE_URL}/consent?ticket={ticket}"

    async def issue_code(self, client: OAuthClientInformationFull, params) -> str:
        """Issue the authorization code and return the client redirect URL."""
        import urllib.parse as _up

        code = self._new_token(32)
        now = datetime.now(timezone.utc).timestamp()
        self._auth_codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=now + 600,  # 10 min
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject=params.resource,  # no real user; tie to the resource URL
        )
        query = _up.urlencode(
            {"code": code, **({"state": params.state} if params.state else {})}
        )
        # params.redirect_uri is an AnyUrl; append query preserving the fragment.
        url = str(params.redirect_uri)
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{query}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._auth_codes.get(authorization_code)
        if code is None:
            return None
        if datetime.now(timezone.utc).timestamp() > code.expires_at:
            self._auth_codes.pop(authorization_code, None)
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        """Exchange an auth code for access + refresh tokens (single-use code)."""
        self._auth_codes.pop(authorization_code.code, None)  # one-time use

        scopes = authorization_code.scopes or ["filesystem"]
        access = self._new_token(32)
        refresh = self._new_token(40)
        now = datetime.now(timezone.utc).timestamp()

        self._access_tokens[access] = AccessToken(
            token=access,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=int(now) + 3600,  # 1 hour
            resource=authorization_code.resource,
            subject=authorization_code.subject,
        )
        self._refresh_tokens[refresh] = RefreshToken(
            token=refresh,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=int(now) + 7 * 86400,  # 7 days
            subject=authorization_code.subject,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        tok = self._refresh_tokens.get(refresh_token)
        if tok is None:
            return None
        if datetime.now(timezone.utc).timestamp() > tok.expires_at:
            self._refresh_tokens.pop(refresh_token, None)
            return None
        return tok

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Rotate the refresh token and issue a fresh access token."""
        self._refresh_tokens.pop(refresh_token.token, None)
        access = self._new_token(32)
        refresh = self._new_token(40)
        now = datetime.now(timezone.utc).timestamp()
        final_scopes = scopes or refresh_token.scopes or ["filesystem"]

        self._access_tokens[access] = AccessToken(
            token=access,
            client_id=client.client_id,
            scopes=final_scopes,
            expires_at=int(now) + 3600,
            subject=refresh_token.subject,
        )
        self._refresh_tokens[refresh] = RefreshToken(
            token=refresh,
            client_id=client.client_id,
            scopes=final_scopes,
            expires_at=int(now) + 7 * 86400,
            subject=refresh_token.subject,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(final_scopes),
            refresh_token=refresh,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        # Static API key → treat as a valid access token with full scopes.
        # This preserves backward-compatibility for clients that authenticate
        # with the raw API key instead of going through the OAuth flow.
        if API_KEY and secrets.compare_digest(token, API_KEY):
            return AccessToken(
                token=token,
                client_id="static-api-key",
                scopes=["filesystem", "read", "write"],
                expires_at=None,  # never expires
                resource=str(self._resource_url) if self._resource_url else None,
            )
        tok = self._access_tokens.get(token)
        if tok is None:
            return None
        if datetime.now(timezone.utc).timestamp() > tok.expires_at:
            self._access_tokens.pop(token, None)
            return None
        return tok


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="local-workspace",
    instructions=(
        f"You are connected to Local Workspace MCP at {ROOT} over the network. "
        "ALL paths are relative to that root — never use absolute paths or '..'. "
        "Use list_tree to discover structure before drilling into files, "
        "list_dir to inspect a single directory, and read_file to fetch content. "
        "read_file returns UTF-8 text for text files and base64 for binaries. "
        "For edits, read_file first, then apply small targeted write_file calls. "
        "For deletions use delete_file (destructive). "
        "Paths returned by the tools are ready to pass back verbatim."
    ),
    # OAuth Authorization Server: enables ChatGPT's OAuth connector flow.
    # - Dynamic Client Registration (DCR) so ChatGPT can register a client id.
    # - Authorization Code + PKCE flow with /authorize, /token, discovery.
    # base_url must be the public HTTPS origin (Cloudflare named tunnel).
    auth=PersistentOAuthProvider(
        base_url=BASE_URL,
        resource_base_url=BASE_URL,
        service_documentation_url=f"{BASE_URL}/health",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["filesystem", "read", "write"],
            default_scopes=["filesystem"],
        ),
    ),
)

# Register the full-machine tool suite (filesystem, editing, search, exec,
# processes, system, git, archive, CDP...).
register_all_tools(mcp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not API_KEY:
        print(
            "[warn] WORKSPACE_MCP_API_KEY is not set. The server will reject all "
            "requests. Set it to a strong random value (e.g. secrets.token_urlsafe(32)).",
            flush=True,
        )

    if not ROOT.is_dir():
        raise SystemExit(f"WORKSPACE_MCP_ROOT '{ROOT}' does not exist.")

    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
    from starlette.routing import Mount, Route

    # FastMCP app — mounts its MCP endpoints under "/mcp" plus the OAuth
    # endpoints from the auth provider (/.well-known, /authorize, /token,
    # /register/DCR...). host_origin_protection stays off so the Cloudflare
    # tunnel Host header is accepted.
    mcp_app = mcp.http_app(transport="http", host_origin_protection=False)

    async def health(request):
        return JSONResponse({
            "status": "ok",
            "active_requests": _ACTIVE_REQUESTS,
        })

    async def consent_get(request):
        err = request.query_params.get("error")
        if err and not request.query_params.get("ticket"):
            return HTMLResponse(oauth_policy.error_page("OAuth bị từ chối: redirect không nằm trong allowlist ChatGPT."), 400)
        ticket = request.query_params.get("ticket", "")
        payload = oauth_policy.take_ticket(ticket)
        if payload is None:
            return HTMLResponse(oauth_policy.error_page("Ticket hết hạn hoặc không hợp lệ."), 400)
        return HTMLResponse(oauth_policy.consent_page(
            ticket=ticket,
            client_name=payload["client_name"],
            redirect_uri=payload["redirect_uri"],
        ))

    async def consent_post(request):
        import urllib.parse as _up

        raw = (await request.body()).decode("utf-8", errors="replace")
        form = dict(_up.parse_qsl(raw))
        ticket = str(form.get("ticket") or "")
        decision = str(form.get("decision") or "")
        payload = oauth_policy.take_ticket(ticket)
        if payload is None:
            return HTMLResponse(oauth_policy.error_page("Ticket hết hạn hoặc không hợp lệ."), 400)

        def _client_error_redirect(code: str) -> RedirectResponse:
            import urllib.parse as _up
            url = payload["redirect_uri"]
            q = {"error": code}
            if payload.get("state"):
                q["state"] = payload["state"]
            sep = "&" if "?" in url else "?"
            return RedirectResponse(url + sep + _up.urlencode(q), status_code=302)

        if decision != "allow":
            oauth_policy.consume_ticket(ticket)
            return _client_error_redirect("access_denied")

        if not oauth_policy.pin_ok(str(form.get("pin") or "")):
            burned = oauth_policy.record_pin_failure(ticket)
            msg = "Sai PIN." + (" Ticket đã hủy." if burned else "")
            remaining = oauth_policy.take_ticket(ticket)
            if remaining is None:
                return HTMLResponse(oauth_policy.error_page(msg), 401)
            return HTMLResponse(oauth_policy.consent_page(
                ticket=ticket,
                client_name=remaining["client_name"],
                redirect_uri=remaining["redirect_uri"],
                error=msg,
            ), 401)

        payload = oauth_policy.consume_ticket(ticket)
        if payload is None:
            return HTMLResponse(oauth_policy.error_page("Ticket hết hạn."), 400)
        client = await mcp.auth.get_client(payload["client_id"])
        if client is None:
            return HTMLResponse(oauth_policy.error_page("OAuth client không còn tồn tại."), 400)
        url = await mcp.auth.issue_code(client, payload["params"])
        return RedirectResponse(url, status_code=302)

    from fastmcp.server.lifespan import Lifespan

    # Kill any long-running processes (Chrome CDP, dev servers) on shutdown so
    # they never leak after the server stops.
    @asynccontextmanager
    async def _lifespan(app):
        async with mcp_app.lifespan(app):
            try:
                yield
            finally:
                PROCESS_MANAGER.shutdown()

    # Parent app: serves /health and carries the FastMCP lifespan. Activity
    # tracking is outermost so the supervisor can distinguish a busy server from
    # a wedged one; API-key enforcement remains in front of the MCP app.
    app = Starlette(
        routes=[
            Route("/health", health),
            Route("/consent", consent_get, methods=["GET"]),
            Route("/consent", consent_post, methods=["POST"]),
            Mount("/", app=mcp_app),
        ],
        middleware=[
            Middleware(RequestActivityMiddleware),
            Middleware(APIKeyMiddleware),
        ],
        lifespan=_lifespan,
    )
    # Keep-alive balance: request handling itself is unbounded, this only
    # affects idle connection reuse between MCP messages. A too-long idle
    # keep-alive (120s) let Cloudflare/proxies hold a socket open past their
    # own timeout, then reset it abruptly — flooding asyncio with
    # ConnectionResetError [WinError 10054] callbacks that, under CPU-heavy
    # builds, backlogged the event loop and wedged the server. 20s recycles
    # idle connections cleanly before proxies drop them.
    uvicorn.run(
        app, host=HOST, port=PORT, log_level="info",
        timeout_keep_alive=int(os.environ.get("UVICORN_KEEP_ALIVE", "20")),
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
