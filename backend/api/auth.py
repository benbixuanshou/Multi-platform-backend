"""Auth routes — register, login, refresh, logout."""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import security_scheme
from core.database import get_db
from core.rate_limit import login_rate_limit, register_rate_limit
from core.redis_client import redis
from core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from models.user import User
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db), _rate=Depends(register_rate_limit)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Registration failed")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token_data = {"sub": user.id}
    return TokenResponse(
        user_id=user.id,
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db), _rate=Depends(login_rate_limit)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token_data = {"sub": user.id}
    return TokenResponse(
        user_id=user.id,
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=401, detail="User not found")
    token_data = {"sub": user_id}
    return TokenResponse(
        user_id=user_id,
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


async def require_auth_header(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> str:
    return credentials.credentials


@router.post("/logout", status_code=204)
async def logout(token: str = Depends(require_auth_header)):
    payload = decode_token(token)
    if payload:
        ttl = payload.get("exp", 0) - int(time.time())
        if ttl > 0:
            await redis.setex(f"bl:{token}", ttl, "1")
    return None
