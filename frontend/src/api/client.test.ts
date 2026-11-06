import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, AUTH_REQUIRED_EVENT, NETWORK_ERROR, READ_TIMEOUT_MS, TIMEOUT_ERROR, apiRequest } from './client';
import { failureKind } from '../components/common/StatusViews';

const errorBody = (code: string, status: number) =>
  new Response(JSON.stringify({ error: { code, message: code, request_id: 'r1', field_errors: [] } }), { status });

/** A fetch that never answers until its signal aborts, like a stalled connection. */
const stalledFetch = vi.fn(
  (_url: string, init: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }),
);

beforeEach(() => {
  vi.stubGlobal('document', { documentElement: { lang: 'en' } });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('slow network: read deadline', () => {
  it('turns a stalled GET into a TIMEOUT error after READ_TIMEOUT_MS', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', stalledFetch);
    const pending = apiRequest('/api/v1/destinations');
    const assertion = expect(pending).rejects.toMatchObject({ code: TIMEOUT_ERROR, status: 0 });
    await vi.advanceTimersByTimeAsync(READ_TIMEOUT_MS);
    await assertion;
  });

  it('gives writes no default deadline', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', stalledFetch);
    let settled = false;
    const pending = apiRequest('/api/v1/reviews/guest', { method: 'POST', body: {} }).finally(() => {
      settled = true;
    });
    pending.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(READ_TIMEOUT_MS * 3);
    expect(settled).toBe(false);
  });

  it("still lets the caller cancel, without calling it a timeout", async () => {
    vi.stubGlobal('fetch', stalledFetch);
    const controller = new AbortController();
    const pending = apiRequest('/api/v1/destinations', { signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
});

describe('no internet', () => {
  it('maps a failed fetch to NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    await expect(apiRequest('/api/v1/destinations')).rejects.toMatchObject({ code: NETWORK_ERROR });
  });
});

describe('session expired', () => {
  it('announces 401 AUTH_REQUIRED so the session can end', async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal('window', { dispatchEvent });
    vi.stubGlobal('fetch', vi.fn(async () => errorBody('AUTH_REQUIRED', 401)));
    await expect(apiRequest('/api/v1/me/reviews')).rejects.toMatchObject({ code: 'AUTH_REQUIRED' });
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    expect((dispatchEvent.mock.calls[0][0] as Event).type).toBe(AUTH_REQUIRED_EVENT);
  });

  it('does not announce wrong credentials as an expired session', async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal('window', { dispatchEvent });
    vi.stubGlobal('fetch', vi.fn(async () => errorBody('INVALID_CREDENTIALS', 401)));
    await expect(apiRequest('/api/v1/auth/login', { method: 'POST', body: {} })).rejects.toBeInstanceOf(ApiError);
    expect(dispatchEvent).not.toHaveBeenCalled();
  });
});

describe('failureKind picks the right error state', () => {
  it.each([
    [new ApiError(0, NETWORK_ERROR, 'x'), 'offline'],
    [new ApiError(0, TIMEOUT_ERROR, 'x'), 'timeout'],
    [new ApiError(401, 'AUTH_REQUIRED', 'x'), 'signin'],
    [new ApiError(403, 'FORBIDDEN', 'x'), 'forbidden'],
    [new ApiError(403, 'ACCOUNT_RESTRICTED', 'x'), 'forbidden'],
    [new ApiError(500, 'INTERNAL_ERROR', 'x'), 'other'],
    [new Error('boom'), 'other'],
  ])('%s -> %s', (error, kind) => {
    expect(failureKind(error)).toBe(kind);
  });
});
