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


def create_app(*, account_store: AccountStore | None = None) -> FastAPI:
    app = FastAPI(title="EcoConecta API", version="0.1.0")
    app.state.account_store = account_store
    app.include_router(accounts_router)

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

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
