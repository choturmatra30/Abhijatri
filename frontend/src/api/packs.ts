import { API_BASE_URL, ApiError, NETWORK_ERROR, TIMEOUT_ERROR, apiRequest, toApiError } from './client';
import type { PackFreshnessItem, PackManifest } from '../types';

/*
 * Offline destination packs (R13; API.md 5.23; Offline-Frontend-Guideline 5.1). Public GET routes with
 * no credentials. `no-cache` skips the browser's own copy; Vercel's edge may still answer with a copy
 * up to about 60 seconds old, which is the accepted public TTL (guideline 5.1a).
 */

/**
 * A cold API can take up to about 20 s for a manifest plus pack after idle (guideline 5.1a), so pack
 * requests get their own, longer deadline than READ_TIMEOUT_MS.
 */
export const PACK_TIMEOUT_MS = 30_000;

const enc = encodeURIComponent;

export function getPackManifest(destinationId: string, signal?: AbortSignal): Promise<PackManifest> {
  return apiRequest<PackManifest>(`/api/v1/destinations/${enc(destinationId)}/pack/manifest`, {
    cache: 'no-cache',
    signal,
    timeoutMs: PACK_TIMEOUT_MS,
  });
}

/** Reconnect check for up to 20 distinct stored packs; answers come back in request order. */
export function getPackFreshness(destinationIds: string[], signal?: AbortSignal): Promise<{ items: PackFreshnessItem[] }> {
  // `destination_id` repeats, which the `params` option cannot express, so the query is built here.
  const query = destinationIds.map((id) => `destination_id=${enc(id)}`).join('&');
  return apiRequest<{ items: PackFreshnessItem[] }>(`/api/v1/packs/freshness?${query}`, {
    cache: 'no-cache',
    signal,
    timeoutMs: PACK_TIMEOUT_MS,
  });
}

/**
 * The pack's exact bytes. The SHA-256 in the manifest covers exactly what the server sent, so this
 * never re-serializes JSON. `arrayBuffer()` gives the decoded bytes, which is what the hash covers
 * even through gzip (guideline 5.1a).
 */
export async function fetchPackBytes(packUrl: string, signal?: AbortSignal): Promise<ArrayBuffer> {
  // Only a path from our own manifest is fetched, never an absolute URL from elsewhere.
  if (!packUrl.startsWith('/api/v1/destinations/')) throw new ApiError(0, 'PACK_URL_INVALID', 'Unexpected pack address');
  const controller = new AbortController();
  let timedOut = false;
  const onAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', onAbort, { once: true });
  }
  const timer = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, PACK_TIMEOUT_MS);
  try {
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${packUrl}`, {
        signal: controller.signal,
        cache: 'no-cache',
        headers: { Accept: 'application/json' },
      });
    } catch (error) {
      if (timedOut) throw new ApiError(0, TIMEOUT_ERROR, `No response within ${PACK_TIMEOUT_MS / 1000} s`);
      if (error instanceof DOMException && error.name === 'AbortError') throw error;
      throw new ApiError(0, NETWORK_ERROR, error instanceof Error ? error.message : 'Network request failed');
    }
    if (!response.ok) throw await toApiError(response);
    try {
      return await response.arrayBuffer();
    } catch (error) {
      if (timedOut) throw new ApiError(0, TIMEOUT_ERROR, `No response within ${PACK_TIMEOUT_MS / 1000} s`);
      throw error instanceof DOMException && error.name === 'AbortError'
        ? error
        : new ApiError(0, NETWORK_ERROR, 'The download was interrupted');
    }
  } finally {
    globalThis.clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}
