import 'fake-indexeddb/auto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, NETWORK_ERROR, TIMEOUT_ERROR } from '../api/client';
import type { PackDocument, PackManifest } from '../types';
import { DB_NAME, resetDbForTests } from './db';
import { RETRY_AFTER_SUPERSEDED_MS, downloadPack, sha256Hex, type DownloadDeps } from './packs';
import { deletePack, listPacks, markChecked, readPack, savePack } from './packStore';

const ID = '8f055a34-606c-5f51-a471-9695b9a6a285';

function packDoc(overrides: Partial<PackDocument> = {}): PackDocument {
  return {
    schema_version: 1,
    destination_id: ID,
    pack_version: 3,
    content_version: 'c'.repeat(64),
    generated_at: '2026-11-07T04:00:00Z',
    generated_on: '2026-11-07',
    expires_at: '2026-11-14T04:00:00Z',
    max_age_seconds: 604800,
    stale_after_days: 30,
    advisories_verified_on: null,
    languages: ['bn', 'en'],
    destination: { id: ID, name_bn: 'বান্দরবান', name_en: 'Bandarban' } as PackDocument['destination'],
    guide_items: [],
    advisories: [],
    advisory_states: [],
    contacts: [],
    reviews: { limit: 20, count: 0, items: [] },
    ...overrides,
  };
}

async function served(doc: PackDocument, manifestOverrides: Partial<PackManifest> = {}) {
  const bytes = new TextEncoder().encode(JSON.stringify(doc)).buffer as ArrayBuffer;
  const manifest: PackManifest = {
    schema_version: doc.schema_version,
    destination_id: doc.destination_id,
    pack_version: doc.pack_version,
    content_version: doc.content_version,
    sha256: await sha256Hex(bytes),
    size_bytes: bytes.byteLength,
    generated_at: doc.generated_at,
    expires_at: doc.expires_at,
    max_age_seconds: doc.max_age_seconds,
    stale_after_days: doc.stale_after_days,
    advisories_verified_on: null,
    languages: ['bn', 'en'],
    review_snapshot: { count: 0, limit: 20 },
    pack_url: `/api/v1/destinations/${ID}/pack?version=${doc.pack_version}`,
    ...manifestOverrides,
  };
  return { bytes, manifest };
}

function deps(overrides: Partial<DownloadDeps>): DownloadDeps {
  return {
    getManifest: vi.fn(),
    fetchBytes: vi.fn(),
    save: savePack,
    remove: deletePack,
    persist: vi.fn(async () => true),
    sleep: vi.fn(async () => undefined),
    isOnline: () => true,
    ...overrides,
  };
}

afterEach(async () => {
  await resetDbForTests();
  await new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
});

