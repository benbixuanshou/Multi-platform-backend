"""Auth routes — register, login, refresh, logout."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/register")
async def register():
    ...


@router.post("/login")
async def login():
    ...


@router.post("/refresh")
async def refresh():
    ...


@router.post("/logout")
async def logout():
    ...
