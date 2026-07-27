from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Retorna la información del usuario autenticado extraída del JWT."""
    return user
