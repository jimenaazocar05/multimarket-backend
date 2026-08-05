from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserMe(BaseModel):
    id: str
    name: str
    username: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserMe
