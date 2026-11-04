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
