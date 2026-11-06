import { useRef } from 'react';
import { createIdempotencyKeys, type IdempotencyKeys } from '../api/idempotency';

/** One key keeper per component instance and action; it survives re-renders (R16). */
export function useIdempotencyKeys(): IdempotencyKeys {
  const keys = useRef<IdempotencyKeys | null>(null);
  if (keys.current === null) keys.current = createIdempotencyKeys();
  return keys.current;
}
