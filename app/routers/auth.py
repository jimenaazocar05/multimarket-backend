"""Router de autenticación: login, logout y /me.

Usa tokens simples almacenados en memoria (dict). Para producción se
recomienda migrar a JWT + base de datos de tokens.
"""
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserMe

router = APIRouter(prefix="/auth", tags=["auth"])

# Almacén en memoria: token → user_id. Suficiente para un sistema interno.
_token_store: dict[str, str] = {}


def _hash_password(password: str) -> str:
    """SHA-256 simple. Para producción usar bcrypt/argon2."""
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(plain: str, hashed: str) -> bool:
    return _hash_password(plain) == hashed


def get_current_user_id(authorization: Optional[str] = None) -> str:
    """Extrae el user_id del token. Usado por dependencias de otros routers."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    user_id = _token_store.get(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Valida credenciales y emite un token de sesión."""
    from sqlalchemy import func
    user: Optional[User] = (
        db.query(User).filter(func.lower(User.username) == datos.username.strip().lower()).first()
    )

    if not user or not user.active or not _verify_password(datos.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = secrets.token_urlsafe(32)
    _token_store[token] = str(user.id)

    return TokenResponse(
        access_token=token,
        user=UserMe(
            id=str(user.id),
            name=user.name,
            username=user.username,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str) -> None:
    """Invalida el token de sesión."""
    _token_store.pop(token, None)


@router.get("/me", response_model=UserMe)
def me(authorization: Optional[str] = None, db: Session = Depends(get_db)) -> UserMe:
    """Devuelve el usuario autenticado actual."""
    from fastapi import Request

    user_id = get_current_user_id(authorization)
    user: Optional[User] = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return UserMe(id=str(user.id), name=user.name, username=user.username)
