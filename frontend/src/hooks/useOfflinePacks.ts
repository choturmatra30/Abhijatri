import { useEffect, useSyncExternalStore } from 'react';
import { checkFreshness, packsStore, refreshPacks } from '../offline/packManager';
import { useOnlineStatus } from './useNetworkState';

/** The device's packs and download jobs (R13), shared by every component that shows them. */
export function useOfflinePacks() {
  const snapshot = useSyncExternalStore(packsStore.subscribe, packsStore.getSnapshot);
  useEffect(() => {
    if (snapshot.packs === null) void refreshPacks();
  }, [snapshot.packs]);
  return snapshot;
}

const RECONNECT_DEBOUNCE_MS = 2_000;

/**
 * Mounted once at the app root (Offline-Frontend-Guideline 5.3): on start while online and whenever
 * the connection returns, checks stored packs against the server. Debounced, so a flapping
 * connection runs it once; it does nothing when no pack is stored.
 */
export function useReconnectPackCheck(): void {
  const online = useOnlineStatus();
  useEffect(() => {
    if (!online) return undefined;
    const timer = window.setTimeout(() => void checkFreshness(), RECONNECT_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [online]);
}
