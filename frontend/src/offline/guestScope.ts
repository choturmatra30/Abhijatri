import { withDb } from './db';

/*
 * Guest scope secret: write-through copy in IndexedDB `meta` (Decisions 2026-11-08, Handoff Q1;
 * Offline-Frontend-Guideline 4.3). `localStorage` stays the synchronous reader for M1; IndexedDB
 * holds the same value, so a browser that cleared one store can restore it from the other. The value
 * never changes here: a new secret comes only from "Start as a new guest" or when both are empty,
 * because a new secret is a new guest tag and breaks review recovery.
 */

export const GUEST_SCOPE_KEY = 'abhijatri_guest_scope';
export const META_SCOPE_KEY = 'guest_scope_secret';
/** The shortest value the API accepts (API.md 5.2: 43 to 200 characters). */
export const MIN_SCOPE_LENGTH = 43;

const valid = (value: unknown): value is string => typeof value === 'string' && value.length >= MIN_SCOPE_LENGTH;

/** Writes the current secret to IndexedDB. Never throws; storage problems are ignored here. */
export async function rememberGuestScope(secret: string): Promise<void> {
  if (!valid(secret)) return;
  await withDb((db) => db.put('meta', secret, META_SCOPE_KEY));
}

function readLocal(): string | null {
  try {
    const value = localStorage.getItem(GUEST_SCOPE_KEY);
    return valid(value) ? value : null;
  } catch {
    return null;
  }
}

/**
 * Runs once at start, before the app reads the secret: copies `localStorage` to IndexedDB, or, when
 * `localStorage` lost it, puts the IndexedDB copy back. Returns what happened, for tests.
 */
export async function syncGuestScope(): Promise<'copied' | 'restored' | 'none'> {
  const local = readLocal();
  if (local) {
    await rememberGuestScope(local);
    return 'copied';
  }
  const stored = await withDb((db) => db.get('meta', META_SCOPE_KEY));
  if (stored.ok && valid(stored.value)) {
    try {
      localStorage.setItem(GUEST_SCOPE_KEY, stored.value);
      return 'restored';
    } catch {
      return 'none';
    }
  }
  return 'none';
}
