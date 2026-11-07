import type { AdvisoryState, PackAdvisory } from '../types';

/*
 * Advisory state recomputed on the device (R13; Offline-Frontend-Guideline 5.4). The pack's
 * `advisory_states` are those of the day it was built and go stale, so offline the state is always
 * recomputed on the current Asia/Dhaka date, with exactly the backend's rules
 * (`backend/app/destination_services.py` `advisory_state`, API.md 5.13).
 */

/** Today's date in Asia/Dhaka as `YYYY-MM-DD`, the calendar the backend uses (`DISPLAY_TZ`). */
export function dhakaToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Dhaka', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

/** Whole days from `from` to `to`, both `YYYY-MM-DD` (calendar dates, no time zone effects). */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}

/** Same order as the backend: not yet effective, then expired, then stale, then current. */
export function advisoryState(advisory: PackAdvisory, today: string, staleAfterDays: number): AdvisoryState {
  if (today < advisory.effective_on) return 'NOT_YET_EFFECTIVE';
  if (today > advisory.valid_until) return 'EXPIRED';
  if (daysBetween(advisory.provenance.verified_on, today) > staleAfterDays) return 'STALE';
  return 'CURRENT';
}

/** Only these are shown, as on the live route (guideline 5.4). */
export const isShownState = (state: AdvisoryState): boolean => state === 'CURRENT' || state === 'STALE';
