/**
 * Idempotency keys for retryable writes (API.md section 3, R16).
 *
 * One user action keeps one key across retries, so a retry after a lost response gets the stored
 * answer instead of acting twice. A *changed* request gets a new key: the server refuses a known key
 * with a different body (`409 IDEMPOTENCY_KEY_REUSED`), and a changed review draft is still
 * recovered by its `client_draft_id`. Pass the request without volatile fields (the Turnstile token
 * is single use and is left out, as the server does).
 */

import { newIdempotencyKey } from './client';

export interface IdempotencyKeys {
  /** The key for this request: the previous key while the request is unchanged, else a new one. */
  keyFor(request: unknown): string;
  /** Forget the last request, after a success, so the next action starts with a new key. */
  reset(): void;
}

/** JSON with object keys sorted at every level, so key order never changes the comparison. */
export function stableStringify(value: unknown): string {
  return JSON.stringify(value, (_key, item: unknown) => {
    if (item === null || typeof item !== 'object' || Array.isArray(item)) return item;
    return Object.fromEntries(Object.entries(item as Record<string, unknown>).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
  });
}

export function createIdempotencyKeys(makeKey: () => string = newIdempotencyKey): IdempotencyKeys {
  let last: { request: string; key: string } | null = null;
  return {
    keyFor(request: unknown): string {
      const serialized = stableStringify(request);
      if (last === null || last.request !== serialized) last = { request: serialized, key: makeKey() };
      return last.key;
    },
    reset(): void {
      last = null;
    },
  };
}
