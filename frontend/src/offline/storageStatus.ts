/**
 * What the browser says about saved data (PF 18.2; Offline-Frontend-Guideline 4.4), for the Offline
 * packs page. Never claims durability the browser did not grant: `refused` means the browser may
 * delete saved data under storage pressure, and the page says so.
 */
export type Persistence = 'granted' | 'refused' | 'unknown';

export interface StorageStatus {
  persistence: Persistence;
  /** Bytes this site uses, when the browser reports it. */
  usageBytes: number | null;
  /** Bytes this site may use, when the browser reports it. */
  quotaBytes: number | null;
}

export async function readStorageStatus(): Promise<StorageStatus> {
  const storage = typeof navigator === 'undefined' ? undefined : navigator.storage;
  let persistence: Persistence = 'unknown';
  let usageBytes: number | null = null;
  let quotaBytes: number | null = null;
  try {
    if (storage?.persisted) persistence = (await storage.persisted()) ? 'granted' : 'refused';
  } catch {
    persistence = 'unknown';
  }
  try {
    if (storage?.estimate) {
      const estimate = await storage.estimate();
      usageBytes = estimate.usage ?? null;
      quotaBytes = estimate.quota ?? null;
    }
  } catch {
    /* not reported */
  }
  return { persistence, usageBytes, quotaBytes };
}
