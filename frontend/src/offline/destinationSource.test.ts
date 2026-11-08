import 'fake-indexeddb/auto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, SAVED_COPY, apiRequest } from '../api/client';
import type { PackDocument, PackManifest } from '../types';
import { SAVED_COPY_HEADER } from './cacheNames';
import { DB_NAME, resetDbForTests } from './db';
import { loadDestination } from './destinationSource';
import { savePack } from './packStore';

/*
 * Handoff F2: with the server down but `navigator.onLine` still true, the service worker answers from its
 * saved-copy cache. When a downloaded pack exists it must win over that copy (Offline-Frontend-Guideline 10).
 */

const ID = '8f055a34-606c-5f51-a471-9695b9a6a285';

const packDoc: PackDocument = {
  schema_version: 1,
  destination_id: ID,
  pack_version: 3,
  content_version: 'c'.repeat(64),
  generated_at: '2026-11-07T04:00:00Z',
  generated_on: '2026-11-07',
  expires_at: '2099-01-01T00:00:00Z',
  max_age_seconds: 604800,
  stale_after_days: 30,
  advisories_verified_on: null,
  languages: ['bn', 'en'],
  destination: { id: ID, name_bn: 'বান্দরবান', name_en: 'Bandarban (pack)' } as PackDocument['destination'],
  guide_items: [],
  advisories: [],
  advisory_states: [],
  contacts: [],
  reviews: { limit: 20, count: 0, items: [] },
};
const manifest = { destination_id: ID, sha256: '0'.repeat(64), size_bytes: 10 } as PackManifest;

/** What the network (or the service worker) answers for the destination route. */
function answer(name: string, savedCopy: boolean): Response {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (savedCopy) headers[SAVED_COPY_HEADER] = '1';
  return new Response(JSON.stringify({ id: ID, name_en: name, advisories: [] }), { status: 200, headers });
}

beforeEach(() => {
  vi.stubGlobal('document', { documentElement: { lang: 'en' } });
  vi.stubGlobal('navigator', { onLine: true });
});

afterEach(async () => {
  vi.unstubAllGlobals();
  await resetDbForTests();
  await new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
});

describe('apiRequest refuseSavedCopy', () => {
  it('returns a saved copy when the caller did not ask to refuse it', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => answer('copy', true)));
    await expect(apiRequest<{ name_en: string }>('/x')).resolves.toMatchObject({ name_en: 'copy' });
  });

  it('throws SAVED_COPY for a saved copy when asked to refuse it', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => answer('copy', true)));
    const error = await apiRequest('/x', { refuseSavedCopy: true }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe(SAVED_COPY);
  });

  it('accepts a live answer even when refusing saved copies', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => answer('live', false)));
    await expect(apiRequest<{ name_en: string }>('/x', { refuseSavedCopy: true })).resolves.toMatchObject({ name_en: 'live' });
  });
});

describe('loadDestination (F2: the pack wins over the saved copy)', () => {
  it('uses the pack when the service worker answered from its saved copy', async () => {
    await savePack(packDoc, manifest);
    vi.stubGlobal('fetch', vi.fn(async () => answer('old saved copy', true)));
    const loaded = await loadDestination(ID);
    expect(loaded.source).toBe('pack');
    expect(loaded.profile.name_en).toBe('Bandarban (pack)');
  });

  it('keeps the saved copy when no pack is stored (R12 behaviour unchanged)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => answer('old saved copy', true)));
    const loaded = await loadDestination(ID);
    expect(loaded.source).toBe('network');
    expect(loaded.profile.name_en).toBe('old saved copy');
  });

  it('prefers live content over the pack when the server answers', async () => {
    await savePack(packDoc, manifest);
    vi.stubGlobal('fetch', vi.fn(async () => answer('live', false)));
    const loaded = await loadDestination(ID);
    expect(loaded.source).toBe('network');
    expect(loaded.profile.name_en).toBe('live');
  });
});
