/**
 * Abhijatri Base API Client
 * Base URL resolution, headers, and the single error contract of Platform Foundation 12.3:
 * every error body is { error: { code, message, request_id, field_errors } }.
 * Callers branch on `code`, never on `message`.
 */

import type { ApiErrorBody, FieldError } from '../types';
import { SAVED_COPY_HEADER } from '../offline/cacheNames';

/**
 * In a production build the app calls `/api/...` on its own address and Vercel forwards it to the
 * API (vercel.json). The session cookies then belong to this site, so browsers keep them; cookies of
 * another site (the Railway API) are not sent on cross-site requests. Set VITE_API_DIRECT=true only
 * when the API is served from the same site. Development uses VITE_API_BASE_URL (localhost:8000).
 */
const configuredApi = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export const API_BASE_URL: string = import.meta.env.PROD && import.meta.env.VITE_API_DIRECT !== 'true' ? '' : configuredApi;

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  fieldErrors: FieldError[];

  constructor(status: number, code: string, message: string, requestId?: string, fieldErrors: FieldError[] = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.fieldErrors = fieldErrors;
  }
}

/** Raised when the request never produced an HTTP response (offline, DNS, CORS, aborted). */
export const NETWORK_ERROR = 'NETWORK_ERROR';
/** Raised when a request got no response before its deadline (slow or stalled network). */
export const TIMEOUT_ERROR = 'TIMEOUT';
/**
 * The answer is the service worker's saved copy (the network failed) and the caller asked to be told,
 * because it holds a downloaded pack that wins over that copy (Handoff F2).
 */
export const SAVED_COPY = 'SAVED_COPY';
/** Window event fired when the API answers 401 AUTH_REQUIRED (session expired or revoked). */
export const AUTH_REQUIRED_EVENT = 'abhijatri:auth-required';
/** Default deadline for GET requests. Slow 3G is the design target (PF 19.4), so this is generous. */
export const READ_TIMEOUT_MS = 20_000;

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  params?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  /** Overrides the deadline in ms; GET defaults to READ_TIMEOUT_MS, other methods have none. */
  timeoutMs?: number;
  /**
   * Sent as `Idempotency-Key` (API.md section 3, R16). Reuse the same key for every retry of one user
   * action: the server then returns the first response instead of acting twice.
   */
  idempotencyKey?: string;
  /**
   * Throw `ApiError(0, SAVED_COPY)` instead of returning the service worker's saved copy. Set it only
   * when a downloaded pack can answer instead (Offline-Frontend-Guideline 10; Handoff F2).
   */
  refuseSavedCopy?: boolean;
}

/** A fresh key for one user action (one draft, one withdraw, one edit, one appeal). */
export const newIdempotencyKey = (): string => crypto.randomUUID();

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false;
  const error = (value as { error: unknown }).error;
  return typeof error === 'object' && error !== null && typeof (error as { code?: unknown }).code === 'string';
}

/**
 * JSON fetch helper.
 *
 * - `Accept-Language` follows the interface language, so server error messages match it.
 * - `Content-Type` is sent only with a body: public GETs stay CORS "simple" requests with no
 *   preflight round trip on slow networks (Platform Foundation 16.1).
 */
export async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, body, idempotencyKey, refuseSavedCopy, ...rest } = options;

  let url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) searchParams.append(key, String(val));
    });
    const qs = searchParams.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    'Accept-Language': document.documentElement.lang === 'en' ? 'en' : 'bn',
  };
  if (body !== undefined) requestHeaders['Content-Type'] = 'application/json';
  if (idempotencyKey) requestHeaders['Idempotency-Key'] = idempotencyKey;

  // Reads give up after a deadline so a stalled connection shows a clear "too slow" error instead of
  // spinning forever. Writes have no default deadline: the server may still complete them, and the
  // caller cannot tell. Review writes are retry-safe: a retry with the same Idempotency-Key gets the
  // stored response (R16), and review submission is also recovered through client_draft_id.
  const method = (rest.method ?? 'GET').toUpperCase();
  const timeoutMs = rest.timeoutMs ?? (method === 'GET' ? READ_TIMEOUT_MS : undefined);
  const { timeoutMs: _ignored, signal: callerSignal, ...fetchOptions } = rest;
  void _ignored;
  const controller = new AbortController();
  let timedOut = false;
  const onCallerAbort = () => controller.abort();
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort();
    else callerSignal.addEventListener('abort', onCallerAbort, { once: true });
  }
  const timer =
    timeoutMs === undefined
      ? undefined
      : globalThis.setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
      headers: { ...requestHeaders, ...(headers as Record<string, string> | undefined) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (timedOut) {
      throw new ApiError(0, TIMEOUT_ERROR, `No response within ${Math.round((timeoutMs ?? 0) / 1000)} s`);
    }
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, NETWORK_ERROR, error instanceof Error ? error.message : 'Network request failed');
  } finally {
    if (timer !== undefined) globalThis.clearTimeout(timer);
    callerSignal?.removeEventListener('abort', onCallerAbort);
  }

  if (!response.ok) throw await toApiError(response);
  if (refuseSavedCopy && response.headers.get(SAVED_COPY_HEADER)) {
    throw new ApiError(0, SAVED_COPY, 'Saved copy from the service worker; a downloaded pack answers instead');
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Turns a non-OK response into an `ApiError` (the PF 12.3 error contract). Shared by `apiRequest` and
 * callers that need the raw body, such as the offline pack download (`api/packs.ts`).
 */
export async function toApiError(response: Response): Promise<ApiError> {
  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    // Non-JSON error body (proxy or gateway page)
  }
  if (isErrorBody(parsed)) {
    const { code, message, request_id, field_errors } = parsed.error;
    if (response.status === 401 && code === 'AUTH_REQUIRED') {
      // A signed-in member's session ended on the server (expired or revoked). SessionContext
      // listens and switches the page to the guest view with a "session expired" notice.
      if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
    }
    return new ApiError(response.status, code, message, request_id, field_errors ?? []);
  }
  return new ApiError(response.status, `HTTP_${response.status}`, response.statusText || `HTTP ${response.status}`);
}
