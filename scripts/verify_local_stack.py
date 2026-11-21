"""Exercise the local Compose API and verify persisted records in PostgreSQL.

Run inside the API container with:
    docker compose exec -T api python - < scripts/verify_local_stack.py

The check refuses to run unless DATABASE_URL points to the local Compose `db`
service. It only appends uniquely keyed test accounts and collection requests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from db.connection import open_connection


BASE_URL = "http://127.0.0.1:8000"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def call(method: str, path: str, *, body=None, token=None, key=None):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["Idempotency-Key"] = key
    request = Request(
        BASE_URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except HTTPError as error:
        payload = error.read()
        try:
            detail = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            detail = None
        return error.code, detail
    except URLError as error:
        raise RuntimeError("FastAPI is not reachable at the local Compose service") from error


def register_and_login(national_id: str) -> tuple[str, str]:
    status, profile = call("POST", "/accounts", body={
        "national_id": national_id,
        "full_name": "Prueba local EcoConecta",
        "address": "Dirección de prueba local",
        "phone": "3000000000",
        "kind": "household",
        "pin": "731942",
    })
    require(status == 201, f"Local test account registration returned HTTP {status}")
    account_id = profile["id"]
    status, session = call("POST", "/accounts/login", body={
        "national_id": national_id,
        "pin": "731942",
    })
    require(status == 200 and bool(session.get("access_token")), "Login failed")
    token = session["access_token"]
    status, identity = call("GET", "/accounts/me", token=token)
    require(status == 200 and identity.get("id") == account_id, "Profile lookup mismatch")
    return account_id, token


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    pilot_value = os.environ.get("ECO_PILOT_ID", "")
    parsed = urlparse(database_url)
    require(parsed.hostname == "db", "Refusing to test: DATABASE_URL host must be local Compose service 'db'")
    require(bool(pilot_value), "ECO_PILOT_ID is not configured")
    pilot_id = UUID(pilot_value)

    with open_connection(database_url) as conn:
        pilot = conn.execute(
            "select id from pilots where id = %s and active", (pilot_id,)
        ).fetchone()
        require(pilot is not None, "Configured active local pilot does not exist")
        flows = {
            row["flow"]
            for row in conn.execute(
                "select flow from collectives where pilot_id = %s", (pilot_id,)
            ).fetchall()
        }
        require({"huerta", "reciclaje"} <= flows, "Local pilot is missing a required collective")
        applied_migrations = {
            row["name"]: row["sha256"]
            for row in conn.execute("select name, sha256 from schema_migrations").fetchall()
        }
    expected_migrations = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path("db/migrations").glob("[0-9][0-9][0-9]_*.sql"))
    }
    require(applied_migrations == expected_migrations, "Applied migration names or checksums differ from repository")
    migration_names = sorted(applied_migrations)
    print("PASS: local pilot, both collectives, and schema_migrations are queryable")

    national_id = str(secrets.randbelow(9 * 10**19) + 10**19)
    owner_id, token = register_and_login(national_id)
    print("PASS: account registration, password login, and /accounts/me")

    status, _ = call("GET", "/community/collections", token="invalid-local-test-token")
    require(status == 401, "Invalid token was not rejected")
    status, _ = call("GET", "/community/collections")
    require(status == 401, "Protected route accepted a request without authentication")

    # RN-08: un hogar nuevo no participa hasta su habilitación. El verificador local
    # simula la habilitación de administración sobre su propia cuenta ficticia.
    start = datetime.now(timezone.utc) + timedelta(days=2)
    status, _ = call("POST", "/community/collections", token=token, key=f"local-verify-{secrets.token_hex(16)}", body={
        "description": "Prueba local antes de habilitar", "contact": "3000000000",
        "address": "Dirección de prueba local", "flow": "organic",
        "preferred_from": start.isoformat(), "preferred_until": (start + timedelta(hours=2)).isoformat(),
    })
    require(status == 403, f"Household outside the pilot could request a collection (HTTP {status})")
    with open_connection(database_url) as conn:
        conn.execute("update users set pilot_enabled = true where id = %s and pilot_id = %s", (owner_id, pilot_id))
    print("PASS: RN-08 household is refused until enabled for the pilot")

    requests = []
    keys = {}
    for flow in ("organic", "recyclable"):
        start = datetime.now(timezone.utc) + timedelta(days=2)
        key = f"local-verify-{secrets.token_hex(16)}"
        body = {
            "description": f"Prueba local de residuos {flow}",
            "contact": "3000000000",
            "address": "Dirección de prueba local",
            "flow": flow,
            "preferred_from": start.isoformat(),
            "preferred_until": (start + timedelta(hours=2)).isoformat(),
        }
        status, created = call("POST", "/community/collections", body=body, token=token, key=key)
        require(status == 201, f"{flow} collection request returned HTTP {status}")
        require(created.get("status") == "received", f"{flow} request has an unexpected initial status")
        request_id = created["id"]
        status, repeated = call("POST", "/community/collections", body=body, token=token, key=key)
        require(status == 201 and repeated.get("id") == request_id, f"{flow} idempotent retry mismatch")
        status, conflict = call(
            "POST", "/community/collections", body={**body, "description": body["description"] + " distinta"},
            token=token, key=key,
        )
        require(status == 409, f"{flow} key reuse with different input returned HTTP {status}")
        status, fetched = call("GET", f"/community/collections/{request_id}", token=token)
        require(status == 200 and fetched.get("id") == request_id, f"{flow} lookup failed")
        requests.append(request_id)
        keys[request_id] = (key, "huerta" if flow == "organic" else "reciclaje")
        print(f"PASS: {flow} create, own lookup, same-key retry, and conflict rejection")

    status, own = call("GET", "/community/collections", token=token)
    require(status == 200 and set(requests) <= {item["id"] for item in own}, "Own request list is incomplete")
    _, other_token = register_and_login(str(secrets.randbelow(9 * 10**19) + 10**19))
    status, hidden = call("GET", f"/community/collections/{requests[0]}", token=other_token)
    require(status == 404, "Another resident could read a private request")

    request_uuids = [UUID(value) for value in requests]
    with open_connection(database_url) as conn:
        account = conn.execute(
            "select id::text as id, document_number from users where id = %s and pilot_id = %s",
            (owner_id, pilot_id),
        ).fetchone()
        rows = conn.execute(
            """select id::text as id, client_id::text as client_id, flow, status, form, idempotency_key
               from pickup_requests where pilot_id = %s and client_id = %s and id = any(%s::uuid[])""",
            (pilot_id, owner_id, request_uuids),
        ).fetchall()
        events = conn.execute(
            """select count(*) as count from collection_events
               where pilot_id = %s and client_id = %s and request_id = any(%s::uuid[])
                 and kind = 'recibida'""",
            (pilot_id, owner_id, request_uuids),
        ).fetchone()["count"]
    require(account is not None and account["document_number"] == national_id, "Test account was not persisted")
    require(len(rows) == 2 and events == 2, "PostgreSQL rows or receipt events were not persisted exactly once")
    for row in rows:
        expected_key, expected_flow = keys[row["id"]]
        require(row["client_id"] == owner_id, "Persisted request owner mismatch")
        require(row["flow"] == expected_flow, "Request was assigned to the wrong collective flow")
        require(row["status"] == "recibida", "Persisted request status mismatch")
        expected_residue = "organico" if expected_flow == "huerta" else "reciclable"
        require(row["form"]["residuo"] == expected_residue, "Persisted waste category mismatch")
        require(row["idempotency_key"] == expected_key, "Persisted idempotency key mismatch")
    print("PASS: SQL confirms two persisted requests, correct flow, owner, keys, and one event each")

    status, _ = call("POST", "/accounts/logout", body={}, token=token)
    require(status == 204, "Logout failed")
    status, _ = call("GET", "/accounts/me", token=token)
    require(status == 401, "Logged-out session remained valid")
    print("PASS: logout revokes the session; no token or PIN was printed")
    print("Migration names:", ", ".join(sorted(migration_names)))


if __name__ == "__main__":
    main()
