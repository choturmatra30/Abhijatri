import { useEffect, useState } from 'react';

/** Whether the browser reports a network connection; updates on the online and offline events. */
export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine));
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, []);
  return online;
}

/** Wait (ms) after which an operation that is still running counts as slow. */
export const SLOW_AFTER_MS = 8000;

/** True once `active` has stayed true for `ms`; resets as soon as `active` turns false. */
export function useSlowFlag(active: boolean, ms: number = SLOW_AFTER_MS): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!active) {
      setSlow(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setSlow(true), ms);
    return () => window.clearTimeout(timer);
  }, [active, ms]);
  return slow;
}

/**
 * How much image data to fetch (Platform Foundation 18.1 and 19.3; Frontend-Implemented 5i).
 * - `none`: offline. Photos are never cached by the service worker, so nothing would load.
 * - `small`: Data Saver is on or the connection is 2G/3G class: small variants only, user media on request.
 * - `full`: normal connection; still sized to the slot, never eager full-resolution user media.
 */
export type ImagePolicy = 'none' | 'small' | 'full';

interface NetworkInformationLike extends EventTarget {
  saveData?: boolean;
  effectiveType?: string;
}

function connection(): NetworkInformationLike | undefined {
  return typeof navigator === 'undefined' ? undefined : (navigator as Navigator & { connection?: NetworkInformationLike }).connection;
}

function lowData(): boolean {
  const c = connection();
  return Boolean(c && (c.saveData || (c.effectiveType && ['slow-2g', '2g', '3g'].includes(c.effectiveType))));
}

export function useImagePolicy(): ImagePolicy {
  const online = useOnlineStatus();
  const [constrained, setConstrained] = useState(lowData);
  useEffect(() => {
    const c = connection();
    if (!c) return undefined;
    const update = () => setConstrained(lowData());
    c.addEventListener('change', update);
    return () => c.removeEventListener('change', update);
  }, []);
  if (!online) return 'none';
  return constrained ? 'small' : 'full';
}
