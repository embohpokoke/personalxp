from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


EnteredBy = Literal["primary", "secondary"]


class LoginRequest(BaseModel):
    pin: str = Field(min_length=1, max_length=64)
    entered_by: EnteredBy | None = None


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    role: str


class AuthResponse(BaseModel):
    user: UserPublic
    entered_by: EnteredBy | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["expense", "income"]
    icon: str | None = Field(default=None, max_length=16)


class CategoryPublic(BaseModel):
    id: int
    name: str
    type: Literal["expense", "income"]
    icon: str | None = None
    is_custom: bool
    created_at: datetime


class ReceiptPublic(BaseModel):
    id: int
    file_path: str
    mime_type: str | None = None
    byte_size: int | None = None
    uploaded_at: datetime
    expires_at: datetime


class TransactionPublic(BaseModel):
    id: int
    user_id: int
    entered_by: EnteredBy | None = None
    source_agent: str | None = None
    type: Literal["expense", "income"]
    amount: Decimal
    currency: str
    exchange_rate: Decimal
    amount_idr: Decimal
    category_id: int | None = None
    category: str | None = None
    description: str | None = None
    merchant: str | None = None
    source_extra: dict[str, Any] | None = None
    txn_date: date
    is_recurring: bool
    recurring_pattern: str | None = None
    created_at: datetime
    receipt: ReceiptPublic | None = None


class TransactionListResponse(BaseModel):
    items: list[TransactionPublic]
    limit: int
    offset: int
    total: int


class TransactionCreateResponse(BaseModel):
    id: int
    message: str
    transaction: TransactionPublic


class TransactionPatch(BaseModel):
    entered_by: EnteredBy | None = None
    type: Literal["expense", "income"] | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    category_id: int | None = None
    category: str | None = Field(default=None, max_length=80)
    description: str | None = None
    merchant: str | None = None
    source_extra: dict[str, Any] | None = None
    txn_date: date | None = None
    is_recurring: bool | None = None
    recurring_pattern: str | None = None


class BudgetCreate(BaseModel):
    category_id: int
    limit_amount: Decimal = Field(ge=0)
    period: Literal["weekly", "monthly"]
    start_date: date
    end_date: date | None = None
    alert_telegram: bool = True


class BudgetPublic(BaseModel):
    id: int
    category_id: int
    category: str
    limit_amount: Decimal
    period: Literal["weekly", "monthly"]
    start_date: date
    end_date: date | None = None
    alert_telegram: bool
    created_at: datetime


class CategoryTotal(BaseModel):
    category_id: int | None = None
    category: str
    type: Literal["expense", "income"]
    total_idr: Decimal
    count: int


class ReportSummary(BaseModel):
    period: Literal["weekly", "monthly", "custom"]
    start_date: date
    end_date: date
    income_idr: Decimal
    expense_idr: Decimal
    net_idr: Decimal
    transaction_count: int
    category_totals: list[CategoryTotal]
    insights: list[str]
