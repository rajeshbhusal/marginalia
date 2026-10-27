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


# The sign-in page can't load the web app's assets (they're behind the gate), so it carries
# its own copy of the design tokens in frontend/src/tokens.css: same colours, light and dark.
_STYLE = """
:root {
  --canvas: #f6f7f9; --surface: #ffffff; --line: #e2e5ea; --line-control: #898c92;
  --ink: #15171c; --ink-muted: #4a4d53; --brand: #2f5bea; --brand-hover: #2349c8;
  --on-brand: #ffffff; --negative: #c7362c; --negative-ink: #ba2c25;
  --elevation: 0 1px 2px oklch(0.2 0.01 265 / 0.04), 0 2px 6px -1px oklch(0.2 0.01 265 / 0.06);
  color-scheme: light;
}
:root[data-theme="dark"] {
  --canvas: #0e1014; --surface: #17191e; --line: #292b30; --line-control: #696c72;
  --ink: #e9ebf0; --ink-muted: #b8bcc2; --brand: #7e9dff; --brand-hover: #9cb3ff;
  --on-brand: #0b1330; --negative: #ff7b6e; --negative-ink: #ff7b6e;
  --elevation: 0 1px 2px oklch(0 0 0 / 0.3), 0 2px 6px -1px oklch(0 0 0 / 0.35);
  color-scheme: dark;
}
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; min-height: 100dvh; display: grid; place-items: center;
  padding: 24px 16px; background: var(--canvas); color: var(--ink);
  font: 400 14px/20px "Inter Variable", Inter, ui-sans-serif, system-ui, -apple-system,
    "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
main { width: min(100%, 24rem); }
.brand {
  display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 24px;
  font: 600 20px/28px "Source Serif 4 Variable", "Source Serif 4", ui-serif, Georgia, serif;
  letter-spacing: -0.01em;
}
.brand svg { width: 28px; height: 28px; }
.brand .page { fill: var(--brand); }
form {
  padding: 32px; border: 1px solid var(--line); border-radius: 12px;
  background: var(--surface); box-shadow: var(--elevation);
}
h1 { margin: 0; font-size: 20px; line-height: 28px; font-weight: 600; letter-spacing: -0.01em; }
.lead { margin: 4px 0 24px; color: var(--ink-muted); }
label { display: block; margin-bottom: 8px; font-weight: 500; }
input[type="password"] {
  display: block; width: 100%; height: 44px; padding: 0 12px; border-radius: 8px;
  border: 1px solid var(--line-control); background: var(--surface); color: var(--ink);
  font: inherit; font-size: 16px;
}
input[aria-invalid="true"] { border-color: var(--negative); }
.error { display: flex; gap: 8px; margin: 8px 0 0; color: var(--negative-ink); }
.error svg { flex: none; width: 16px; height: 16px; margin-top: 2px; }
button {
  width: 100%; height: 44px; margin-top: 24px; border: 0; border-radius: 8px;
  background: var(--brand); color: var(--on-brand); font: inherit; font-size: 16px;
  font-weight: 500; cursor: pointer;
}
button:hover { background: var(--brand-hover); }
:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
@media (max-width: 400px) { form { padding: 24px; } }
"""

# The same theme choice as the web app: the one saved by its toggle, or the system's
_THEME_SCRIPT = """(function () {
  var saved = null;
  try { saved = localStorage.getItem("marginalia-theme"); } catch (e) {}
  var dark = saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();"""

_LOGO = """<svg viewBox="0 0 64 64" aria-hidden="true">
<rect class="page" x="6" y="4" width="40" height="56" rx="6"/>
<rect x="14" y="16" width="20" height="4" rx="2" fill="#fff" opacity=".9"/>
<rect x="14" y="26" width="24" height="4" rx="2" fill="#fff" opacity=".9"/>
<rect x="14" y="36" width="16" height="4" rx="2" fill="#fff" opacity=".9"/>
<rect x="40" y="22" width="20" height="16" rx="4" fill="#ffc400"/>
<path d="M44 38l-4 7v-7z" fill="#ffc400"/></svg>"""

_ALERT_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" '
    'r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>'
)

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>Sign in · Marginalia</title>
<script>{script}</script>
<style>{style}</style></head>
<body><main>
  <div class="brand">{logo}<span>Marginalia</span></div>
  <form method="post" action="/login">
    <h1>Sign in</h1>
    <p class="lead">Enter the password you were given to continue.</p>
    <input type="hidden" name="next" value="{next}">
    <label for="password">Password</label>
    <input id="password" type="password" name="password" autocomplete="current-password"
           required autofocus{invalid}>
    {error}
    <button type="submit">Sign in</button>
  </form>
</main></body></html>"""


def _login_page(next_path: str, error: str = "", status: int = 200) -> HTMLResponse:
    error_html = (
        f'<p class="error" id="password-error" role="alert">{_ALERT_ICON}{html.escape(error)}</p>'
        if error
        else ""
    )
    invalid = ' aria-invalid="true" aria-describedby="password-error"' if error else ""
    page = _PAGE.format(
        script=_THEME_SCRIPT,
        style=_STYLE,
        logo=_LOGO,
        error=error_html,
        invalid=invalid,
        next=html.escape(next_path, quote=True),
    )
    return HTMLResponse(page, status_code=status, headers={"Cache-Control": "no-store"})


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
