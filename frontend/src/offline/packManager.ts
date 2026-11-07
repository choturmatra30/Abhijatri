import { getPackFreshness } from '../api/packs';
import { ApiError } from '../api/client';
import type { StoredPack } from './db';
import { batches, planFreshness } from './freshness';
import { downloadPack, type DownloadFailure } from './packs';
import { deletePack, listPacks, markChecked } from './packStore';

/*
 * One shared view of the device's packs (R13; Offline-Frontend-Guideline 5.3, 5.7), so the Download
 * button, the Offline packs page and the reconnect check always agree. React reads it through
 * `useOfflinePacks` (useSyncExternalStore).
 */

export type PackJob = { status: 'downloading' } | { status: 'failed'; reason: DownloadFailure };

/** Shown once, then dismissed: the server said a destination is gone, so its pack was removed. */
export interface PackNotice {
  destinationId: string;
  name_bn: string;
  name_en: string;
  why: 'withdrawn' | 'not_found';
}

export interface PacksState {
  /** null until the first read finishes. */
  packs: StoredPack[] | null;
  /** Whether this device can store packs at all. */
  storage: 'ok' | 'quota' | 'unavailable';
  jobs: Record<string, PackJob>;
  notices: PackNotice[];
  checking: boolean;
}

let state: PacksState = { packs: null, storage: 'ok', jobs: {}, notices: [], checking: false };
const listeners = new Set<() => void>();
const controllers = new Map<string, AbortController>();

function set(patch: Partial<PacksState>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

export const packsStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  getSnapshot: () => state,
};

export async function refreshPacks(): Promise<void> {
  const result = await listPacks();
  if (result.ok) set({ packs: result.value, storage: 'ok' });
  else set({ packs: [], storage: result.reason });
}

function setJob(id: string, job: PackJob | null) {
  const jobs = { ...state.jobs };
  if (job) jobs[id] = job;
  else delete jobs[id];
  set({ jobs });
}

function packName(id: string): { name_bn: string; name_en: string } {
  const pack = state.packs?.find((p) => p.destination_id === id)?.pack.destination;
  return { name_bn: pack?.name_bn ?? '', name_en: pack?.name_en ?? '' };
}

function addNotice(id: string, why: PackNotice['why']) {
  set({ notices: [...state.notices.filter((n) => n.destinationId !== id), { destinationId: id, ...packName(id), why }] });
}

/** Downloads (or updates) one pack. Any failure keeps the old pack (packs.ts). */
export async function download(destinationId: string): Promise<boolean> {
  if (state.jobs[destinationId]?.status === 'downloading') return false;
  const controller = new AbortController();
  controllers.set(destinationId, controller);
  setJob(destinationId, { status: 'downloading' });
  const result = await downloadPack(destinationId, { signal: controller.signal });
  controllers.delete(destinationId);
  if (result.ok) setJob(destinationId, null);
  else if (result.reason === 'cancelled') setJob(destinationId, null);
  else {
    if (result.reason === 'withdrawn' || result.reason === 'not_found') addNotice(destinationId, result.reason);
    setJob(destinationId, { status: 'failed', reason: result.reason });
  }
  await refreshPacks();
  return result.ok;
}

export function cancelDownload(destinationId: string): void {
  controllers.get(destinationId)?.abort();
}

export async function removePack(destinationId: string): Promise<boolean> {
  const result = await deletePack(destinationId);
  setJob(destinationId, null);
  await refreshPacks();
  return result.ok;
}

export function dismissNotice(destinationId: string): void {
  set({ notices: state.notices.filter((n) => n.destinationId !== destinationId) });
}

/**
 * The reconnect check (guideline 5.3): ask the server about every stored pack, then update, remove or
 * leave each one. Downloads run one at a time to stay under the pack rate limit. Any failed request
 * stops the run and changes nothing.
 */
export async function checkFreshness(): Promise<void> {
  if (state.checking) return;
  const stored = await listPacks();
  if (!stored.ok || stored.value.length === 0) return;
  set({ checking: true });
  try {
    for (const group of batches(stored.value.map((s) => s.destination_id))) {
      let answer;
      try {
        answer = await getPackFreshness(group);
      } catch {
        return; // network failure, 429 or 503: keep every pack and try on the next reconnect
      }
      for (const action of planFreshness(stored.value, answer.items)) {
        if (action.kind === 'unchanged') {
          await markChecked(action.destinationId, false);
        } else if (action.kind === 'remove') {
          addNotice(action.destinationId, action.why);
          await deletePack(action.destinationId);
        } else {
          const ok = await download(action.destinationId);
          if (!ok) {
            const job = state.jobs[action.destinationId];
            // Keep the pack, mark it so the page offers Update; stop on a rate limit.
            await markChecked(action.destinationId, true);
            if (job?.status === 'failed' && job.reason === 'rate_limited') return;
          }
        }
      }
    }
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
  } finally {
    set({ checking: false });
    await refreshPacks();
  }
}
