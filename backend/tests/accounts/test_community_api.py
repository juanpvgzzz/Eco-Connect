from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.app.accounts.models import AccountKind, AccountRole
from backend.app.community.ports import BusinessNotEnabled, InsufficientPoints
from backend.app.main import create_app
from backend.tests.accounts.test_service import MemoryAccountStore
from backend.tests.accounts.test_api import register


def future_window():
    start = datetime.now(timezone.utc) + timedelta(days=2)
    return start.isoformat(), (start + timedelta(hours=2)).isoformat()


@dataclass
class FakeAppointment:
    scheduled_at: datetime
    responsible_name: str


@dataclass
class FakeCollection:
    id: str
    owner_id: str
    status: str
    description: str
    address: str
    created_at: datetime
    appointment: FakeAppointment | None = None


@dataclass
class FakeNotification:
    id: str
    owner_id: str
    title: str
    message: str
    created_at: datetime


@dataclass
class FakePoints:
    owner_id: str
    balance: int


@dataclass
class FakeMovement:
    id: str
    owner_id: str
    points: int
    reason: str
    created_at: datetime


@dataclass
class FakeReward:
    id: str
    title: str
    description: str
    cost: int


@dataclass
class FakeRedemption:
    owner_id: str
    code: str
    reward_id: str
    reward_title: str
    expires_at: datetime


class FakeCollectionsGateway:
    def __init__(self):
        now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        self.created_by = []
        self.own = FakeCollection(
            "req-own", "user-id", "scheduled", "Botellas plásticas", "Calle 1", now,
            FakeAppointment(datetime(2026, 11, 20, 19, tzinfo=timezone.utc), "Equipo A"),
        )
        self.other = FakeCollection(
            "req-other", "someone-else", "received", "Dato ajeno", "Calle privada", now
        )

    def create_for_user(self, actor, request):
        if actor.profile.kind is AccountKind.BUSINESS and not actor.profile.pilot_enabled:
            raise BusinessNotEnabled
        self.created_by.append((actor.id, request))
        return FakeCollection(
            "req-new", actor.id, "received", request.description, request.address,
            datetime.now(timezone.utc),
        )

    def list_for_user(self, owner_id):
        self.requested_owner_id = owner_id
        return [self.own, self.other]

    def get_for_user(self, owner_id, request_id):
        self.requested_owner_id = owner_id
        return {"req-own": self.own, "req-other": self.other}.get(request_id)

    def list_notifications_for_user(self, owner_id):
        self.requested_owner_id = owner_id
        now = datetime.now(timezone.utc)
        return [
            FakeNotification("note-own", owner_id, "Agenda", "Tu cita está lista", now),
            FakeNotification("note-other", "someone-else", "Privada", "Secreto", now),
        ]

    def list_appointments_for_user(self, owner_id):
        self.requested_owner_id = owner_id
        return [self.own, self.other]


class FakePointsGateway:
    def __init__(self):
        self.code_requests = []
        self.debit_calls = 0
        self.insufficient = False
        self.reward = FakeReward("reward-1", "Abono", "Abono orgánico", 25)

    def get_points_for_user(self, owner_id):
        self.requested_owner_id = owner_id
        return FakePoints(owner_id, 100)

    def list_movements_for_user(self, owner_id):
        self.requested_owner_id = owner_id
        now = datetime.now(timezone.utc)
        return [
            FakeMovement("move-own", owner_id, 10, "Recolección", now),
            FakeMovement("move-other", "someone-else", 50, "Privado", now),
        ]

    def list_rewards(self):
        return [self.reward]

    def request_code_for_user(self, owner_id, reward_id):
        if self.insufficient:
            raise InsufficientPoints
        self.code_requests.append((owner_id, reward_id))
        return FakeRedemption(
            owner_id, "EC-12345", reward_id, self.reward.title,
            datetime(2026, 11, 21, 17, tzinfo=timezone.utc),
        )


def make_client(kind="household"):
    account_store = MemoryAccountStore()
    collections = FakeCollectionsGateway()
    points = FakePointsGateway()
    app = create_app(
        account_store=account_store,
        collections_gateway=collections,
        points_gateway=points,
    )
    from fastapi.testclient import TestClient

    client = TestClient(app)
    register(client, national_id="123456789", kind=kind)
    user = account_store.find_by_national_id("123456789")
    user.id = "user-id"
    login = client.post(
        "/accounts/login", json={"national_id": "123456789", "pin": "1234"}
    )
    return client, collections, points, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_collection_create_and_lists_are_limited_to_current_user():
    client, collections, _, headers = make_client()
    start, end = future_window()
    response = client.post(
        "/community/collections",
        json={
            "description": "Botellas plásticas limpias",
            "contact": "3001234567",
            "address": "Calle 1 # 2-3",
            "preferred_from": start,
            "preferred_until": end,
        },
        headers=headers,
    )

    assert response.status_code == 201
    assert collections.created_by[0][0] == "user-id"
    listed = client.get("/community/collections?owner_id=someone-else", headers=headers)
    assert [item["id"] for item in listed.json()] == ["req-own"]
    assert collections.requested_owner_id == "user-id"
    assert client.get("/community/collections/req-other", headers=headers).status_code == 404


def test_collection_rejects_invalid_availability():
    client, _, _, headers = make_client()
    start, end = future_window()
    response = client.post(
        "/community/collections",
        json={
            "description": "Botellas",
            "contact": "3001234567",
            "address": "Calle 1",
            "preferred_from": end,
            "preferred_until": start,
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_non_pilot_business_is_rejected_by_collections_contract():
    client, _, _, headers = make_client(kind="business")
    start, end = future_window()
    response = client.post(
        "/community/collections",
        json={
            "description": "Botellas plásticas limpias",
            "contact": "3001234567",
            "address": "Calle 1 # 2-3",
            "preferred_from": start,
            "preferred_until": end,
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_collection_rejects_past_availability():
    client, _, _, headers = make_client()
    response = client.post(
        "/community/collections",
        json={
            "description": "Botellas",
            "contact": "3001234567",
            "address": "Calle 1",
            "preferred_from": "2020-01-01T09:00:00-05:00",
            "preferred_until": "2020-01-01T11:00:00-05:00",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_appointments_show_barranquilla_time_and_only_own_notifications():
    client, _, _, headers = make_client()
    appointments = client.get("/community/appointments", headers=headers)
    notifications = client.get("/community/notifications", headers=headers)

    assert appointments.status_code == 200
    assert appointments.json()[0]["scheduled_at"] == "2026-11-20T14:00:00-05:00"
    assert notifications.status_code == 200
    assert [item["id"] for item in notifications.json()] == ["note-own"]


def test_points_history_is_private_and_redemption_code_does_not_debit():
    client, _, points, headers = make_client()
    balance = client.get("/community/points", headers=headers)
    movements = client.get("/community/points/movements", headers=headers)
    rewards = client.get("/community/rewards", headers=headers)
    redemption = client.post(
        "/community/redemptions", json={"reward_id": "reward-1"}, headers=headers
    )

    assert balance.json()["balance"] == 100
    assert [item["id"] for item in movements.json()] == ["move-own"]
    assert rewards.json()[0]["id"] == "reward-1"
    assert redemption.status_code == 201
    assert redemption.json()["code"] == "EC-12345"
    assert points.code_requests == [("user-id", "reward-1")]
    assert points.debit_calls == 0


def test_insufficient_points_is_a_controlled_conflict():
    client, _, points, headers = make_client()
    points.insufficient = True

    response = client.post(
        "/community/redemptions", json={"reward_id": "reward-1"}, headers=headers
    )

    assert response.status_code == 409
