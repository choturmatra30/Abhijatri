/** Shared by the service worker (src/sw.ts) and the app, so both read and write the same caches. */
export const CACHE_VERSION = 'v1';
export const PUBLIC_API_CACHE = `abj-public-api-${CACHE_VERSION}`;
/**
 * Added by the service worker to a destination or review answer it served from its saved-copy cache
 * because the network failed or stalled. The app then prefers a downloaded pack, which is the newer,
 * user-chosen copy (Offline-Frontend-Guideline 10 "the pack wins"; Handoff F2).
 */
export const SAVED_COPY_HEADER = 'X-Abhijatri-Saved-Copy';
/** PF 18.4 default maximum age for saved destination content until the Step 8 decision. */
export const MAX_OFFLINE_AGE_MS = 7 * 24 * 60 * 60 * 1000;
