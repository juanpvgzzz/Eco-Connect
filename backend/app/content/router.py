from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.accounts.dependencies import get_current_identity
from backend.app.accounts.models import AccountIdentity
from backend.app.content.models import ContentCategory, ContentRecord
from backend.app.content.ports import ContentStore
from backend.app.content.schemas import ContentResponse, ContentWriteRequest
from backend.app.content.service import ContentNotFound, ContentService


router = APIRouter(prefix="/content", tags=["content"])


def get_content_service(request: Request) -> ContentService:
    service = getattr(request.app.state, "content_service", None)
    if service is not None:
        return service
    store: ContentStore | None = getattr(request.app.state, "content_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Content persistence is not configured",
        )
    service = ContentService(store)
    request.app.state.content_service = service
    return service


@router.get("", response_model=list[ContentResponse])
def list_published_content(
    category: ContentCategory | None = None,
    service: ContentService = Depends(get_content_service),
) -> list[ContentRecord]:
    return service.list_public(category)


@router.get("/admin", response_model=list[ContentResponse])
def list_content_for_admin(
    actor: AccountIdentity = Depends(get_current_identity),
    service: ContentService = Depends(get_content_service),
) -> list[ContentRecord]:
    return service.list_for_admin(actor=actor)


@router.get("/{content_id}", response_model=ContentResponse)
def get_published_content(
    content_id: str,
    service: ContentService = Depends(get_content_service),
) -> ContentRecord:
    try:
        return service.get_public(content_id=content_id)
    except ContentNotFound:
        raise HTTPException(status_code=404, detail="Content not found") from None


@router.post(
    "/admin",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_draft(
    request: ContentWriteRequest,
    actor: AccountIdentity = Depends(get_current_identity),
    service: ContentService = Depends(get_content_service),
) -> ContentRecord:
    return service.create_draft(actor=actor, **request.model_dump())


@router.put("/admin/{content_id}", response_model=ContentResponse)
def update_draft(
    content_id: str,
    request: ContentWriteRequest,
    actor: AccountIdentity = Depends(get_current_identity),
    service: ContentService = Depends(get_content_service),
) -> ContentRecord:
    return service.update_draft(
        actor=actor, content_id=content_id, **request.model_dump()
    )


@router.post("/admin/{content_id}/publish", response_model=ContentResponse)
def publish_content(
    content_id: str,
    actor: AccountIdentity = Depends(get_current_identity),
    service: ContentService = Depends(get_content_service),
) -> ContentRecord:
    return service.publish(actor=actor, content_id=content_id)
