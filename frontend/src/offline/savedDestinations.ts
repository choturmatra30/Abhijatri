import type { DestinationProfile, DestinationSummary } from '../types';
import { MAX_OFFLINE_AGE_MS, PUBLIC_API_CACHE } from './cacheNames';

const DETAIL_PATH = /^\/api\/v1\/destinations\/([0-9a-f-]{36})$/;

export interface SavedDestination {
  summary: DestinationSummary;
  /** When this device saved the copy (the response's Date header). */
  savedAt: Date | null;
}

/**
 * Destinations whose full page this device has saved for offline use (Frontend-Implemented 5i).
 * Reads the service worker's public cache directly, so it works with no network at all. Copies older
 * than the offline maximum age are left out: they are never presented as current (PF 18.4).
 */
export async function savedDestinations(): Promise<SavedDestination[]> {
  if (typeof caches === 'undefined') return [];
  try {
    const cache = await caches.open(PUBLIC_API_CACHE);
    const now = Date.now();
    const found: SavedDestination[] = [];
    for (const request of await cache.keys()) {
      if (!DETAIL_PATH.test(new URL(request.url).pathname)) continue;
      const response = await cache.match(request);
      if (!response) continue;
      const dateHeader = response.headers.get('date');
      const savedAt = dateHeader ? new Date(dateHeader) : null;
      if (savedAt && now - savedAt.getTime() > MAX_OFFLINE_AGE_MS) continue;
      const profile = (await response.json()) as DestinationProfile;
      found.push({
        savedAt,
        summary: {
          id: profile.id,
          name_bn: profile.name_bn,
          name_en: profile.name_en,
          region_bn: profile.region_bn,
          region_en: profile.region_en,
          summary_bn: profile.summary_bn,
          summary_en: profile.summary_en,
          latitude: profile.latitude,
          longitude: profile.longitude,
          community_rating: profile.community_rating,
          guest_feedback: profile.guest_feedback,
          active_advisory_count: profile.advisories.filter((a) => new Date(a.valid_until).getTime() >= now).length,
          last_updated: profile.last_updated,
        },
      });
    }
    return found.sort((a, b) => a.summary.name_en.localeCompare(b.summary.name_en));
  } catch {
    return []; // storage unavailable or cleared: behave as "nothing saved"
  }
}

/**
 * Asks the browser not to evict saved data under storage pressure (PF 18.2). A refusal is fine:
 * the result is shown on the offline pages so nobody is told data is durable when it is not.
 */
export async function requestPersistentStorage(): Promise<boolean | null> {
  if (typeof navigator === 'undefined' || !navigator.storage?.persist) return null;
  try {
    if (await navigator.storage.persisted()) return true;
    return await navigator.storage.persist();
  } catch {
    return null;
  }
}
