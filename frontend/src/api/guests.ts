/**
 * Guest entry (API.md 5.14; Review.md 3.2 step 1).
 *
 * The guest's name stays on this device: it is kept in localStorage for the welcome message and
 * to pre-fill the review display name, and is never sent to the API. The server only returns a
 * stable "Guest #N" for this device, keyed by the same Guest scope secret used for reviews.
 */

import type { GuestVisit, GuestVisitStats } from '../types';
import { apiRequest } from './client';
import { getGuestScopeSecret } from './reviews';

const GUEST_NAME_KEY = 'abhijatri_guest_name';
/** Same limit as the review display name (API.md 5.15 `display_name`). */
export const GUEST_NAME_MAX = 80;

/** Trimmed, NFC-normalised and at most 80 code points; null when nothing usable is left. */
export function normalizeGuestName(value: string): string | null {
  const normalized = value.normalize('NFC').trim();
  if (!normalized) return null;
  return [...normalized].slice(0, GUEST_NAME_MAX).join('').trim();
}

export function loadGuestName(): string | null {
  try {
    const stored = localStorage.getItem(GUEST_NAME_KEY);
    return stored ? normalizeGuestName(stored) : null;
  } catch {
    return null; // storage blocked: the guest simply enters the name again
  }
}

export function saveGuestName(name: string | null): void {
  try {
    if (name) localStorage.setItem(GUEST_NAME_KEY, name);
    else localStorage.removeItem(GUEST_NAME_KEY);
  } catch {
    // storage blocked: the name lives only in memory for this visit
  }
}

/** The body carries only the scope secret; the name is never sent. */
export function registerGuestVisit(): Promise<GuestVisit> {
  return apiRequest<GuestVisit>('/api/v1/guest-visits', {
    method: 'POST',
    body: { guest_scope_secret: getGuestScopeSecret() },
  });
}

export function getGuestVisitStats(signal?: AbortSignal): Promise<GuestVisitStats> {
  return apiRequest<GuestVisitStats>('/api/v1/guest-visits/stats', { signal });
}
