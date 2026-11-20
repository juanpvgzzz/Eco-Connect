from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.content.models import ContentCategory, ContentStatus


class ContentWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    category: ContentCategory
    body: str = Field(min_length=1, max_length=20000)


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: ContentCategory
    body: str
    status: ContentStatus
    author_id: str
    created_at: datetime
    updated_at: datetime
