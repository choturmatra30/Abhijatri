export type Language = 'bn' | 'en';
export type Theme = 'light' | 'dark';

// ---------------------------------------------------------------------------
// API contract types (Docs/api/API.md sections 2, 5 and 8; backend app/schemas.py)
// ---------------------------------------------------------------------------

export interface FieldError {
  field: string;
  code: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
    field_errors: FieldError[];
  };
}

export type SourceType = 'OFFICIAL' | 'TEAM_RESEARCH' | 'OPEN_LICENCE' | 'VENDOR_LICENSED' | 'OTHER';
export type GuideCategory = 'ATTRACTION' | 'ACCOMMODATION' | 'FOOD' | 'TRANSPORT' | 'LOCAL_PRACTICE';
export type AdvisorySeverity = 'INFO' | 'CAUTION' | 'WARNING' | 'CRITICAL';
export type AdvisoryState = 'NOT_YET_EFFECTIVE' | 'CURRENT' | 'STALE' | 'EXPIRED';
export type ContactKind =
  | 'POLICE'
  | 'TOURIST_POLICE'
  | 'AMBULANCE'
  | 'FIRE'
  | 'HOSPITAL'
  | 'COAST_GUARD'
  | 'FOREST_OFFICE'
  | 'LOCAL_GUIDE'
  | 'OTHER';

export interface Provenance {
  source_type: SourceType;
  source_ref: string;
  publisher: string;
  effective_on: string;
  verified_on: string;
  next_review_on: string | null;
  licence: string;
}

export interface RatingSummary {
  average: number | null;
  count: number;
}

export interface DestinationSummary {
  id: string;
  name_bn: string;
  name_en: string;
  region_bn: string | null;
  region_en: string | null;
  summary_bn: string | null;
  summary_en: string | null;
  latitude: number | null;
  longitude: number | null;
  community_rating: RatingSummary;
  guest_feedback: RatingSummary;
  active_advisory_count: number;
  last_updated: string;
}

export interface DestinationList {
  items: DestinationSummary[];
  next_cursor: string | null;
}

export interface GuideItem {
  id: string;
  category: GuideCategory;
  title_bn: string;
  title_en: string;
  body_bn: string;
  body_en: string;
  sort_order: number;
  provenance: Provenance;
}

export interface Advisory {
  id: string;
  severity: AdvisorySeverity;
  title_bn: string;
  title_en: string;
  text_bn: string;
  text_en: string;
  effective_on: string;
  valid_until: string;
  state: AdvisoryState;
  provenance: Provenance;
}

export interface Contact {
  id: string;
  kind: ContactKind;
  name_bn: string;
  name_en: string;
  phone: string;
  address_bn: string | null;
  address_en: string | null;
  latitude: number | null;
  longitude: number | null;
  provenance: Provenance;
}

export interface DestinationProfile {
  id: string;
  name_bn: string;
  name_en: string;
  region_bn: string | null;
  region_en: string | null;
  summary_bn: string | null;
  summary_en: string | null;
  seasonality_bn: string | null;
  seasonality_en: string | null;
  restrictions_bn: string | null;
  restrictions_en: string | null;
  latitude: number | null;
  longitude: number | null;
  community_rating: RatingSummary;
  guest_feedback: RatingSummary;
  guide_items: GuideItem[];
  advisories: Advisory[];
  contacts: Contact[];
  content_licence: string | null;
  content_verified_on: string | null;
  as_of: string;
  stale_after_days: number;
  last_updated: string;
}

export type ReviewStatus =
  | 'PENDING'
  | 'UNDER_REVIEW'
  | 'CHANGES_REQUESTED'
  | 'PUBLISHED'
  | 'HIDDEN'
  | 'REJECTED'
  | 'WITHDRAWN'
  | 'DELETED';
export type ReviewLanguage = 'BN' | 'EN' | 'MIXED';
export type TravellerType = 'SOLO' | 'STUDENT' | 'COUPLE' | 'FAMILY' | 'GROUP';
export type ComfortTier = 'ECONOMY' | 'STANDARD' | 'PREMIUM';

export interface PublicReview {
  id: string;
  guest_display_name: string | null;
  status: ReviewStatus;
  overall_rating: number;
  published_at: string;
  title: string;
  body: string;
}

export interface ReviewFeed {
  items: PublicReview[];
  next_cursor: string | null;
  guest_rating_average: number | null;
  guest_rating_count: number;
}

export interface GuestReviewCreate {
  destination_id: string;
  client_draft_id: string;
  guest_scope_secret: string;
  receipt_secret: string;
  turnstile_token?: string | null;
  guest_display_name: string;
  language: ReviewLanguage;
  traveller_type: TravellerType;
  comfort_tier: ComfortTier;
  visit_month: string;
  title: string;
  body: string;
  overall_rating: number;
  consent_version: string;
}

export interface GuestReviewCreated {
  review_id: string;
  status: ReviewStatus;
  version: number;
  duplicate_recovered: boolean;
}

export interface ReceiptStatus {
  review_id: string;
  status: ReviewStatus;
  version: number;
  published_at: string | null;
  decision_reason: string | null;
  appeal_deadline: string | null;
}

// ---------------------------------------------------------------------------
// Prototype-only shapes (pages not yet backed by the API: planner, packs, trips)
// ---------------------------------------------------------------------------

export interface Destination {
  id: string;
  nameBn: string;
  nameEn: string;
  regionBn: string;
  regionEn: string;
  coverImage: string;
  rating: number;
  reviewCount: number;
  descriptionBn: string;
  descriptionEn: string;
  seasonalityBn: string;
  seasonalityEn: string;
  activeAdvisoriesCount: number;
  offlinePackSizeMb: number;
  highlightsBn: string[];
  highlightsEn: string[];
}

export interface CostEstimateItem {
  category: string;
  unit: string;
  quantity: number;
  low: number;
  expected: number;
  high: number;
  confidence: number;
}

export interface CostEstimateResult {
  destination: string;
  partySize: number;
  durationDays: number;
  durationNights: number;
  comfortTier: 'economy' | 'standard' | 'premium';
  items: CostEstimateItem[];
  totalExpected: number;
  perPersonExpected: number;
  sharedTotal: number;
  individualTotal: number;
  overallConfidence: 'High' | 'Medium' | 'Low';
}

export interface HealthStatus {
  status: string;
  database?: string;
  latencyMs?: number;
  timestamp?: string;
  urlChecked?: string;
  error?: string;
}
