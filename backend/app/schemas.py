import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import get_settings
from app.models import ComfortTier, ReviewLanguage, ReviewStatus, TravellerType


class GuestReviewCreate(BaseModel):
    destination_id: uuid.UUID
    client_draft_id: uuid.UUID
    guest_scope_secret: str = Field(min_length=43, max_length=200, repr=False)
    guest_display_name: str = Field(min_length=1, max_length=80)
    language: ReviewLanguage
    traveller_type: TravellerType
    comfort_tier: ComfortTier
    visit_month: date
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=20, max_length=6000)
    overall_rating: int = Field(ge=1, le=5)
    consent_version: str = Field(min_length=1, max_length=40)

    @field_validator("visit_month")
    @classmethod
    def first_day_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("visit_month must use the first day of its month")
        display_tz = get_settings().display_tz
        current_month = datetime.now(display_tz).date().replace(day=1)
        if value > current_month:
            raise ValueError(f"visit_month cannot be in the future in {display_tz.key}")
        return value


class GuestReviewCreated(BaseModel):
    review_id: uuid.UUID
    status: ReviewStatus
    version: int
    receipt_token: str = Field(repr=False)
    duplicate_recovered: bool


class ModerationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    decision: Literal["PUBLISH", "REJECT", "HIDE", "RESTORE"]
    reason_code: str = Field(min_length=2, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class ModerationResult(BaseModel):
    review_id: uuid.UUID
    status: ReviewStatus
    version: int
    counted_rating: int | None


class ConflictFlagRequest(BaseModel):
    expected_version: int = Field(ge=1)
    conflict_declared: bool
    reason_code: str = Field(min_length=2, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class ReceiptExchange(BaseModel):
    review_id: uuid.UUID
    receipt_token: str = Field(min_length=40, max_length=200, repr=False)


class ReceiptStatus(BaseModel):
    review_id: uuid.UUID
    status: ReviewStatus
    version: int
    published_at: datetime | None


class WithdrawRequest(BaseModel):
    expected_version: int = Field(ge=1)
    receipt_token: str = Field(min_length=40, max_length=200, repr=False)


class PublicReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    guest_display_name: str | None
    status: ReviewStatus
    overall_rating: int
    published_at: datetime
    title: str
    body: str


class ReviewFeed(BaseModel):
    items: list[PublicReview]
    next_cursor: str | None
    guest_rating_average: float | None
    guest_rating_count: int


class HealthResponse(BaseModel):
    status: str

