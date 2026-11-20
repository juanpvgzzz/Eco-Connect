from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
) -> FastAPI:
    app = FastAPI(title="EcoConecta API", version="0.1.0")
    app.state.account_store = account_store
    app.state.content_store = content_store
    app.state.collections_gateway = collections_gateway
    app.state.points_gateway = points_gateway
    app.include_router(accounts_router)
    app.include_router(content_router)
    app.include_router(community_router)

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

    return app


app = create_app()
