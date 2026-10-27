"""An optional shared-password gate for hosted test deployments.

When MARGINALIA_ACCESS_PASSWORD is set, every page and API route needs the password, entered
on /login and kept in a signed, httpOnly cookie. /api/health stays open for health checks.
With no password set (local development) nothing changes.
"""

import asyncio
import hashlib
import hmac
import html
import time
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.settings import settings

COOKIE_NAME = "marginalia_session"
OPEN_PATHS = {"/api/health", "/login", "/logout"}
FAILED_LOGIN_DELAY = 1.0  # Seconds, to slow down password guessing

router = APIRouter(include_in_schema=False)


def check_settings() -> None:
    if settings.access_gate_enabled and not settings.SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET must be set when MARGINALIA_ACCESS_PASSWORD is set.")


def _signature(issued: str) -> str:
    # The password is part of the signed message, so changing it signs everyone out
    key = hashlib.sha256(
        f"{settings.SESSION_SECRET}\0{settings.MARGINALIA_ACCESS_PASSWORD}".encode()
    ).digest()
    return hmac.new(key, f"marginalia-access:{issued}".encode(), hashlib.sha256).hexdigest()


def make_token(now: float | None = None) -> str:
    issued = str(int(now if now is not None else time.time()))
    return f"{issued}.{_signature(issued)}"


def token_is_valid(token: str | None, now: float | None = None) -> bool:
    if not token or "." not in token:
        return False
    issued, signature = token.split(".", 1)
    if not issued.isdigit() or not hmac.compare_digest(signature, _signature(issued)):
        return False
    age = (now if now is not None else time.time()) - int(issued)
    return 0 <= age <= settings.SESSION_MAX_AGE_DAYS * 86400


def _safe_next(target: str | None) -> str:
    # Only same-site paths, so the login page can't be used as an open redirect
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    return target


def install(app: FastAPI) -> None:
    app.include_router(router)

    @app.middleware("http")
    async def access_gate(request: Request, call_next):
        if not settings.access_gate_enabled or request.url.path in OPEN_PATHS:
            return await call_next(request)
        if token_is_valid(request.cookies.get(COOKIE_NAME)):
            return await call_next(request)
        if request.url.path.startswith("/api/") or request.url.path in ("/docs", "/openapi.json"):
            return JSONResponse(status_code=401, content={"detail": "Sign in to Marginalia."})
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Sign in · Marginalia</title>
<style>
  :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
  body {{ display: grid; place-items: center; min-height: 100vh; margin: 0; }}
  form {{ display: grid; gap: .75rem; width: min(20rem, 90vw); }}
  h1 {{ font-size: 1.25rem; margin: 0 0 .5rem; }}
  input, button {{ font: inherit; padding: .6rem .75rem; border-radius: .5rem; }}
  input {{ border: 1px solid #8886; }}
  button {{ border: 0; background: #2563eb; color: white; cursor: pointer; }}
  .error {{ color: #dc2626; margin: 0; }}
</style></head>
<body><form method="post" action="/login">
  <h1>Marginalia</h1>
  {error}
  <input type="hidden" name="next" value="{next}">
  <input type="password" name="password" placeholder="Password" aria-label="Password"
         autocomplete="current-password" required autofocus>
  <button type="submit">Sign in</button>
</form></body></html>"""


def _login_page(next_path: str, error: str = "", status: int = 200) -> HTMLResponse:
    error_html = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
    return HTMLResponse(
        _PAGE.format(error=error_html, next=html.escape(next_path, quote=True)),
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/login")
async def login_form(request: Request) -> Response:
    next_path = _safe_next(request.query_params.get("next"))
    if not settings.access_gate_enabled or token_is_valid(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse(next_path, status_code=303)
    return _login_page(next_path)


@router.post("/login")
async def login(request: Request) -> Response:
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    password = (form.get("password") or [""])[0]
    next_path = _safe_next((form.get("next") or ["/"])[0])
    if not settings.access_gate_enabled:
        return RedirectResponse(next_path, status_code=303)
    expected = settings.MARGINALIA_ACCESS_PASSWORD or ""
    if not hmac.compare_digest(password.encode(), expected.encode()):
        await asyncio.sleep(FAILED_LOGIN_DELAY)
        return _login_page(next_path, "That password isn't right.", status=401)
    response = RedirectResponse(next_path, status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        make_token(),
        max_age=settings.SESSION_MAX_AGE_DAYS * 86400,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(
        COOKIE_NAME, httponly=True, secure=settings.SESSION_COOKIE_SECURE, samesite="lax"
    )
    return response
