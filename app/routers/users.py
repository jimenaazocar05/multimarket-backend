from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from uuid import UUID

from app.db import get_db
from app.models.user import User
from app.schemas.user import ROLES, UserCreate, UserOut, UserUpdate
from app.security import hash_password, require_admin

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.name).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(datos: UserCreate, db: Session = Depends(get_db)):
    if datos.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Debe ser uno de: {', '.join(ROLES)}")

    existing = db.query(User).filter(func.lower(User.username) == datos.username.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")

    user = User(
        name=datos.name,
        username=datos.username.strip(),
        password_hash=hash_password(datos.password),
        role=datos.role,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    datos: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    is_self = user.id == current.id
    if datos.role is not None:
        if datos.role not in ROLES:
            raise HTTPException(status_code=400, detail=f"Rol inválido. Debe ser uno de: {', '.join(ROLES)}")
        if is_self and datos.role != "admin":
            raise HTTPException(status_code=400, detail="No puedes quitarte tu propio rol de administrador")
        user.role = datos.role

    if datos.active is not None:
        if is_self and not datos.active:
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")
        user.active = datos.active

    if datos.name is not None:
        user.name = datos.name

    if datos.password:
        user.password_hash = hash_password(datos.password)

    db.commit()
    db.refresh(user)
    return user
