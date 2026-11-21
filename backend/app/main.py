import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.app.accounts.dependencies import get_current_identity
from backend.app.accounts.models import AccountIdentity
from backend.app.accounts.ports import AccountStore
from backend.app.accounts.router import router as accounts_router
from backend.app.accounts.service import (
    AccountAlreadyExists,
    AccountError,
    AccountNotFound,
    ForbiddenAction,
    InvalidCredentials,
    InvalidSession,
    TooManyLoginAttempts,
)
from backend.app.collections.api import router as collections_router
from backend.app.collections.service import Collections, Problem
from backend.app.community.ports import CommunityCollectionsGateway, CommunityPointsGateway
from backend.app.community.router import router as community_router
from backend.app.community.service import (
    CommunityError,
    CommunityInsufficientPoints,
    CommunityNotEligible,
    CommunityNotFound,
    IntegrationContractError,
)
from backend.app.content.ports import ContentStore
from backend.app.content.router import router as content_router
from backend.app.content.service import ContentError, ContentNotFound, ForbiddenContentAction
from backend.app.errors import InvalidInput


def create_app(
    *,
    account_store: AccountStore | None = None,
    content_store: ContentStore | None = None,
    collections_gateway: CommunityCollectionsGateway | None = None,
    points_gateway: CommunityPointsGateway | None = None,
    database_url: str | None = None,
    pilot_id: UUID | None = None,
) -> FastAPI:
    app = FastAPI(title="EcoConecta API", version="0.1.0")
    if database_url:
        if pilot_id is None:
            raise ValueError("ECO_PILOT_ID is required when DATABASE_URL is configured")
        from backend.app.accounts.postgres_store import PostgresAccountStore
        from backend.app.collections.postgres import PostgresCollections
        from backend.app.community.postgres import PostgresCommunityCollections, PostgresCommunityPoints
        from backend.app.content.postgres_store import PostgresContentStore

        persistence = PostgresCollections(database_url, pilot_id)
        collections = Collections(persistence.transaction)

        def current_collection_actor(
            identity: Annotated[AccountIdentity, Depends(get_current_identity)],
        ):
            return persistence.actor(identity)

        account_store = account_store or PostgresAccountStore(database_url, pilot_id)
        content_store = content_store or PostgresContentStore(database_url, pilot_id)
        collections_gateway = collections_gateway or PostgresCommunityCollections(
            database_url, pilot_id, collections,
        )
        points_gateway = points_gateway or PostgresCommunityPoints(database_url, pilot_id)
        app.include_router(collections_router(collections, current_collection_actor))

    app.state.account_store = account_store
    app.state.content_store = content_store
    app.state.collections_gateway = collections_gateway
    app.state.points_gateway = points_gateway
    app.include_router(accounts_router)
    app.include_router(content_router)
    app.include_router(community_router)

    @app.exception_handler(Problem)
    async def collection_error_handler(request: Request, exc: Problem) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's input can include submitted PINs or entire request bodies.
        errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(AccountError)
    async def account_error_handler(request: Request, exc: AccountError) -> JSONResponse:
        if isinstance(exc, AccountAlreadyExists):
            status_code, detail = 409, "An account with this national ID already exists"
        elif isinstance(exc, InvalidCredentials):
            status_code, detail = 401, "Invalid national ID or PIN"
        elif isinstance(exc, TooManyLoginAttempts):
            status_code, detail = 429, "Too many login attempts; try again later"
        elif isinstance(exc, InvalidSession):
            status_code, detail = 401, "Invalid or expired session"
        elif isinstance(exc, ForbiddenAction):
            status_code, detail = 403, "Insufficient permissions"
        elif isinstance(exc, AccountNotFound):
            status_code, detail = 404, "Account not found"
        else:
            status_code, detail = 400, "Account request could not be completed"
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)

    @app.exception_handler(InvalidInput)
    async def invalid_input_handler(request: Request, exc: InvalidInput) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": "Invalid request"})

    @app.exception_handler(ContentError)
    async def content_error_handler(request: Request, exc: ContentError) -> JSONResponse:
        if isinstance(exc, ForbiddenContentAction):
            status_code, detail = 403, "Insufficient permissions"
        elif isinstance(exc, ContentNotFound):
            status_code, detail = 404, "Content not found"
        else:
            status_code, detail = 400, "Content request could not be completed"
        return JSONResponse(status_code=status_code, content={"detail": detail})

    @app.exception_handler(CommunityError)
    async def community_error_handler(request: Request, exc: CommunityError) -> JSONResponse:
        if isinstance(exc, CommunityNotEligible):
            status_code, detail = 403, "This business is not enabled for the pilot"
        elif isinstance(exc, CommunityInsufficientPoints):
            status_code, detail = 409, "Not enough points for this reward"
        elif isinstance(exc, CommunityNotFound):
            status_code, detail = 404, "Community resource not found"
        elif isinstance(exc, IntegrationContractError):
            status_code, detail = 502, "A connected module returned invalid ownership data"
        else:
            status_code, detail = 400, "Community request could not be completed"
        return JSONResponse(status_code=status_code, content={"detail": detail})

    # The production image serves the compiled React app from this same service.
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


def create_configured_app() -> FastAPI:
    database_url = os.environ.get("DATABASE_URL")
    configured_pilot = os.environ.get("ECO_PILOT_ID")
    if not database_url:
        return create_app()
    if not configured_pilot:
        raise ValueError("ECO_PILOT_ID is required when DATABASE_URL is configured")
    return create_app(database_url=database_url, pilot_id=UUID(configured_pilot))


app = create_configured_app()
