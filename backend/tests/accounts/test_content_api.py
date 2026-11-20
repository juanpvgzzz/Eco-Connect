from backend.app.accounts.models import AccountRole
from backend.tests.accounts.test_api import make_client, register
from backend.tests.accounts.test_content import MemoryContentStore


def test_only_published_content_is_public_and_admin_can_publish():
    client, accounts = make_client()
    content_store = MemoryContentStore()
    client.app.state.content_store = content_store
    register(client)
    admin = accounts.find_by_national_id("123456789")
    admin.role = AccountRole.ADMIN
    login = client.post(
        "/accounts/login", json={"national_id": "123456789", "pin": "1234"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    draft_response = client.post(
        "/content/admin",
        json={
            "title": "Separar residuos",
            "category": "separation",
            "body": "Separa los materiales reciclables.",
        },
        headers=headers,
    )

    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["status"] == "draft"
    assert client.get("/content").json() == []
    assert client.get(f"/content/{draft['id']}").status_code == 404
    assert client.post(f"/content/admin/{draft['id']}/publish", headers=headers).status_code == 200
    assert client.get("/content").json()[0]["id"] == draft["id"]


def test_non_admin_cannot_create_content():
    client, _ = make_client()
    client.app.state.content_store = MemoryContentStore()
    register(client)
    login = client.post(
        "/accounts/login", json={"national_id": "123456789", "pin": "1234"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/content/admin",
        json={
            "title": "Guía",
            "category": "materials",
            "body": "Contenido.",
        },
        headers=headers,
    )

    assert response.status_code == 403
