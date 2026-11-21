"""V2 Phase 2: authentication, roles, territory scoping, audit, and negative (attack) tests.

Runs on a temporary SQLite database (host and container). Synthetic users only.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.auth.deps import COOKIE_NAME, CSRF_HEADER, CSRF_VALUE
from app.auth.passwords import hash_password
from app.auth.service import utcnow
from app.core.config import get_settings
from app.db.database import connect
from app.db.models import AuditEvent, AuthSession, Territory, TerritoryAssignment, User
from app.main import create_app

PW = "correct-horse-battery-staple"  # synthetic test password
H = {CSRF_HEADER: CSRF_VALUE}
ORIGIN = {"origin": "https://testserver"}


@pytest.fixture
def env(tmp_path):
    engine = connect(tmp_path / "auth.db")
    with Session(engine) as db:
        ta, tb = Territory(code="T-A", name="Territory A"), Territory(code="T-B", name="Territory B")
        users = {
            name: User(username=name, display_name=name.title(), role=role, password_hash=hash_password(PW))
            for name, role in [("worker_a", "worker"), ("worker_b", "worker"),
                               ("supervisor", "supervisor"), ("admin", "admin")]
        }
        db.add_all([ta, tb, *users.values()])
        db.flush()
        db.add_all([
            TerritoryAssignment(user_id=users["worker_a"].id, territory_id=ta.id),
            TerritoryAssignment(user_id=users["worker_b"].id, territory_id=tb.id),
            TerritoryAssignment(user_id=users["supervisor"].id, territory_id=ta.id),
            TerritoryAssignment(user_id=users["supervisor"].id, territory_id=tb.id),
        ])
        db.commit()
        ids = {"T-A": ta.id, "T-B": tb.id, **{k: v.id for k, v in users.items()}}
    app = create_app(engine)
    with TestClient(app, base_url="https://testserver") as client:
        yield client, engine, ids


def login(client, username, password=PW):
    return client.post("/api/v2/auth/login", json={"username": username, "password": password}, headers=H)


# ------------------------------------------------------------------ authentication
def test_login_sets_hardened_cookie_and_me_works(env):
    client, _, ids = env
    r = login(client, "worker_a")
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
    me = client.get("/api/v2/auth/me").json()
    assert me["role"] == "worker"
    assert [t["code"] for t in me["territories"]] == ["T-A"]


def test_wrong_password_and_unknown_user_get_same_generic_error(env):
    client, _, _ = env
    a, b = login(client, "worker_a", "wrong-password-123"), login(client, "nobody", "wrong-password-123")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_login_rate_limited_after_repeated_failures(env):
    client, _, _ = env
    for _ in range(get_settings().login_max_failures):
        assert login(client, "worker_a", "wrong-password-123").status_code == 401
    assert login(client, "worker_a").status_code == 429  # even the right password is refused now


def test_login_without_csrf_header_is_refused(env):
    client, _, _ = env
    r = client.post("/api/v2/auth/login", json={"username": "worker_a", "password": PW})
    assert r.status_code == 403


def test_unauthenticated_requests_get_401(env):
    client, _, ids = env
    assert client.get("/api/v2/auth/me").status_code == 401
    assert client.get("/api/v2/territories").status_code == 401
    assert client.get(f"/api/v2/territories/{ids['T-A']}").status_code == 401


def test_forged_cookie_rejected(env):
    client, _, _ = env
    client.cookies.set(COOKIE_NAME, "forged-token-value", domain="testserver")
    assert client.get("/api/v2/auth/me").status_code == 401


def test_logout_revokes_the_token_server_side(env):
    client, _, _ = env
    login(client, "worker_a")
    token = client.cookies.get(COOKIE_NAME)
    assert client.post("/api/v2/auth/logout", headers=H).status_code == 204
    client.cookies.set(COOKIE_NAME, token, domain="testserver")  # replay the old token
    assert client.get("/api/v2/auth/me").status_code == 401


def test_expired_session_rejected(env):
    client, engine, _ = env
    login(client, "worker_a")
    with Session(engine) as db:
        for s in db.scalars(select(AuthSession)).all():
            s.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/v2/auth/me").status_code == 401


def test_deactivated_user_loses_access_immediately(env):
    client, engine, ids = env
    login(client, "worker_a")
    with Session(engine) as db:
        db.get(User, ids["worker_a"]).active = False
        db.commit()
    assert client.get("/api/v2/auth/me").status_code == 401
    assert login(client, "worker_a").status_code == 401


# ------------------------------------------------------------------ territory scoping (BOLA)
def test_worker_sees_only_own_territory(env):
    client, _, ids = env
    login(client, "worker_a")
    assert [t["code"] for t in client.get("/api/v2/territories").json()] == ["T-A"]
    assert client.get(f"/api/v2/territories/{ids['T-A']}").status_code == 200


def test_worker_guessing_other_territory_id_gets_404(env):
    client, _, ids = env
    login(client, "worker_a")
    r = client.get(f"/api/v2/territories/{ids['T-B']}")
    assert r.status_code == 404  # not 403: does not confirm the ID exists


def test_supervisor_sees_assigned_and_admin_sees_all(env):
    client, _, _ = env
    login(client, "supervisor")
    assert [t["code"] for t in client.get("/api/v2/territories").json()] == ["T-A", "T-B"]
    client.cookies.clear()
    login(client, "admin")
    assert [t["code"] for t in client.get("/api/v2/territories").json()] == ["T-A", "T-B"]


def test_ending_assignment_removes_access_without_relogin(env):
    client, engine, ids = env
    login(client, "worker_a")
    with Session(engine) as db:
        row = db.scalar(select(TerritoryAssignment).where(TerritoryAssignment.user_id == ids["worker_a"]))
        row.ends_at = utcnow()
        db.commit()
    assert client.get("/api/v2/territories").json() == []
    assert client.get(f"/api/v2/territories/{ids['T-A']}").status_code == 404


# ------------------------------------------------------------------ roles and audit
@pytest.mark.parametrize("who", ["worker_a", "supervisor"])
def test_non_admin_cannot_use_admin_endpoints(env, who):
    client, _, ids = env
    login(client, who)
    body = {"username": "mallory", "display_name": "M", "role": "admin", "password": PW}
    assert client.post("/api/v2/admin/users", json=body, headers=H).status_code == 403
    assert client.post("/api/v2/admin/assignments", json={"user_id": str(ids[who]), "territory_id": str(ids["T-B"])},
                       headers=H).status_code == 403
    assert client.get("/api/v2/admin/audit").status_code == 403


def test_admin_changes_are_audited_without_secrets(env):
    client, engine, ids = env
    login(client, "admin")
    r = client.post("/api/v2/admin/users", headers=H, json={
        "username": "worker_c", "display_name": "Worker C", "role": "worker", "password": PW})
    assert r.status_code == 201
    new_id = r.json()["id"]
    a = client.post("/api/v2/admin/assignments", headers=H,
                    json={"user_id": new_id, "territory_id": str(ids["T-A"])})
    assert a.status_code == 201
    assert client.post("/api/v2/admin/assignments", headers=H,
                       json={"user_id": new_id, "territory_id": str(ids["T-A"])}).status_code == 409
    assert client.post(f"/api/v2/admin/assignments/{a.json()['id']}/end", headers=H).json()["ends_at"]
    actions = [e["action"] for e in client.get("/api/v2/admin/audit").json()]
    assert {"user.create", "assignment.create", "assignment.end", "auth.login"} <= set(actions)
    with Session(engine) as db:
        dump = " ".join(str(e.details) + str(e.resource_id) for e in db.scalars(select(AuditEvent)).all())
    assert PW not in dump


def test_admin_unsafe_request_without_csrf_header_refused(env):
    client, _, _ = env
    login(client, "admin")
    body = {"username": "worker_d", "display_name": "D", "role": "worker", "password": PW}
    assert client.post("/api/v2/admin/users", json=body).status_code == 403


def test_request_id_header_returned(env):
    client, _, _ = env
    assert client.get("/api/health").headers.get("x-request-id")


# ------------------------------------------------------------------ WebSocket gate
def _ws(client, headers):
    with client.websocket_connect("/ws/v2/session", headers=headers) as ws:
        return ws.receive_json()


def test_ws_without_session_cookie_rejected(env):
    client, _, _ = env
    with pytest.raises(WebSocketDisconnect) as exc:
        _ws(client, ORIGIN)
    assert exc.value.code == 4401


def test_ws_with_forged_cookie_rejected(env):
    client, _, _ = env
    with pytest.raises(WebSocketDisconnect) as exc:
        _ws(client, {**ORIGIN, "cookie": f"{COOKIE_NAME}=forged"})
    assert exc.value.code == 4401


def test_ws_cross_site_origin_rejected_even_with_valid_cookie(env):
    client, _, _ = env
    login(client, "worker_a")
    token = client.cookies.get(COOKIE_NAME)
    with pytest.raises(WebSocketDisconnect) as exc:
        _ws(client, {"origin": "https://evil.example", "cookie": f"{COOKIE_NAME}={token}"})
    assert exc.value.code == 4403


def test_ws_authenticated_same_origin_accepted(env):
    client, _, _ = env
    login(client, "worker_a")
    token = client.cookies.get(COOKIE_NAME)
    msg = _ws(client, {**ORIGIN, "cookie": f"{COOKIE_NAME}={token}"})
    assert msg["code"] == "NOT_READY"  # gate passed; voice binding is Phase 5


# ------------------------------------------------------------------ Round 1 compatibility switch
def test_legacy_default_off_in_v2_postgres_mode_and_on_only_in_sqlite_mode():
    from app.core.config import Settings

    v2 = Settings(_env_file=None, database_url="postgresql+psycopg://u:p@db/x", legacy_round1_api_enabled=None)
    r1 = Settings(_env_file=None, database_url=None, legacy_round1_api_enabled=None)
    assert v2.legacy_round1_enabled is False   # V2: unauthenticated Round 1 endpoints off by default
    assert r1.legacy_round1_enabled is True    # Round 1 SQLite workflow unchanged
    assert Settings(_env_file=None, database_url="postgresql+psycopg://u:p@db/x",
                    legacy_round1_api_enabled=True).legacy_round1_enabled is True  # explicit opt-in only


@pytest.mark.parametrize(("flag", "visits_status"), [("false", 404), ("true", 200)])
def test_legacy_round1_api_switch(tmp_path, monkeypatch, flag, visits_status):
    monkeypatch.setenv("LEGACY_ROUND1_API_ENABLED", flag)
    get_settings.cache_clear()
    try:
        with TestClient(create_app(connect(tmp_path / "l.db")), base_url="https://testserver") as client:
            assert client.get("/api/visits").status_code == visits_status
            assert client.get("/api/health").json()["legacy_round1_api"] is (flag == "true")
    finally:
        monkeypatch.delenv("LEGACY_ROUND1_API_ENABLED")
        get_settings.cache_clear()
