/**
 * The review form and rating rules come from the server (API.md 5.15), so the client renders
 * what `POST /reviews/guest` will accept. The local labels in `reviewLabels.ts` remain the
 * fallback when the request fails (weak network), so the form always renders.
 */

import type { ReviewParameters } from '../types';
import { storeParameters, storedParameters } from '../offline/parameters';
import { apiRequest } from './client';

let cached: Promise<ReviewParameters> | null = null;

/**
 * One request per page load; a failure is not cached, so the next caller retries. The last answer is
 * kept on the device and used when the request fails, e.g. offline (Offline-Frontend-Guideline 6.3).
 */
export function getReviewParameters(): Promise<ReviewParameters> {
  if (!cached) {
    cached = apiRequest<ReviewParameters>('/api/v1/review-parameters')
      .then((parameters) => {
        void storeParameters(parameters);
        return parameters;
      })
      .catch(async (error: unknown) => {
        cached = null;
        const stored = await storedParameters();
        if (stored) return stored;
        throw error;
      });
  }
  return cached;
}
