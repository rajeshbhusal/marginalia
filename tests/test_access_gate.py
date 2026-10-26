import time

import httpx
import pytest

from app import auth
from app.settings import settings


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setattr(settings, "MARGINALIA_ACCESS_PASSWORD", "correct horse")
    monkeypatch.setattr(settings, "SESSION_SECRET", "test-secret")
    monkeypatch.setattr(auth, "FAILED_LOGIN_DELAY", 0)


async def _login(client, password="correct horse", next_path="/"):
    return await client.post(
        "/login",
        content=httpx.QueryParams({"password": password, "next": next_path}).__str__(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


async def test_without_a_password_nothing_is_gated(client):
    assert (await client.get("/api/courses")).status_code == 200


async def test_api_needs_a_login(client, gate):
    response = await client.get("/api/courses")
    assert response.status_code == 401


async def test_pages_redirect_to_the_login_page(client, gate):
    response = await client.get("/courses/abc?x=1")
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fcourses%2Fabc%3Fx%3D1"
    page = await client.get("/login?next=/courses/abc")
    assert page.status_code == 200
    assert 'type="password"' in page.text


async def test_health_stays_open(client, gate):
    assert (await client.get("/api/health")).status_code == 200


async def test_wrong_password_is_rejected(client, gate):
    response = await _login(client, "nope")
    assert response.status_code == 401
    assert auth.COOKIE_NAME not in response.cookies
    assert (await client.get("/api/courses")).status_code == 401


async def test_login_sets_a_secure_signed_cookie(client, gate):
    response = await _login(client, next_path="/courses/abc")
    assert response.status_code == 303
    assert response.headers["location"] == "/courses/abc"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    token = response.cookies[auth.COOKIE_NAME]
    assert auth.token_is_valid(token)

    client.cookies.set(auth.COOKIE_NAME, token)
    assert (await client.get("/api/courses")).status_code == 200

    logout = await client.post("/logout")
    assert logout.status_code == 303
    client.cookies.clear()
    assert (await client.get("/api/courses")).status_code == 401


async def test_login_never_redirects_off_site(client, gate):
    for target in ("https://evil.example", "//evil.example", "/\\evil.example"):
        response = await _login(client, next_path=target)
        assert response.headers["location"] == "/"


def test_tokens_are_tamper_proof_and_expire(gate, monkeypatch):
    token = auth.make_token()
    issued, signature = token.split(".")
    assert not auth.token_is_valid(f"{int(issued) + 1}.{signature}")
    assert not auth.token_is_valid(token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert not auth.token_is_valid("garbage")
    assert not auth.token_is_valid(token, now=time.time() + 31 * 86400)
    # A new secret or password signs everyone out
    monkeypatch.setattr(settings, "SESSION_SECRET", "rotated")
    assert not auth.token_is_valid(token)


def test_a_password_needs_a_session_secret(monkeypatch):
    monkeypatch.setattr(settings, "MARGINALIA_ACCESS_PASSWORD", "pw")
    monkeypatch.setattr(settings, "SESSION_SECRET", None)
    with pytest.raises(RuntimeError):
        auth.check_settings()
