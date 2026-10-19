import { useCallback, useEffect, useState } from 'react';

export interface ApiResource<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

/**
 * Loads one resource, cancels the request when the inputs change or the component unmounts,
 * and exposes a `reload` for retry buttons. `deps` must identify the request.
 */
export function useApiResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): ApiResource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    load(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setData(null);
          setError(err);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, error, loading, reload };
}
