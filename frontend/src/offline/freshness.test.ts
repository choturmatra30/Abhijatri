import 'fake-indexeddb/auto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PackDocument, PackFreshnessItem, PackManifest } from '../types';
import { DB_NAME, resetDbForTests, type StoredPack } from './db';
import { batches, planFreshness } from './freshness';

vi.mock('../api/packs', () => ({
  getPackFreshness: vi.fn(),
  getPackManifest: vi.fn(),
  fetchPackBytes: vi.fn(),
  PACK_TIMEOUT_MS: 30_000,
}));

const A = '8f055a34-606c-5f51-a471-9695b9a6a285';
const B = 'a3933bfe-c594-5826-ac28-f889ab588737';

const doc = (id: string, content = 'c1', version = 3): PackDocument =>
  ({
    schema_version: 1,
    destination_id: id,
    pack_version: version,
    content_version: content,
    generated_at: '2026-11-07T04:00:00Z',
    generated_on: '2026-11-07',
    expires_at: '2026-11-14T04:00:00Z',
    max_age_seconds: 604800,
    stale_after_days: 30,
    advisories_verified_on: null,
    languages: ['bn', 'en'],
    destination: { id, name_bn: 'বান্দরবান', name_en: 'Bandarban' },
    guide_items: [],
    advisories: [],
    advisory_states: [],
    contacts: [],
    reviews: { limit: 20, count: 0, items: [] },
  }) as unknown as PackDocument;

const stored = (id: string, content = 'c1', version = 3): StoredPack => ({
  destination_id: id,
  pack: doc(id, content, version),
  sha256: 's',
  size_bytes: 1,
  downloaded_at: '2026-11-07T00:00:00Z',
  last_checked_at: null,
  update_available: false,
});

const item = (id: string, status: PackFreshnessItem['status'], content: string | null = 'c1', version: number | null = 3): PackFreshnessItem => ({
  destination_id: id,
  status,
  pack_version: version,
  content_version: content,
  sha256: null,
  size_bytes: null,
  generated_at: null,
  expires_at: null,
  pack_url: null,
});

describe('planFreshness (guideline table 5.3)', () => {
  const s = [stored(A)];
  it('content changed: download', () => {
    expect(planFreshness(s, [item(A, 'AVAILABLE', 'c2')])).toEqual([{ kind: 'download', destinationId: A, why: 'content' }]);
  });
  it('same content, newer build: download to extend the expiry', () => {
    expect(planFreshness(s, [item(A, 'AVAILABLE', 'c1', 4)])).toEqual([{ kind: 'download', destinationId: A, why: 'extend' }]);
  });
  it('nothing changed', () => {
    expect(planFreshness(s, [item(A, 'AVAILABLE')])).toEqual([{ kind: 'unchanged', destinationId: A }]);
  });
  it('withdrawn and not found: remove', () => {
    expect(planFreshness(s, [item(A, 'WITHDRAWN', null, null)])).toEqual([{ kind: 'remove', destinationId: A, why: 'withdrawn' }]);
    expect(planFreshness(s, [item(A, 'NOT_FOUND', null, null)])).toEqual([{ kind: 'remove', destinationId: A, why: 'not_found' }]);
  });
  it('ignores answers about packs this device does not hold', () => {
    expect(planFreshness(s, [item(B, 'WITHDRAWN', null, null)])).toEqual([]);
  });
  it('batches of at most 20 ids', () => {
    const ids = Array.from({ length: 45 }, (_, i) => String(i));
    expect(batches(ids).map((b) => b.length)).toEqual([20, 20, 5]);
  });
});

describe('checkFreshness (reconnect run)', () => {
  beforeEach(() => {
    vi.resetModules();
  });
  afterEach(async () => {
    await resetDbForTests();
    await new Promise<void>((resolve) => {
      const request = indexedDB.deleteDatabase(DB_NAME);
      request.onsuccess = request.onerror = request.onblocked = () => resolve();
    });
  });

  async function setup(packs: StoredPack[]) {
    const store = await import('./packStore');
    for (const p of packs) await store.savePack(p.pack, { sha256: p.sha256, size_bytes: p.size_bytes } as PackManifest);
    const api = await import('../api/packs');
    const manager = await import('./packManager');
    return { store, api: vi.mocked(api), manager };
  }

  it('a failed check deletes nothing', async () => {
    const { store, api, manager } = await setup([stored(A), stored(B)]);
    api.getPackFreshness.mockRejectedValue(new Error('offline'));
    await manager.checkFreshness();
    const all = await store.listPacks();
    expect(all.ok && all.value.map((p) => p.destination_id).sort()).toEqual([A, B]);
  });

  it('removes a withdrawn pack with a notice, marks an unchanged one checked', async () => {
    const { store, api, manager } = await setup([stored(A), stored(B)]);
    api.getPackFreshness.mockResolvedValue({ items: [item(A, 'AVAILABLE'), item(B, 'WITHDRAWN', null, null)] });
    await manager.checkFreshness();
    const all = await store.listPacks();
    expect(all.ok && all.value.map((p) => p.destination_id)).toEqual([A]);
    expect(all.ok && all.value[0].last_checked_at).not.toBeNull();
    expect(manager.packsStore.getSnapshot().notices.map((n) => [n.destinationId, n.why])).toEqual([[B, 'withdrawn']]);
  });

  it('keeps the pack and marks it "update available" when the update download fails', async () => {
    const { store, api, manager } = await setup([stored(A)]);
    api.getPackFreshness.mockResolvedValue({ items: [item(A, 'AVAILABLE', 'c2')] });
    api.getPackManifest.mockRejectedValue(Object.assign(new Error('x'), { name: 'TypeError' }));
    await manager.checkFreshness();
    const kept = await store.readPack(A);
    expect(kept.ok && kept.value?.pack.content_version).toBe('c1');
    expect(kept.ok && kept.value?.update_available).toBe(true);
  });

  it('does nothing and asks nothing when no pack is stored', async () => {
    const { api, manager } = await setup([]);
    await manager.checkFreshness();
    expect(api.getPackFreshness).not.toHaveBeenCalled();
  });
});
