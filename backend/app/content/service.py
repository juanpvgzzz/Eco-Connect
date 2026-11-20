from datetime import datetime, timezone
from uuid import uuid4

from backend.app.accounts.models import AccountIdentity, AccountRole
from backend.app.content.models import ContentCategory, ContentRecord, ContentStatus
from backend.app.content.ports import ContentStore


class ContentError(Exception):
    """Base class for controlled content use-case errors."""


class ForbiddenContentAction(ContentError):
    pass


class ContentNotFound(ContentError):
    pass


class ContentService:
    def __init__(self, store: ContentStore) -> None:
        self.store = store

    def list_public(
        self, category: ContentCategory | None = None
    ) -> list[ContentRecord]:
        return [
            item
            for item in self.store.list_published(category)
            if item.status is ContentStatus.PUBLISHED
            and (category is None or item.category is category)
        ]

    def get_public(self, *, content_id: str) -> ContentRecord:
        item = self.store.find_content(content_id)
        if item is None or item.status is not ContentStatus.PUBLISHED:
            raise ContentNotFound
        return item

    def list_for_admin(self, *, actor: AccountIdentity) -> list[ContentRecord]:
        self._require_admin(actor)
        return self.store.list_all()

    def create_draft(
        self,
        *,
        actor: AccountIdentity,
        title: str,
        category: ContentCategory,
        body: str,
    ) -> ContentRecord:
        self._require_admin(actor)
        now = datetime.now(timezone.utc)
        item = ContentRecord(
            id=str(uuid4()),
            title=self._required_text(title, "title"),
            category=category,
            body=self._required_text(body, "body"),
            status=ContentStatus.DRAFT,
            author_id=actor.id,
            created_at=now,
            updated_at=now,
        )
        return self.store.save_content(item)

    def update_draft(
        self,
        *,
        actor: AccountIdentity,
        content_id: str,
        title: str,
        category: ContentCategory,
        body: str,
    ) -> ContentRecord:
        self._require_admin(actor)
        item = self.store.find_content(content_id)
        if item is None:
            raise ContentNotFound
        item.title = self._required_text(title, "title")
        item.category = category
        item.body = self._required_text(body, "body")
        item.updated_at = datetime.now(timezone.utc)
        return self.store.save_content(item)

    def publish(self, *, actor: AccountIdentity, content_id: str) -> ContentRecord:
        self._require_admin(actor)
        item = self.store.find_content(content_id)
        if item is None:
            raise ContentNotFound
        item.status = ContentStatus.PUBLISHED
        item.updated_at = datetime.now(timezone.utc)
        return self.store.save_content(item)

    @staticmethod
    def _require_admin(actor: AccountIdentity) -> None:
        if actor.profile.role is not AccountRole.ADMIN:
            raise ForbiddenContentAction

    @staticmethod
    def _required_text(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field} is required")
        return value
