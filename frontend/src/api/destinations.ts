/**
 * Public destination reads (R02 contract, Docs/api/API.md 5.12 and 5.13).
 * Both routes are public, cacheable for 60 seconds and carry Bangla and English in one payload,
 * so a language switch never needs a refetch.
 */

import type { DestinationList, DestinationProfile, DestinationSummary } from '../types';
import { apiRequest } from './client';

export function listDestinations(
  options: { after?: string | null; limit?: number; signal?: AbortSignal } = {},
): Promise<DestinationList> {
  return apiRequest<DestinationList>('/api/v1/destinations', {
    params: { after: options.after, limit: options.limit },
    signal: options.signal,
  });
}

/** Follows `next_cursor` until the list is complete. The semester scope is five destinations. */
export async function listAllDestinations(signal?: AbortSignal): Promise<DestinationSummary[]> {
  const items: DestinationSummary[] = [];
  let after: string | null = null;
  do {
    const page: DestinationList = await listDestinations({ after, limit: 50, signal });
    items.push(...page.items);
    after = page.next_cursor;
  } while (after);
  return items;
}

export function getDestination(
  id: string,
  options: { includeExpired?: boolean; signal?: AbortSignal } = {},
): Promise<DestinationProfile> {
  return apiRequest<DestinationProfile>(`/api/v1/destinations/${encodeURIComponent(id)}`, {
    params: { include_expired: options.includeExpired || undefined },
    signal: options.signal,
  });
}
