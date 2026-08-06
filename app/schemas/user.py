from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

ROLES = ("admin", "vendedor")


class UserCreate(BaseModel):
    name: str
    username: str
    password: str
    role: str = Field(default="vendedor")


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    name: str
    username: str
    role: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True
