import type { PackDocument, PackManifest } from '../types';
import { withDb, type StoreResult, type StoredPack } from './db';

/*
 * Stored destination packs (R13; Offline-Frontend-Guideline 4.2, 5.2). Every function returns an
 * honest result and never throws (guideline 4.2 "Failure handling").
 */

export function readPack(destinationId: string): Promise<StoreResult<StoredPack | undefined>> {
  return withDb((db) => db.get('packs', destinationId));
}

export function listPacks(): Promise<StoreResult<StoredPack[]>> {
  return withDb((db) => db.getAll('packs'));
}

/**
 * Stores a verified pack. A single `put` is one transaction: the previous pack for this destination
 * stays until it commits, and stays untouched if it fails (guideline 5.2).
 */
export function savePack(pack: PackDocument, manifest: PackManifest, now: Date = new Date()): Promise<StoreResult<StoredPack>> {
  const record: StoredPack = {
    destination_id: pack.destination_id,
    pack,
    sha256: manifest.sha256,
    size_bytes: manifest.size_bytes,
    downloaded_at: now.toISOString(),
    last_checked_at: now.toISOString(),
    update_available: false,
  };
  return withDb(async (db) => {
    await db.put('packs', record);
    return record;
  });
}

/** Removes one pack only. */
export function deletePack(destinationId: string): Promise<StoreResult<void>> {
  return withDb((db) => db.delete('packs', destinationId));
}

/** Records a freshness check without touching the pack's content (guideline 5.3). */
export function markChecked(destinationId: string, updateAvailable: boolean, now: Date = new Date()): Promise<StoreResult<boolean>> {
  return withDb(async (db) => {
    const tx = db.transaction('packs', 'readwrite');
    const current = await tx.store.get(destinationId);
    if (!current) {
      await tx.done;
      return false;
    }
    await tx.store.put({ ...current, last_checked_at: now.toISOString(), update_available: updateAvailable });
    await tx.done;
    return true;
  });
}
