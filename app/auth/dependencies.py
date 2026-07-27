from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt import verify_supabase_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Extrae y valida el usuario actual del token Bearer.

    Retorna un dict con id, email y role listos para inyectar
    con Depends(get_current_user) en cualquier endpoint protegido.
    """
    payload = verify_supabase_token(credentials.credentials)
    return {
        "id": payload["sub"],
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
    }
