from typing import Protocol

from backend.app.content.models import ContentCategory, ContentRecord


class ContentStore(Protocol):
    """Persistence contract owned by the shared PostgreSQL integration."""

    def list_published(
        self, category: ContentCategory | None = None
    ) -> list[ContentRecord]: ...

    def find_content(self, content_id: str) -> ContentRecord | None: ...

    def list_all(self) -> list[ContentRecord]: ...

    def save_content(self, content: ContentRecord) -> ContentRecord: ...
