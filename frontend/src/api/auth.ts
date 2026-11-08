/**
 * Member account calls (API.md 5.17). The browser talks only to this API: it keeps the tokens in
 * HttpOnly cookies, so this module never sees one. Calls send credentials explicitly; the public
 * reads in `client.ts` stay credential-free CORS simple requests (PF 16.1).
 *
 * Writes that need a session send the synchronizer token from `GET /auth/csrf`. A rejected token
 * is fetched again and the write retried once (the session may have rotated).
 */

import type { AuthSession } from '../types';
import { ApiError, apiRequest } from './client';

const BASE = '/api/v1/auth';

/**
 * Deadline for the account forms submitted before a session exists (sign-in, sign-up, resend, reset
 * request). Writes otherwise wait forever, so a stalled connection left "Please wait…" on screen with
 * no way out. The API gives up after 15 s (REQUEST_TIMEOUT_SECONDS), so 30 s fires only when the
 * network itself stalled. Each of these is safe to submit again: the answer is the same either way.
 */
export const ACCOUNT_FORM_TIMEOUT_MS = 30_000;

let csrfToken: string | null = null;

export function forgetCsrfToken(): void {
  csrfToken = null;
}

async function csrf(): Promise<string> {
  if (csrfToken === null) {
    const { csrf_token } = await apiRequest<{ csrf_token: string }>(`${BASE}/csrf`, { credentials: 'include' });
    csrfToken = csrf_token;
  }
  return csrfToken;
}

interface CallOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  /** True for a write made with a session cookie: it carries `X-CSRF-Token`. */
  session?: boolean;
  /** `Idempotency-Key` of the user action (R16); the CSRF retry below reuses it. */
  idempotencyKey?: string;
  /** Additional request headers such as optimistic-concurrency `If-Match`. */
  headers?: Record<string, string>;
  /** Gives up with a `TIMEOUT` ApiError after this many ms (see `ACCOUNT_FORM_TIMEOUT_MS`). */
  timeoutMs?: number;
}

export async function call<T>(
  path: string,
  { method = 'POST', body, session = false, idempotencyKey, headers, timeoutMs }: CallOptions = {},
): Promise<T> {
  const attempt = async (): Promise<T> =>
    apiRequest<T>(path.startsWith('/api/') ? path : `${BASE}${path}`, {
      method,
      body,
      credentials: 'include',
      headers: { ...headers, ...(session ? { 'X-CSRF-Token': await csrf() } : {}) },
      idempotencyKey,
      timeoutMs,
    });
  try {
    return await attempt();
  } catch (error) {
    if (session && error instanceof ApiError && error.code === 'CSRF_INVALID') {
      forgetCsrfToken();
      return attempt();
    }
    throw error;
  }
}

/** Never a 401: an anonymous visitor gets `{ authenticated: false }`. */
export const getSession = (): Promise<AuthSession> => call<AuthSession>('/session', { method: 'GET' });

export const register = (input: { email: string; password: string; display_name: string; turnstile_token?: string | null }) =>
  call<{ status: string }>('/register', {
    body: { ...input, turnstile_token: input.turnstile_token ?? undefined },
    timeoutMs: ACCOUNT_FORM_TIMEOUT_MS,
  });

export const verifyEmail = (tokenHash: string) => call<{ status: string }>('/verify-email', { body: { token_hash: tokenHash } });

export const resendVerification = (email: string) => call<{ status: string }>('/resend-verification', { body: { email }, timeoutMs: ACCOUNT_FORM_TIMEOUT_MS });

export async function login(email: string, password: string): Promise<AuthSession> {
  const session = await call<AuthSession>('/login', { body: { email, password }, timeoutMs: ACCOUNT_FORM_TIMEOUT_MS });
  forgetCsrfToken(); // a new session has a new token
  return session;
}

export async function logout(): Promise<void> {
  try {
    await call<void>('/logout', { session: true });
  } finally {
    forgetCsrfToken();
  }
}

// Reporting a review (member, anonymous, removal request) lives in `./reports`.

export const requestPasswordReset = (email: string, turnstileToken?: string | null) =>
  call<{ status: string }>('/password-reset/request', {
    body: { email, turnstile_token: turnstileToken ?? undefined },
    timeoutMs: ACCOUNT_FORM_TIMEOUT_MS,
  });

export const confirmPasswordReset = (tokenHash: string, newPassword: string) =>
  call<{ status: string }>('/password-reset/confirm', { body: { token_hash: tokenHash, new_password: newPassword } });
