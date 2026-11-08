import { ApiError, SAVED_COPY } from '../api/client';
import { getDestination } from '../api/destinations';
import { failureKind } from '../components/common/StatusViews';
import type { DestinationProfile } from '../types';
import { dhakaToday } from './advisoryState';
import type { StoredPack } from './db';
import { packToProfile } from './packAdapter';
import { readPack } from './packStore';

/*
 * Where a destination page comes from (R13; Offline-Frontend-Guideline 3, 5.6):
 * online, the network; offline, the downloaded pack first (no 4-second service-worker wait), then the
 * service worker's opened-page copy, then the not-saved message. A real 404 is never hidden by a pack.
 */

export interface LoadedDestination {
  profile: DestinationProfile;
  source: 'network' | 'pack';
  /** The downloaded pack for this destination, if any (for the banner and the Download button). */
  stored: StoredPack | null;
}

export async function loadDestination(id: string, { signal }: { signal?: AbortSignal } = {}): Promise<LoadedDestination> {
  const read = await readPack(id);
  const stored = read.ok ? (read.value ?? null) : null;
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
  if (stored && offline) return { profile: packToProfile(stored, dhakaToday()), source: 'pack', stored };
  try {
    // With a pack stored, the service worker's saved copy is refused: the pack wins (Handoff F2).
    return { profile: await getDestination(id, { signal, refuseSavedCopy: stored !== null }), source: 'network', stored };
  } catch (error) {
    if (stored && error instanceof ApiError && error.code === SAVED_COPY) {
      return { profile: packToProfile(stored, dhakaToday()), source: 'pack', stored };
    }
    const kind = failureKind(error);
    if (stored && (kind === 'offline' || kind === 'timeout')) {
      return { profile: packToProfile(stored, dhakaToday()), source: 'pack', stored };
    }
    throw error;
  }
}
