from fastapi.testclient import TestClient

from backend.app.accounts.models import AccountRole
from backend.app.main import create_app
from backend.tests.accounts.test_service import MemoryAccountStore


def make_client():
    store = MemoryAccountStore()
    app = create_app()
    app.state.account_store = store
    return TestClient(app), store


def register(client, **overrides):
    body = {
        "national_id": "12.345.678-9",
        "full_name": "María Pérez",
        "address": "Calle 1",
        "phone": "3001234567",
        "kind": "household",
        "pin": "1234",
    }
    body.update(overrides)
    return client.post("/accounts", json=body)


def test_public_registration_returns_profile_without_privileges():
    client, _ = make_client()

    response = register(client)

    assert response.status_code == 201
    data = response.json()
    assert data["profile"]["national_id"] == "123456789"
    assert data["profile"]["role"] == "resident"
    assert data["profile"]["pilot_enabled"] is False
    assert "pin" not in data["profile"]


def test_registration_rejects_privilege_fields():
    client, _ = make_client()

    response = register(client, role="admin", pilot_enabled=True)

    assert response.status_code == 422


def test_registration_rejects_invalid_pin():
    client, _ = make_client()

    response = register(client, pin="not-a-pin")

    assert response.status_code == 422


def test_login_profile_and_logout_revokes_token():
    client, _ = make_client()
    assert register(client).status_code == 201
    login = client.post(
        "/accounts/login", json={"national_id": "123456789", "pin": "1234"}
    )
    token = login.json()["access_token"]

    profile = client.get("/accounts/me", headers={"Authorization": f"Bearer {token}"})
    logged_out = client.post(
        "/accounts/logout", headers={"Authorization": f"Bearer {token}"}
    )
    after_logout = client.get("/accounts/me", headers={"Authorization": f"Bearer {token}"})

    assert profile.status_code == 200
    assert profile.json()["id"]
    assert logged_out.status_code == 204
    assert after_logout.status_code == 401


def test_only_admin_can_authorize_profiles_and_enable_pilot():
    client, store = make_client()
    register(client, national_id="123456789", kind="business")
    account = store.find_by_national_id("123456789")
    account.role = AccountRole.ADMIN
    register(client, national_id="987654321", kind="business")
    target = store.find_by_national_id("987654321")

    login = client.post(
        "/accounts/login", json={"national_id": "123456789", "pin": "1234"}
    )
    token = login.json()["access_token"]
    updated = client.put(
        f"/accounts/admin/{target.id}/authorization",
        json={"role": "leader", "pilot_enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert updated.status_code == 200
    assert updated.json()["profile"]["role"] == "leader"
    assert updated.json()["profile"]["pilot_enabled"] is True
