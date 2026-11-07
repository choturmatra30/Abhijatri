import { fetchPackBytes, getPackManifest } from '../api/packs';
import { ApiError, NETWORK_ERROR, TIMEOUT_ERROR } from '../api/client';
import type { PackDocument, PackManifest } from '../types';
import type { StoredPack } from './db';
import { deletePack, savePack } from './packStore';
import { requestPersistentStorage } from './savedDestinations';

/*
 * Download, verify and store one destination pack (R13; API.md 5.23; Offline-Frontend-Guideline 5.2).
 * A pack is stored only after its bytes match the manifest's SHA-256 and its format is understood.
 * Any failure leaves the previously stored pack untouched; only a clear server answer (410 withdrawn,
 * 404 not found) removes it (guideline section 2, rule 10).
 */

/** The pack format this app understands (API.md 5.23 `schema_version`). */
export const SCHEMA_VERSION = 1;
/** Wait before the single retry after `409 PACK_VERSION_SUPERSEDED`: the edge may still hold the old manifest. */
export const RETRY_AFTER_SUPERSEDED_MS = 5_000;

export type DownloadFailure =
  | 'network' // no connection
  | 'timeout' // no answer in time, even after one retry
  | 'integrity' // bytes did not match the manifest's SHA-256
  | 'format' // unknown schema version, or not the pack the manifest described
  | 'superseded' // a newer build kept appearing; clears within about a minute
  | 'not_found' // unknown or unpublished destination (any stored pack was removed)
  | 'withdrawn' // destination archived (any stored pack was removed)
  | 'rate_limited' // 429
  | 'server' // other server failure
  | 'quota' // device storage is full
  | 'unavailable' // storage blocked, e.g. some private windows
  | 'cancelled'; // the user cancelled

export type DownloadResult = { ok: true; stored: StoredPack } | { ok: false; reason: DownloadFailure };

/** Seams for tests; the app uses the defaults. */
export interface DownloadDeps {
  getManifest: typeof getPackManifest;
  fetchBytes: typeof fetchPackBytes;
  save: typeof savePack;
  remove: typeof deletePack;
  persist: () => Promise<unknown>;
  sleep: (ms: number) => Promise<void>;
  isOnline: () => boolean;
}

const defaultDeps: DownloadDeps = {
  getManifest: getPackManifest,
  fetchBytes: fetchPackBytes,
  save: savePack,
  remove: deletePack,
  persist: requestPersistentStorage,
  sleep: (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)),
  isOnline: () => typeof navigator === 'undefined' || navigator.onLine !== false,
};

class PackCheckError extends Error {
  constructor(readonly reason: 'integrity' | 'format') {
    super(reason);
  }
}

export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Parses and checks verified bytes against the manifest they were downloaded for. */
export function parsePack(bytes: ArrayBuffer, manifest: PackManifest, destinationId: string): PackDocument {
  let pack: PackDocument;
  try {
    pack = JSON.parse(new TextDecoder().decode(bytes)) as PackDocument;
  } catch {
    throw new PackCheckError('format');
  }
  if (
    pack?.schema_version !== SCHEMA_VERSION ||
    pack.destination_id !== destinationId ||
    pack.pack_version !== manifest.pack_version ||
    pack.content_version !== manifest.content_version ||
    !pack.destination ||
    !Array.isArray(pack.advisories) ||
    !pack.reviews
  ) {
    throw new PackCheckError('format');
  }
  return pack;
}

function failureOf(error: unknown): DownloadFailure {
  if (error instanceof PackCheckError) return error.reason;
  if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled';
  if (!(error instanceof ApiError)) return 'server';
  if (error.code === NETWORK_ERROR) return 'network';
  if (error.code === TIMEOUT_ERROR) return 'timeout';
  if (error.code === 'PACK_VERSION_SUPERSEDED' || error.status === 409) return 'superseded';
  if (error.code === 'PACK_WITHDRAWN' || error.status === 410) return 'withdrawn';
  if (error.status === 404) return 'not_found';
  if (error.status === 429) return 'rate_limited';
  return 'server';
}

/** Retried once: a cold API start (guideline 5.1a) and a build that changed mid-download (5.2). */
const RETRYABLE: ReadonlySet<DownloadFailure> = new Set(['timeout', 'superseded', 'network']);

async function attempt(destinationId: string, signal: AbortSignal | undefined, deps: DownloadDeps): Promise<DownloadResult> {
  try {
    const manifest = await deps.getManifest(destinationId, signal);
    if (manifest.destination_id !== destinationId) return { ok: false, reason: 'format' };
    const bytes = await deps.fetchBytes(manifest.pack_url, signal);
    if ((await sha256Hex(bytes)) !== manifest.sha256) throw new PackCheckError('integrity');
    const pack = parsePack(bytes, manifest, destinationId);
    const saved = await deps.save(pack, manifest);
    if (!saved.ok) return { ok: false, reason: saved.reason };
    return { ok: true, stored: saved.value };
  } catch (error) {
    return { ok: false, reason: failureOf(error) };
  }
}

export async function downloadPack(
  destinationId: string,
  { signal }: { signal?: AbortSignal } = {},
  deps: DownloadDeps = defaultDeps,
): Promise<DownloadResult> {
  let result = await attempt(destinationId, signal, deps);
  // One retry, never while the browser reports no connection or after a cancel.
  if (!result.ok && RETRYABLE.has(result.reason) && deps.isOnline() && !signal?.aborted) {
    if (result.reason === 'superseded') await deps.sleep(RETRY_AFTER_SUPERSEDED_MS);
    if (!signal?.aborted) result = await attempt(destinationId, signal, deps);
  }
  if (result.ok) {
    // Ask the browser to keep saved data; a refusal is fine and is shown on the Offline packs page.
    void deps.persist();
  } else if (result.reason === 'withdrawn' || result.reason === 'not_found') {
    // A clear server answer: the destination is gone, so its pack must not be shown any more.
    await deps.remove(destinationId);
  }
  return result;
}
