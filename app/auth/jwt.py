import jwt
from fastapi import HTTPException, status
from app.config import settings


def verify_supabase_token(token: str) -> dict:
    """Decodifica y verifica la firma del JWT emitido por Supabase Auth."""
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
