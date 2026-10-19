import { HealthStatus } from '../types';
import { API_BASE_URL } from './client';

const ALLOWED_BACKEND_HOSTS = new Set([
  'localhost',
  '127.0.0.1',
  '::1',
  'api.abhijatri.example',
]);

/**
 * Allows only same-origin paths, HTTPS hosts on the allow-list or the configured
 * API host, and plain HTTP for localhost.
 */
export function isAllowedBackendUrl(value: string): boolean {
  try {
    if (value.startsWith('/') && !value.startsWith('//')) return true;
    const url = new URL(value, window.location.origin);
    const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(url.hostname);
    const validProtocol = url.protocol === 'https:' || (isLocalhost && url.protocol === 'http:');
    let configuredHost = '';
    if (API_BASE_URL) {
      try { configuredHost = new URL(API_BASE_URL).hostname; } catch { configuredHost = ''; }
    }
    return validProtocol && (ALLOWED_BACKEND_HOSTS.has(url.hostname) || url.hostname === configuredHost);
  } catch {
    return false;
  }
}

/**
 * Diagnostic health check service for the Abhijatri FastAPI backend.
 * Checks /api/v1/health (liveness) and probes /api/v1/health/ready (database readiness).
 */
export async function checkBackendHealth(customUrl?: string): Promise<HealthStatus> {
  const targetBase = customUrl ? customUrl.replace(/\/+$/, '') : API_BASE_URL;
  if (customUrl && !isAllowedBackendUrl(targetBase)) {
    return {
      status: 'error',
      error: 'Backend URL is not allowed',
      timestamp: new Date().toISOString(),
      urlChecked: targetBase,
    };
  }
  const start = performance.now();

  // Try /api/v1/health first, then fallbacks
  const candidateUrls = targetBase
    ? [`${targetBase}/api/v1/health`, `${targetBase}/api/health`, `${targetBase}/health`]
    : ['/api/v1/health', '/api/health'];

  let lastError = '';
  for (const url of candidateUrls) {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      });
      const latency = Math.round(performance.now() - start);

      if (response.ok) {
        const data = await response.json();

        // Also check /ready to test database if available (runs SELECT 1 per Architecture.md)
        let dbStatus = 'connected (liveness passed)';
        try {
          const readyUrl = url.replace(/\/health$/, '/health/ready');
          const readyRes = await fetch(readyUrl, {
            headers: { 'Accept': 'application/json' },
          });
          if (readyRes.ok) {
            dbStatus = 'database ready (SELECT 1 OK)';
          }
        } catch {
          // ignore secondary ready check failure
        }

        return {
          status: data.status || 'ok',
          database: dbStatus,
          latencyMs: latency,
          timestamp: new Date().toISOString(),
          urlChecked: url,
        };
      } else {
        lastError = `HTTP ${response.status} ${response.statusText}`;
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      lastError = errorMsg;
    }
  }

  const latency = Math.round(performance.now() - start);
  return {
    status: 'unreachable',
    latencyMs: latency,
    timestamp: new Date().toISOString(),
    urlChecked: candidateUrls[0],
    error: lastError || 'Failed to connect to backend server',
  };
}

