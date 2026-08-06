"""Router de autenticación: login, logout y /me.

Usa tokens simples almacenados en memoria (dict). Para producción se
recomienda migrar a JWT + base de datos de tokens.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserMe
from app.security import _token_store, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Valida credenciales y emite un token de sesión."""
    from sqlalchemy import func
    user: Optional[User] = (
        db.query(User).filter(func.lower(User.username) == datos.username.strip().lower()).first()
    )

    if not user or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    valid, rehash = verify_password(datos.password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if rehash:
        # Migración perezosa: el usuario tenía un hash SHA-256 legado.
        user.password_hash = rehash
        db.commit()

    token = secrets.token_urlsafe(32)
    _token_store[token] = str(user.id)

    return TokenResponse(
        access_token=token,
        user=UserMe(
            id=str(user.id),
            name=user.name,
            username=user.username,
            role=user.role,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str) -> None:
    """Invalida el token de sesión."""
    _token_store.pop(token, None)


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)) -> UserMe:
    """Devuelve el usuario autenticado actual."""
    return UserMe(id=str(user.id), name=user.name, username=user.username, role=user.role)
