"""Store the environmental guide in the shared content table."""

from uuid import UUID

from backend.app.content.models import ContentCategory, ContentRecord, ContentStatus
from backend.app.content.service import ContentNotFound
from db.connection import open_connection


def _content(row):
    return ContentRecord(
        id=str(row["id"]), title=row["title"], category=ContentCategory(row["category"]),
        body=row["body"], status=ContentStatus.PUBLISHED if row["status"] == "publicado"
        else ContentStatus.DRAFT, author_id=str(row["author_id"]), created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresContentStore:
    def __init__(self, url: str, pilot_id: UUID):
        self.url = url
        self.pilot_id = pilot_id

    def list_published(self, category: ContentCategory | None = None) -> list[ContentRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select * from content_entries where (pilot_id = %s or pilot_id is null)
                    and status = 'publicado' and (%s::text is null or category = %s)
                order by published_at desc, id
            """, (self.pilot_id, category, category)).fetchall()
        return [_content(row) for row in rows]

    def find_content(self, content_id: str) -> ContentRecord | None:
        with open_connection(self.url) as conn:
            row = conn.execute("""
                select * from content_entries where id::text = %s and (
                    (pilot_id = %s and status <> 'archivado')
                    or (pilot_id is null and status = 'publicado')
                )
            """, (content_id, self.pilot_id)).fetchone()
        return _content(row) if row else None

    def list_all(self) -> list[ContentRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select * from content_entries where pilot_id = %s and status <> 'archivado'
                order by updated_at desc, id
            """, (self.pilot_id,)).fetchall()
        return [_content(row) for row in rows]

    def save_content(self, content: ContentRecord) -> ContentRecord:
        status = "publicado" if content.status == ContentStatus.PUBLISHED else "borrador"
        published_at = content.updated_at if status == "publicado" else None
        with open_connection(self.url) as conn:
            row = conn.execute("""
                insert into content_entries
                    (id, pilot_id, author_id, slug, title, category, body, status,
                     published_at, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                    title = excluded.title, category = excluded.category, body = excluded.body,
                    status = case when content_entries.status = 'publicado'
                        then 'publicado' else excluded.status end,
                    updated_at = greatest(content_entries.updated_at, excluded.updated_at),
                    published_at = coalesce(content_entries.published_at, excluded.published_at)
                where content_entries.pilot_id = excluded.pilot_id
                returning *
            """, (content.id, self.pilot_id, content.author_id, content.id, content.title,
                  content.category, content.body, status, published_at, content.created_at,
                  content.updated_at)).fetchone()
        if row is None:
            raise ContentNotFound
        return _content(row)
