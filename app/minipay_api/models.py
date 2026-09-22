from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CustomerCreate(BaseModel):
    customer_ref: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)


class CustomerOut(BaseModel):
    id: int
    customer_ref: str
    name: str
    created_at: datetime


class PaymentCreate(BaseModel):
    customer_ref: str = Field(min_length=1, max_length=40)
    amount: Decimal = Field(gt=0)
    transaction_ref: Optional[str] = Field(default=None, max_length=50)

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class PaymentOut(BaseModel):
    id: int
    transaction_ref: str
    customer_id: int
    amount: Decimal
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    failure_code: Optional[str]
    idempotent_replay: bool = False
