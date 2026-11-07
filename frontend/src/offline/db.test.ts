import 'fake-indexeddb/auto';
import { afterEach, describe, expect, it } from 'vitest';
import { DB_NAME, resetDbForTests, storageFailure, withDb, type StoredPack } from './db';
import { readStorageStatus } from './storageStatus';

const pack = (id: string): StoredPack => ({
  destination_id: id,
  pack: { destination_id: id } as StoredPack['pack'],
  sha256: 'a'.repeat(64),
  size_bytes: 10,
  downloaded_at: '2026-11-07T00:00:00Z',
  last_checked_at: null,
  update_available: false,
});

afterEach(async () => {
  await resetDbForTests();
  await new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
});

describe('offline database', () => {
  it('creates the packs, drafts and meta stores', async () => {
    const result = await withDb(async (db) => [...db.objectStoreNames].sort());
    expect(result).toEqual({ ok: true, value: ['drafts', 'meta', 'packs'] });
  });

  it('stores and reads a pack by destination id', async () => {
    await withDb((db) => db.put('packs', pack('d1')));
    const read = await withDb((db) => db.get('packs', 'd1'));
    expect(read.ok && read.value?.sha256).toBe('a'.repeat(64));
  });

  it('indexes drafts by state', async () => {
    await withDb((db) => db.put('drafts', { client_draft_id: 'x', state: 'READY' }));
    const ready = await withDb((db) => db.getAllFromIndex('drafts', 'by_state', 'READY'));
    expect(ready.ok && ready.value.map((d) => d.client_draft_id)).toEqual(['x']);
  });

  it('never throws: a failing operation becomes an honest result', async () => {
    const result = await withDb(async () => {
      throw new DOMException('disk full', 'QuotaExceededError');
    });
    expect(result).toEqual({ ok: false, reason: 'quota' });
  });

  it('reports storage as unavailable when IndexedDB is missing', async () => {
    await resetDbForTests();
    const saved = globalThis.indexedDB;
    // @ts-expect-error simulate private mode / blocked storage
    delete globalThis.indexedDB;
    try {
      expect(await withDb(async () => 1)).toEqual({ ok: false, reason: 'unavailable' });
    } finally {
      globalThis.indexedDB = saved;
    }
  });

  it('classifies storage errors', () => {
    expect(storageFailure(new DOMException('x', 'QuotaExceededError'))).toBe('quota');
    expect(storageFailure(new Error('x'))).toBe('unavailable');
    expect(storageFailure(null)).toBe('unavailable');
  });
});

describe('storage status', () => {
  it('says unknown, not durable, when the browser reports nothing', async () => {
    expect(await readStorageStatus()).toEqual({ persistence: 'unknown', usageBytes: null, quotaBytes: null });
  });
});
