/** Shared by the service worker (src/sw.ts) and the app, so both read and write the same caches. */
export const CACHE_VERSION = 'v1';
export const PUBLIC_API_CACHE = `abj-public-api-${CACHE_VERSION}`;
/** PF 18.4 default maximum age for saved destination content until the Step 8 decision. */
export const MAX_OFFLINE_AGE_MS = 7 * 24 * 60 * 60 * 1000;
