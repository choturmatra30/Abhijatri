/**
 * Guest entry and footprint (API.md 5.14; Review.md 3.2 step 1).
 *
 * Only how many guests come each day is counted, never who. The guest's name stays on this
 * device. The browser reports at most one visit per Dhaka day with an empty request body, and
 * keeps the number of its first visit to say "Guest #N".
 */

import type { GuestVisit, GuestVisitStats } from '../types';
import { currentDisplayDate } from '../utils/format';
import { apiRequest } from './client';

const GUEST_NAME_KEY = 'abhijatri_guest_name';
const GUEST_NUMBER_KEY = 'abhijatri_guest_number';
const LAST_VISIT_KEY = 'abhijatri_guest_last_visit';
/** Same limit as the review display name (API.md 5.15 `display_name`). */
export const GUEST_NAME_MAX = 80;

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage blocked: behave as a first visit
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // storage blocked: the value lives only in memory for this visit
  }
}

/** Trimmed, NFC-normalised and at most 80 code points; null when nothing usable is left. */
export function normalizeGuestName(value: string): string | null {
  const normalized = value.normalize('NFC').trim();
  if (!normalized) return null;
  return [...normalized].slice(0, GUEST_NAME_MAX).join('').trim();
}

export function loadGuestName(): string | null {
  const stored = read(GUEST_NAME_KEY);
  return stored ? normalizeGuestName(stored) : null;
}

export function saveGuestName(name: string | null): void {
  write(GUEST_NAME_KEY, name);
}

/**
 * Signs the guest out: forgets the name, the guest number and the last-visit day. The next guest
 * on this browser registers a new visit and gets the next, higher number, so guest numbers only
 * ever increase. The review scope secret stays, so duplicate-draft recovery and receipts keep
 * working.
 */
export function signOutGuest(): void {
  write(GUEST_NAME_KEY, null);
  write(GUEST_NUMBER_KEY, null);
  write(LAST_VISIT_KEY, null);
}

export function loadGuestNumber(): number | null {
  const value = Number(read(GUEST_NUMBER_KEY));
  return Number.isInteger(value) && value > 0 ? value : null;
}

/** Sends nothing about the guest: the body is always an empty object. */
export function registerGuestVisit(): Promise<GuestVisit> {
  return apiRequest<GuestVisit>('/api/v1/guest-visits', { method: 'POST', body: {} });
}

/**
 * Counts this browser at most once per Dhaka day and returns its guest number. A later day adds
 * one visit to the daily count but keeps the number from the first visit.
 */
export async function recordDailyVisit(now: Date = new Date()): Promise<number | null> {
  const today = currentDisplayDate(now);
  const stored = loadGuestNumber();
  if (stored !== null && read(LAST_VISIT_KEY) === today) return stored;
  const { visit_number } = await registerGuestVisit();
  write(LAST_VISIT_KEY, today);
  if (stored !== null) return stored;
  write(GUEST_NUMBER_KEY, String(visit_number));
  return visit_number;
}

export function getGuestVisitStats(signal?: AbortSignal): Promise<GuestVisitStats> {
  return apiRequest<GuestVisitStats>('/api/v1/guest-visits/stats', { signal });
}
