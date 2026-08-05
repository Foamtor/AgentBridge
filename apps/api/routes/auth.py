"""Local console administrator authentication endpoints."""

from __future__ import annotations

from typing import Literal

from auth.local_admin import AuthSessionError, PasswordPolicyError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=512)


class SessionPublic(BaseModel):
    status: Literal["anonymous", "password_change_required", "authenticated"]
    username: str | None = None
    permissions: list[str] | None = None


def _service(request: Request):
    service = getattr(request.app.state, "console_auth_service", None)
    if service is None:
        raise HTTPException(status_code=404, detail={"code": "auth_unavailable"})
    return service


def _session_token(request: Request) -> str:
    name = request.app.state.settings.auth_cookie_name
    return str(request.cookies.get(name) or "")


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin != expected:
        raise HTTPException(status_code=403, detail={"code": "cross_site_request"})


def _set_cookie(response: Response, request: Request, token: str, max_age: int) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.headers["Cache-Control"] = "no-store"


async def _public_session(request: Request) -> SessionPublic:
    token = _session_token(request)
    if not token:
        return SessionPublic(status="anonymous")
    record = await _service(request).get_session(token)
    if not record:
        return SessionPublic(status="anonymous")
    if record["kind"] == "password_change":
        return SessionPublic(status="password_change_required", username=record["username"])
    return SessionPublic(status="authenticated", username=record["username"], permissions=["*"])


@router.get("/session", response_model=SessionPublic, response_model_exclude_none=True)
async def session(request: Request) -> SessionPublic:
    return await _public_session(request)


@router.post("/login", response_model=SessionPublic, response_model_exclude_none=True)
async def login(body: LoginBody, request: Request, response: Response) -> SessionPublic:
    _same_origin(request)
    bucket = f"{request.client.host if request.client else 'unknown'}:{body.username.casefold()}"
    try:
        authenticated = await _service(request).authenticate(
            body.username, body.password, bucket_key=bucket
        )
    except AuthSessionError as exc:
        status = 429 if str(exc) == "auth_rate_limited" else 401
        raise HTTPException(status_code=status, detail={"code": str(exc)}) from exc
    _set_cookie(
        response,
        request,
        authenticated.token,
        request.app.state.settings.auth_password_change_seconds
        if authenticated.kind == "password_change"
        else request.app.state.settings.auth_session_absolute_seconds,
    )
    return SessionPublic(
        status="password_change_required" if authenticated.kind == "password_change" else "authenticated",
        username=authenticated.username,
        permissions=["*"] if authenticated.kind == "authenticated" else None,
    )


@router.post("/change-password", response_model=SessionPublic, response_model_exclude_none=True)
async def change_password(
    body: ChangePasswordBody, request: Request, response: Response
) -> SessionPublic:
    _same_origin(request)
    try:
        changed = await _service(request).change_password(
            session_token=_session_token(request),
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code}) from exc
    except AuthSessionError as exc:
        raise HTTPException(status_code=401, detail={"code": str(exc)}) from exc
    _set_cookie(response, request, changed.token, request.app.state.settings.auth_session_absolute_seconds)
    return SessionPublic(status="authenticated", username=changed.username, permissions=["*"])


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> Response:
    _same_origin(request)
    token = _session_token(request)
    if token:
        await _service(request).logout(token)
    response.delete_cookie(request.app.state.settings.auth_cookie_name, path="/")
    response.headers["Cache-Control"] = "no-store"
    response.status_code = 204
    return response
