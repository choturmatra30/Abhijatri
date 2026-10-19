/**
 * Guest review lifecycle (Docs/api/API.md 5.1 to 5.4 and 5.8; Platform Foundation 13).
 *
 * Secrets rule: the guest scope secret and the receipt travel only in JSON bodies. They never go
 * into a URL, header, log, analytics event or error message.
 */

import type {
  GuestReviewCreate,
  GuestReviewCreated,
  ReceiptStatus,
  ReviewFeed,
} from '../types';
import { apiRequest } from './client';

/** Consent text version shown with the submission notice (API.md 5.2). */
export const CONSENT_VERSION = '2026-10-01';

const RECEIPT_PATTERN = /^abr1_[A-Za-z0-9_-]{43}$/;
const GUEST_SCOPE_KEY = 'abhijatri_guest_scope';

function base64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function randomBase64Url(byteLength: number): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

/** PF 13.2: 32 bytes from crypto.getRandomValues, unpadded base64url, prefix `abr1_` (48 chars). */
export function generateReceipt(): string {
  return `abr1_${randomBase64Url(32)}`;
}

export function isReceiptFormat(value: string): boolean {
  return RECEIPT_PATTERN.test(value.trim());
}

/**
 * The guest scope secret is long-lived per device and is only a supplemental abuse signal.
 * PF 18.1 places it in IndexedDB; until the offline draft store lands (R15) it is kept in
 * localStorage. It never leaves the device except in the submission body.
 */
export function getGuestScopeSecret(): string {
  try {
    const stored = localStorage.getItem(GUEST_SCOPE_KEY);
    if (stored && stored.length >= 43) return stored;
    const fresh = randomBase64Url(48);
    localStorage.setItem(GUEST_SCOPE_KEY, fresh);
    return fresh;
  } catch {
    return randomBase64Url(48); // storage blocked: one-off scope for this session
  }
}

export function getReviewFeed(
  destinationId: string,
  options: { after?: string | null; limit?: number; signal?: AbortSignal } = {},
): Promise<ReviewFeed> {
  return apiRequest<ReviewFeed>(`/api/v1/destinations/${encodeURIComponent(destinationId)}/reviews`, {
    params: { after: options.after, limit: options.limit },
    signal: options.signal,
  });
}

/**
 * 201 = created, 200 with `duplicate_recovered` = a retry of the same draft found the stored
 * review. The same `client_draft_id` and receipt must be reused on every retry of one draft.
 */
export function submitGuestReview(payload: GuestReviewCreate): Promise<GuestReviewCreated> {
  return apiRequest<GuestReviewCreated>('/api/v1/reviews/guest', {
    method: 'POST',
    body: payload,
  });
}

export function getReceiptStatus(reviewId: string, receiptSecret: string): Promise<ReceiptStatus> {
  return apiRequest<ReceiptStatus>('/api/v1/review-receipts/status', {
    method: 'POST',
    body: { review_id: reviewId, receipt_secret: receiptSecret },
  });
}

export function withdrawGuestReview(
  reviewId: string,
  receiptSecret: string,
  expectedVersion: number,
): Promise<ReceiptStatus> {
  return apiRequest<ReceiptStatus>(`/api/v1/reviews/${encodeURIComponent(reviewId)}/withdraw`, {
    method: 'POST',
    body: { receipt_secret: receiptSecret, expected_version: expectedVersion },
  });
}