describe('downloadPack', () => {
  it('stores a pack whose bytes match the manifest hash, and asks for persistent storage', async () => {
    const { bytes, manifest } = await served(packDoc());
    const d = deps({ getManifest: vi.fn(async () => manifest), fetchBytes: vi.fn(async () => bytes) });
    const result = await downloadPack(ID, {}, d);
    expect(result.ok).toBe(true);
    const stored = await readPack(ID);
    expect(stored.ok && stored.value?.pack.destination.name_bn).toBe('বান্দরবান');
    expect(stored.ok && stored.value?.sha256).toBe(manifest.sha256);
    expect(d.persist).toHaveBeenCalledOnce();
  });

  it('refuses bytes that do not match the hash and keeps the old pack', async () => {
    const old = await served(packDoc({ pack_version: 2 }));
    await savePack(packDoc({ pack_version: 2 }), old.manifest);
    const { manifest } = await served(packDoc());
    const tampered = new TextEncoder().encode(JSON.stringify(packDoc({ guide_items: [] , languages: ['en'] }))).buffer as ArrayBuffer;
    const result = await downloadPack(ID, {}, deps({ getManifest: vi.fn(async () => manifest), fetchBytes: vi.fn(async () => tampered) }));
    expect(result).toEqual({ ok: false, reason: 'integrity' });
    const stored = await readPack(ID);
    expect(stored.ok && stored.value?.pack.pack_version).toBe(2);
  });

  it('refuses an unknown schema version', async () => {
    const { bytes, manifest } = await served(packDoc({ schema_version: 2 }));
    const result = await downloadPack(ID, {}, deps({ getManifest: vi.fn(async () => manifest), fetchBytes: vi.fn(async () => bytes) }));
    expect(result).toEqual({ ok: false, reason: 'format' });
    expect((await listPacks()).ok && (await listPacks())).toEqual({ ok: true, value: [] });
  });

  it('refuses a pack for another destination or another build than the manifest says', async () => {
    const other = await served(packDoc({ destination_id: 'a3933bfe-c594-5826-ac28-f889ab588737' }));
    const r1 = await downloadPack(ID, {}, deps({
      getManifest: vi.fn(async () => ({ ...other.manifest, destination_id: ID })),
      fetchBytes: vi.fn(async () => other.bytes),
    }));
    expect(r1).toEqual({ ok: false, reason: 'format' });
    const { bytes, manifest } = await served(packDoc());
    const r2 = await downloadPack(ID, {}, deps({ getManifest: vi.fn(async () => ({ ...manifest, pack_version: 9 })), fetchBytes: vi.fn(async () => bytes) }));
    expect(r2).toEqual({ ok: false, reason: 'format' });
  });

  it('keeps the old pack when saving fails (storage full)', async () => {
    const old = await served(packDoc({ pack_version: 2 }));
    await savePack(packDoc({ pack_version: 2 }), old.manifest);
    const { bytes, manifest } = await served(packDoc());
    const result = await downloadPack(ID, {}, deps({
      getManifest: vi.fn(async () => manifest),
      fetchBytes: vi.fn(async () => bytes),
      save: vi.fn(async () => ({ ok: false as const, reason: 'quota' as const })),
    }));
    expect(result).toEqual({ ok: false, reason: 'quota' });
    const stored = await readPack(ID);
    expect(stored.ok && stored.value?.pack.pack_version).toBe(2);
  });

  it('retries once after 409 superseded, waiting first, then succeeds', async () => {
    const { bytes, manifest } = await served(packDoc());
    const fetchBytes = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(409, 'PACK_VERSION_SUPERSEDED', 'newer build'))
      .mockResolvedValueOnce(bytes);
    const d = deps({ getManifest: vi.fn(async () => manifest), fetchBytes });
    const result = await downloadPack(ID, {}, d);
    expect(result.ok).toBe(true);
    expect(d.sleep).toHaveBeenCalledWith(RETRY_AFTER_SUPERSEDED_MS);
    expect(fetchBytes).toHaveBeenCalledTimes(2);
  });

  it('gives up after the second 409 and keeps the old pack', async () => {
    const old = await served(packDoc({ pack_version: 2 }));
    await savePack(packDoc({ pack_version: 2 }), old.manifest);
    const { manifest } = await served(packDoc());
    const fetchBytes = vi.fn(async () => {
      throw new ApiError(409, 'PACK_VERSION_SUPERSEDED', 'newer build');
    });
    const result = await downloadPack(ID, {}, deps({ getManifest: vi.fn(async () => manifest), fetchBytes }));
    expect(result).toEqual({ ok: false, reason: 'superseded' });
    expect(fetchBytes).toHaveBeenCalledTimes(2);
    expect((await readPack(ID)).ok).toBe(true);
  });

  it('retries a cold-start timeout once', async () => {
    const { bytes, manifest } = await served(packDoc());
    const getManifest = vi.fn().mockRejectedValueOnce(new ApiError(0, TIMEOUT_ERROR, 'slow')).mockResolvedValueOnce(manifest);
    const result = await downloadPack(ID, {}, deps({ getManifest, fetchBytes: vi.fn(async () => bytes) }));
    expect(result.ok).toBe(true);
    expect(getManifest).toHaveBeenCalledTimes(2);
  });

  it('does not retry while the browser reports no connection', async () => {
    const getManifest = vi.fn(async () => {
      throw new ApiError(0, NETWORK_ERROR, 'offline');
    });
    const result = await downloadPack(ID, {}, deps({ getManifest, isOnline: () => false }));
    expect(result).toEqual({ ok: false, reason: 'network' });
    expect(getManifest).toHaveBeenCalledTimes(1);
  });

  it('removes a stored pack only on a clear server answer (410 withdrawn)', async () => {
    const old = await served(packDoc());
    await savePack(packDoc(), old.manifest);
    const result = await downloadPack(ID, {}, deps({ getManifest: vi.fn(async () => { throw new ApiError(410, 'PACK_WITHDRAWN', 'archived'); }) }));
    expect(result).toEqual({ ok: false, reason: 'withdrawn' });
    expect((await readPack(ID)).ok && (await readPack(ID))).toEqual({ ok: true, value: undefined });
  });

  it('never removes a pack when a check merely fails (network, 429, 503)', async () => {
    const old = await served(packDoc());
    await savePack(packDoc(), old.manifest);
    for (const error of [new ApiError(0, NETWORK_ERROR, 'x'), new ApiError(429, 'RATE_LIMITED', 'x'), new ApiError(503, 'SERVICE_UNAVAILABLE', 'x')]) {
      await downloadPack(ID, {}, deps({ getManifest: vi.fn(async () => { throw error; }) }));
      const stored = await readPack(ID);
      expect(stored.ok && stored.value?.destination_id).toBe(ID);
    }
  });

  it('reports a cancel without retrying', async () => {
    const controller = new AbortController();
    controller.abort();
    const getManifest = vi.fn(async () => {
      throw new DOMException('aborted', 'AbortError');
    });
    const result = await downloadPack(ID, { signal: controller.signal }, deps({ getManifest }));
    expect(result).toEqual({ ok: false, reason: 'cancelled' });
    expect(getManifest).toHaveBeenCalledTimes(1);
  });
});

describe('packStore', () => {
  it('saves, lists, replaces in place and deletes one pack only', async () => {
    const a = await served(packDoc());
    await savePack(packDoc(), a.manifest);
    await savePack(packDoc({ destination_id: 'other', destination: { id: 'other' } as PackDocument['destination'] }), { ...a.manifest, destination_id: 'other' });
    await savePack(packDoc({ pack_version: 4 }), { ...a.manifest, pack_version: 4 });
    const all = await listPacks();
    expect(all.ok && all.value.map((p) => `${p.destination_id}:${p.pack.pack_version}`).sort()).toEqual([`${ID}:4`, 'other:3']);
    await deletePack(ID);
    const left = await listPacks();
    expect(left.ok && left.value.map((p) => p.destination_id)).toEqual(['other']);
  });

  it('records a freshness check without changing the content', async () => {
    const a = await served(packDoc());
    await savePack(packDoc(), a.manifest, new Date('2026-11-07T00:00:00Z'));
    expect(await markChecked(ID, true, new Date('2026-11-08T00:00:00Z'))).toEqual({ ok: true, value: true });
    const stored = await readPack(ID);
    expect(stored.ok && [stored.value?.last_checked_at, stored.value?.update_available, stored.value?.pack.pack_version]).toEqual([
      '2026-11-08T00:00:00.000Z',
      true,
      3,
    ]);
    expect(await markChecked('missing', false)).toEqual({ ok: true, value: false });
  });
});
