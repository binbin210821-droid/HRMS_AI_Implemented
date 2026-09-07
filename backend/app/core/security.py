from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
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
