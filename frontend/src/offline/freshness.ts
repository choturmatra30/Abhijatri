import type { PackFreshnessItem } from '../types';
import type { StoredPack } from './db';

/*
 * What to do with each stored pack after a reconnect check (R13; Offline-Frontend-Guideline 5.3).
 * Pure, so every row of the guideline's table is tested. A failed check is never an action: the
 * caller keeps every pack when the request itself fails (guideline section 2, rule 10).
 */

export type FreshnessAction =
  | { kind: 'download'; destinationId: string; why: 'content' | 'extend' }
  | { kind: 'unchanged'; destinationId: string }
  | { kind: 'remove'; destinationId: string; why: 'withdrawn' | 'not_found' };

export function planFreshness(stored: StoredPack[], items: PackFreshnessItem[]): FreshnessAction[] {
  const byId = new Map(stored.map((s) => [s.destination_id, s]));
  const actions: FreshnessAction[] = [];
  for (const item of items) {
    const pack = byId.get(item.destination_id);
    if (!pack) continue; // the server answered about something this device does not hold
    if (item.status === 'WITHDRAWN') actions.push({ kind: 'remove', destinationId: item.destination_id, why: 'withdrawn' });
    else if (item.status === 'NOT_FOUND') actions.push({ kind: 'remove', destinationId: item.destination_id, why: 'not_found' });
    else if (item.content_version !== null && item.content_version !== pack.pack.content_version)
      actions.push({ kind: 'download', destinationId: item.destination_id, why: 'content' });
    else if (item.pack_version !== null && item.pack_version > pack.pack.pack_version)
      // Same content, newer build: downloading only extends `expires_at` (API.md 5.23).
      actions.push({ kind: 'download', destinationId: item.destination_id, why: 'extend' });
    else actions.push({ kind: 'unchanged', destinationId: item.destination_id });
  }
  return actions;
}

/** The freshness route takes 1 to 20 distinct ids (API.md 5.23). */
export function batches<T>(values: T[], size = 20): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < values.length; i += size) out.push(values.slice(i, i + size));
  return out;
}
