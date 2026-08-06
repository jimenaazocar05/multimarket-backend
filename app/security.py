"""Autenticación y control de acceso compartidos.

Tokens simples almacenados en memoria (dict) — suficiente para un sistema
interno. Para producción se recomienda migrar a JWT + base de datos de
tokens.
"""
import hashlib
import re
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User

# Almacén en memoria: token → user_id.
_token_store: dict[str, str] = {}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def hash_password(password: str) -> str:
    """Hashea una contraseña con bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _hash_password_sha256_legacy(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> tuple[bool, Optional[str]]:
    """Verifica `plain` contra `hashed` (bcrypt o SHA-256 legado).

    Devuelve (es_valida, nuevo_hash_bcrypt). `nuevo_hash_bcrypt` viene
    poblado cuando la verificación fue contra un hash legado válido, para
    que el caller lo persista (migración perezosa a bcrypt).
    """
    if _SHA256_RE.match(hashed):
        if _hash_password_sha256_legacy(plain) == hashed:
            return True, hash_password(plain)
        return False, None

    try:
        if bcrypt.checkpw(plain.encode(), hashed.encode()):
            return True, None
        return False, None
    except ValueError:
        return False, None


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Dependencia FastAPI: extrae y valida el usuario autenticado."""
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

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependencia FastAPI: exige que el usuario autenticado sea admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere permisos de administrador",
        )
    return user
