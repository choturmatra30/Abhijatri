import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiRequest } from './client';
import { createIdempotencyKeys, stableStringify } from './idempotency';
import { submitGuestReview, withdrawGuestReview } from './reviews';

type Call = [string, RequestInit];

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
let fetchMock: ReturnType<typeof vi.fn>;
const sentHeaders = (index = 0) => (fetchMock.mock.calls[index] as unknown as Call)[1].headers as Record<string, string>;

beforeEach(() => {
  vi.stubGlobal('document', { documentElement: { lang: 'en' } });
  fetchMock = vi.fn(async () => ok({ review_id: 'r1', status: 'PENDING', version: 1, duplicate_recovered: false }));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Idempotency-Key header (R16)', () => {
  it('is sent only when a key is given', async () => {
    await apiRequest('/api/v1/x', { method: 'POST', body: {}, idempotencyKey: 'k-1' });
    await apiRequest('/api/v1/x', { method: 'POST', body: {} });
    expect(sentHeaders(0)['Idempotency-Key']).toBe('k-1');
    expect(sentHeaders(1)).not.toHaveProperty('Idempotency-Key');
  });

  it('is never sent on public reads, which stay CORS simple requests', async () => {
    await apiRequest('/api/v1/destinations');
    expect(sentHeaders()).not.toHaveProperty('Idempotency-Key');
    expect(sentHeaders()).not.toHaveProperty('Content-Type');
  });

  it('is passed through by the review write helpers', async () => {
    await submitGuestReview({} as never, 'guest-key');
    await withdrawGuestReview('r1', 'abr1_x', 3, 'withdraw-key');
    expect(sentHeaders(0)['Idempotency-Key']).toBe('guest-key');
    expect(sentHeaders(1)['Idempotency-Key']).toBe('withdraw-key');
  });
});

describe('createIdempotencyKeys', () => {
  const counter = () => {
    let n = 0;
    return () => `key-${++n}`;
  };

  it('keeps one key while the same request is retried', () => {
    const keys = createIdempotencyKeys(counter());
    expect(keys.keyFor({ a: 1, b: 2 })).toBe('key-1');
    expect(keys.keyFor({ b: 2, a: 1 })).toBe('key-1');
  });

  it('gives a changed request a new key, so the server never sees a reused key', () => {
    const keys = createIdempotencyKeys(counter());
    expect(keys.keyFor({ title: 'one' })).toBe('key-1');
    expect(keys.keyFor({ title: 'two' })).toBe('key-2');
  });

  it('starts over after reset (a success)', () => {
    const keys = createIdempotencyKeys(counter());
    keys.keyFor({ a: 1 });
    keys.reset();
    expect(keys.keyFor({ a: 1 })).toBe('key-2');
  });

  it('uses random UUIDs by default', () => {
    const key = createIdempotencyKeys().keyFor({});
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });
});

describe('stableStringify', () => {
  it('sorts keys at every level and keeps arrays in order', () => {
    expect(stableStringify({ b: { y: 1, x: 2 }, a: [3, 1] })).toBe('{"a":[3,1],"b":{"x":2,"y":1}}');
  });
});
