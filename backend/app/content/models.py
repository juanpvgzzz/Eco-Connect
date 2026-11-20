from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ContentCategory(StrEnum):
    MATERIALS = "materials"
    SEPARATION = "separation"
    GARDEN = "garden"
    ROUTES = "routes"
    SCHEDULES = "schedules"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(slots=True)
class ContentRecord:
    id: str
    title: str
    category: ContentCategory
    body: str
    status: ContentStatus
    author_id: str
    created_at: datetime
    updated_at: datetime
