"""Explicitly validated request / response models."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from .config import MAX_QUANTITY

Category = Literal["sweet", "savoury", "drink", "healthy-ish"]
Status = Literal["stocked", "running_low", "gone"]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: Literal["admin", "member"]
    model_config = ConfigDict(from_attributes=True)


class LoginOut(BaseModel):
    token: str
    user: UserOut


class SnackBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    category: Category
    low_stock_threshold: int = Field(default=5, ge=0, le=MAX_QUANTITY)

    @field_validator("name")
    @classmethod
    def trim_name(cls, name: str):
        value = name.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class SnackCreate(SnackBase):
    quantity: int = Field(default=0, ge=0, le=MAX_QUANTITY)


class SnackPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Intentionally excludes quantity: stock changes must be audited by restock/consume.
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: Category | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0, le=MAX_QUANTITY)

    @field_validator("name")
    @classmethod
    def trim_name(cls, name: str | None):
        if name is None:
            return name
        value = name.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class AmountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: int = Field(ge=1, le=MAX_QUANTITY)


class SnackOut(BaseModel):
    id: int
    name: str
    category: Category
    quantity: int
    low_stock_threshold: int
    status: Status
    votes: int
    has_voted: bool


class SnackPage(BaseModel):
    items: list[SnackOut]
    total: int
    page: int
    page_size: int
    pages: int


class WinnerOut(BaseModel):
    id: int
    name: str
    category: Category
    votes_this_week: int


class SummaryOut(BaseModel):
    stocked: int
    running_low: int
    gone: int
    total: int
    snack_of_the_week: WinnerOut | None


class ActivityOut(BaseModel):
    id: int
    user_name: str
    snack_name: str
    action: Literal["consumed", "restocked"]
    amount: int
    created_at: str


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    page: int
    page_size: int
    pages: int
