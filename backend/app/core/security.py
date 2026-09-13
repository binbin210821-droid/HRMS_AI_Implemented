import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, cast

import bcrypt
from fastapi import HTTPException, Response, status
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import Settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _cookie_samesite(settings: Settings) -> Literal["lax", "strict", "none"]:
    value = settings.auth_cookie_samesite.lower()
    if value not in {"lax", "strict", "none"}:
        raise ValueError("AUTH_COOKIE_SAMESITE phải là lax, strict hoặc none")
    return cast(Literal["lax", "strict", "none"], value)


def set_auth_cookies(
    response: Response,
    token: str,
    settings: Settings,
    *,
    csrf_token: str | None = None,
) -> str:
    csrf_value = csrf_token or generate_csrf_token()
    response.set_cookie(
        settings.auth_access_cookie_name,
        token,
        httponly=True,
        max_age=settings.auth_cookie_max_age,
        path="/",
        domain=settings.auth_cookie_domain or None,
        secure=settings.auth_cookie_secure,
        samesite=_cookie_samesite(settings),
    )
    set_csrf_cookie(response, settings, csrf_value)
    return csrf_value


def set_csrf_cookie(response: Response, settings: Settings, csrf_token: str) -> None:
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        max_age=settings.auth_cookie_max_age,
        path="/",
        domain=settings.auth_cookie_domain or None,
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite=_cookie_samesite(settings),
    )


def ensure_csrf_cookie(response: Response, settings: Settings, existing: str | None) -> str:
    csrf_value = existing or generate_csrf_token()
    set_csrf_cookie(response, settings, csrf_value)
    return csrf_value


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.auth_access_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain or None,
        secure=settings.auth_cookie_secure,
        samesite=_cookie_samesite(settings),
    )
    response.delete_cookie(
        settings.auth_csrf_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain or None,
        secure=settings.auth_cookie_secure,
        samesite=_cookie_samesite(settings),
    )


def create_access_token(
    subject: str,
    settings: Settings,
    expires_minutes: int | None = None,
    *,
    role: str | None = None,
    department_id: str | None = None,
    username: str | None = None,
    full_name: str | None = None,
) -> str:
    lifetime = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=lifetime)
    payload = {"sub": subject, "exp": expires_at}
    if role is not None:
        payload.update({"role": role, "department_id": department_id})
        if username is not None:
            payload["username"] = username
        if full_name is not None:
            payload["full_name"] = full_name
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.algorithm])
    except JWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thông tin đăng nhập không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token thiếu thông tin tài khoản",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
