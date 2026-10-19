import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import get_settings
from app.models import (
    AdvisorySeverity,
    ComfortTier,
    ContactKind,
    GuideCategory,
    ReviewLanguage,
    ReviewStatus,
    SourceType,
    TravellerType,
)


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GuestReviewCreate(StrictRequestModel):
    destination_id: uuid.UUID
    client_draft_id: uuid.UUID
    guest_scope_secret: str = Field(min_length=43, max_length=200, repr=False)
    receipt_secret: str = Field(min_length=1, max_length=100, repr=False)
    turnstile_token: str | None = Field(default=None, max_length=2048, repr=False)
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
    duplicate_recovered: bool


class ModerationRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    decision: Literal["PUBLISH", "REJECT", "HIDE", "RESTORE"]
    reason_code: str = Field(min_length=2, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class ModerationResult(BaseModel):
    review_id: uuid.UUID
    status: ReviewStatus
    version: int
    counted_rating: int | None


class ConflictFlagRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    conflict_declared: bool
    reason_code: str = Field(min_length=2, max_length=60)
    note: str | None = Field(default=None, max_length=500)


class ReceiptStatusRequest(StrictRequestModel):
    review_id: uuid.UUID
    receipt_secret: str = Field(min_length=1, max_length=100, repr=False)


class ReceiptStatus(BaseModel):
    review_id: uuid.UUID
    status: ReviewStatus
    version: int
    published_at: datetime | None
    decision_reason: str | None
    appeal_deadline: datetime | None


class WithdrawRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    receipt_secret: str = Field(min_length=1, max_length=100, repr=False)


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



AdvisoryState = Literal["NOT_YET_EFFECTIVE", "CURRENT", "STALE", "EXPIRED"]


class Provenance(BaseModel):
    """Public source metadata. Researcher and reviewer names stay internal."""

    model_config = ConfigDict(from_attributes=True)

    source_type: SourceType
    source_ref: str
    publisher: str
    effective_on: date
    verified_on: date
    next_review_on: date | None
    licence: str


class CommunityRatingSummary(BaseModel):
    average: float | None
    count: int


class GuestFeedbackSummary(BaseModel):
    average: float | None
    count: int


class DestinationSummary(BaseModel):
    id: uuid.UUID
    name_bn: str
    name_en: str
    region_bn: str | None
    region_en: str | None
    summary_bn: str | None
    summary_en: str | None
    latitude: float | None
    longitude: float | None
    community_rating: CommunityRatingSummary
    guest_feedback: GuestFeedbackSummary
    active_advisory_count: int
    last_updated: datetime


class DestinationList(BaseModel):
    items: list[DestinationSummary]
    next_cursor: str | None


class GuideItem(BaseModel):
    id: uuid.UUID
    category: GuideCategory
    title_bn: str
    title_en: str
    body_bn: str
    body_en: str
    sort_order: int
    provenance: Provenance


class Advisory(BaseModel):
    id: uuid.UUID
    severity: AdvisorySeverity
    title_bn: str
    title_en: str
    text_bn: str
    text_en: str
    effective_on: date
    valid_until: date
    state: AdvisoryState
    provenance: Provenance


class Contact(BaseModel):
    id: uuid.UUID
    kind: ContactKind
    name_bn: str
    name_en: str
    phone: str
    address_bn: str | None
    address_en: str | None
    latitude: float | None
    longitude: float | None
    provenance: Provenance


class DestinationProfile(BaseModel):
    id: uuid.UUID
    name_bn: str
    name_en: str
    region_bn: str | None
    region_en: str | None
    summary_bn: str | None
    summary_en: str | None
    seasonality_bn: str | None
    seasonality_en: str | None
    restrictions_bn: str | None
    restrictions_en: str | None
    latitude: float | None
    longitude: float | None
    community_rating: CommunityRatingSummary
    guest_feedback: GuestFeedbackSummary
    guide_items: list[GuideItem]
    advisories: list[Advisory]
    contacts: list[Contact]
    content_licence: str | None
    content_verified_on: date | None
    as_of: date
    stale_after_days: int
    last_updated: datetime
