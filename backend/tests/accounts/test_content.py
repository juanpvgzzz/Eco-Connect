from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from backend.app.accounts.models import AccountIdentity, AccountProfile, AccountKind, AccountRole
from backend.app.content.models import ContentCategory, ContentStatus
from backend.app.content.service import ContentService, ForbiddenContentAction, ContentNotFound


@dataclass
class MemoryContent:
    id: str
    title: str
    category: ContentCategory
    body: str
    status: ContentStatus
    author_id: str
    created_at: datetime
    updated_at: datetime


class MemoryContentStore:
    def __init__(self):
        self.items = {}

    def list_published(self, category=None):
        return [
            item
            for item in self.items.values()
            if item.status is ContentStatus.PUBLISHED
            and (category is None or item.category is category)
        ]

    def find_content(self, content_id):
        return self.items.get(content_id)

    def save_content(self, content):
        self.items[content.id] = content
        return content

    def list_all(self):
        return list(self.items.values())


@pytest.fixture
def admin():
    return AccountIdentity(
        id="admin-id",
        profile=AccountProfile(
            national_id="1",
            full_name="Admin",
            address="Centro",
            phone="3000000000",
            kind=AccountKind.HOUSEHOLD,
            role=AccountRole.ADMIN,
            pilot_enabled=False,
        ),
    )


@pytest.fixture
def resident():
    return AccountIdentity(
        id="resident-id",
        profile=AccountProfile(
            national_id="2",
            full_name="Vecina",
            address="Barrio",
            phone="3000000001",
            kind=AccountKind.HOUSEHOLD,
            role=AccountRole.RESIDENT,
            pilot_enabled=False,
        ),
    )


def test_drafts_are_hidden_until_published(admin):
    store = MemoryContentStore()
    service = ContentService(store)
    draft = service.create_draft(
        actor=admin,
        title="Separar residuos",
        category=ContentCategory.SEPARATION,
        body="Lava y separa los materiales reciclables.",
    )

    assert service.list_public() == []
    service.publish(actor=admin, content_id=draft.id)
    assert service.list_public() == [draft]


def test_public_listing_filters_drafts_even_if_store_returns_them(admin):
    store = MemoryContentStore()
    service = ContentService(store)
    draft = service.create_draft(
        actor=admin,
        title="Horario en borrador",
        category=ContentCategory.SCHEDULES,
        body="Este contenido aún no está aprobado.",
    )
    store.list_published = lambda category=None: list(store.items.values())

    assert service.list_public() == []


def test_non_admin_cannot_manage_or_read_drafts(admin, resident):
    service = ContentService(MemoryContentStore())
    draft = service.create_draft(
        actor=admin,
        title="Huerta en casa",
        category=ContentCategory.GARDEN,
        body="Usa recipientes con drenaje.",
    )

    with pytest.raises(ForbiddenContentAction):
        service.publish(actor=resident, content_id=draft.id)
    with pytest.raises(ContentNotFound):
        service.get_public(content_id=draft.id)
