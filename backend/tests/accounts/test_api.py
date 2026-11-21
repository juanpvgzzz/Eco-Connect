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


def test_validation_errors_do_not_echo_submitted_credentials():
    client, _ = make_client()
    invalid = register(client, pin="x" * 16)
    incomplete = client.post("/accounts", json={"pin": "0" * 8})
    for response in (invalid, incomplete):
        assert response.status_code == 422
        assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


def test_adapter_value_error_does_not_leak_internal_details():
    client, store = make_client()

    def fail_lookup(_national_id):
        raise ValueError("database connection password leaked")

    store.find_by_national_id = fail_lookup
    client = TestClient(client.app, raise_server_exceptions=False)
    response = client.post(
        "/accounts/login", json={"national_id": "123456789", "pin": "1234"}
    )

    assert response.status_code == 500
    assert "database connection password leaked" not in response.text


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
        json={
            "role": "leader",
            "pilot_enabled": True,
            "collective_id": "collective-recyclers",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert updated.status_code == 200
    assert updated.json()["profile"]["role"] == "leader"
    assert updated.json()["profile"]["pilot_enabled"] is True
    assert updated.json()["collective_id"] == "collective-recyclers"
    assert {"address", "phone"}.isdisjoint(updated.json()["profile"])
    users = client.get("/accounts/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert users.status_code == 200
    assert users.json()
    assert all({"address", "phone"}.isdisjoint(user) for user in users.json())


def test_openapi_exposes_account_content_and_community_routes():
    client, _ = make_client()

    schema = client.get("/openapi.json").json()

    assert "/accounts/login" in schema["paths"]
    assert "/content" in schema["paths"]
    assert "/community/collections" in schema["paths"]


def test_resident_cannot_manage_access_and_admin_cannot_grant_field_worker_access():
    client, store = make_client()
    account = register(client).json()
    login_body = {"national_id": "123456789", "pin": "1234"}
    token = client.post("/accounts/login", json=login_body).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    path = f"/accounts/admin/{account['id']}/authorization"
    worker = {"role": "field_worker", "pilot_enabled": False, "collective_id": "huerta"}
    assert client.get("/accounts/admin/users", headers=headers).status_code == 403
    assert client.get("/accounts/admin/collectives", headers=headers).status_code == 403
    assert client.put(path, headers=headers, json=worker).status_code == 403
    record = store.find_by_id(account["id"])
    record.role = AccountRole.ADMIN
    assert client.put(path, headers=headers, json=worker).status_code == 422

    record.role = AccountRole.FIELD_WORKER
    assert client.get("/accounts/me", headers=headers).status_code == 401
    assert client.post("/accounts/login", json=login_body).status_code == 401
