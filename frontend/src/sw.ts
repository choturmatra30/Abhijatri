/// <reference lib="webworker" />
/*
 * Abhijatri service worker (Gantt R12; Platform Foundation 18; Security.md 7.4; Frontend-Implemented 5i).
 *
 * Caches, by allowlist only:
 *   1. the application shell and versioned build assets (precache, injected at build time);
 *   2. public destination data: GET /api/v1/destinations, /destinations/{id}, /destinations/{id}/reviews;
 *   3. the Google Fonts stylesheet and font files (CORS responses only, never opaque ones).
 * Never caches: photos and user media, sessions, accounts, receipts, reports, staff routes, any
 * non-GET request, any request carrying an Authorization header, or any response marked
 * `no-store` / `private`. Public API responses older than 7 days are not served (PF 18.4 default).
 */
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import type { WorkboxPlugin } from 'workbox-core/types';
import { CACHE_VERSION, PUBLIC_API_CACHE } from './offline/cacheNames';

declare const self: ServiceWorkerGlobalScope;

// Bump CACHE_VERSION (offline/cacheNames.ts) when the caching rules change; old caches are removed on activation.
const VERSION = CACHE_VERSION;
const SEVEN_DAYS = 7 * 24 * 60 * 60;

// 1. App shell. The precache list is generated per build, so each deploy gets a fresh, versioned cache.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Every in-app address opens the cached shell offline; API and static files are not navigations.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//, /^\/images\//, /^\/icons\//] }));

/** Refuses anything the server did not mark cacheable (Security.md 7.4: honour no-store). */
const honourCacheControl: WorkboxPlugin = {
  cacheWillUpdate: async ({ response }) => {
    const cc = (response.headers.get('Cache-Control') ?? '').toLowerCase();
    if (cc.includes('no-store') || cc.includes('private')) return null;
    return response;
  },
};

// 2. Public destination data. Network first so online readers always get current content; after 4 s
// on a stalled connection the saved copy is shown instead of a spinner.
const PUBLIC_API = /^\/api\/v1\/destinations(?:\/[0-9a-f-]{36}(?:\/reviews)?)?$/;
registerRoute(
  ({ url, request, sameOrigin }) =>
    sameOrigin && request.method === 'GET' && !request.headers.has('Authorization') && PUBLIC_API.test(url.pathname),
  new NetworkFirst({
    cacheName: PUBLIC_API_CACHE,
    networkTimeoutSeconds: 4,
    plugins: [
      new CacheableResponsePlugin({ statuses: [200] }),
      honourCacheControl,
      new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: SEVEN_DAYS, purgeOnQuotaError: true }),
    ],
  }),
);

// 3. Fonts. The stylesheet is requested with crossorigin="anonymous" (index.html), so both are CORS.
registerRoute(
  ({ url }) => url.origin === 'https://fonts.googleapis.com',
  new StaleWhileRevalidate({ cacheName: `abj-fonts-css-${VERSION}`, plugins: [new CacheableResponsePlugin({ statuses: [200] })] }),
);
registerRoute(
  ({ url }) => url.origin === 'https://fonts.gstatic.com',
  new CacheFirst({
    cacheName: `abj-fonts-${VERSION}`,
    plugins: [new CacheableResponsePlugin({ statuses: [200] }), new ExpirationPlugin({ maxEntries: 30, maxAgeSeconds: 365 * 24 * 60 * 60 })],
  }),
);

// A new version waits until the reader accepts the "update available" prompt (UpdatePrompt.tsx).
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') void self.skipWaiting();
});

// First install: control the open page right away, so it works offline without a reload.
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Remove our runtime caches from older rule versions (precache cleanup is handled above).
      const names = await caches.keys();
      await Promise.all(
        names.filter((n) => n.startsWith('abj-') && !n.endsWith(`-${VERSION}`)).map((n) => caches.delete(n)),
      );
      await self.clients.claim();
    })(),
  );
});
