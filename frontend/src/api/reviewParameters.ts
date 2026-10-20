/**
 * The review form and rating rules come from the server (API.md 5.15), so the client renders
 * what `POST /reviews/guest` will accept. The local labels in `reviewLabels.ts` remain the
 * fallback when the request fails (weak network), so the form always renders.
 */

import type { ReviewParameters } from '../types';
import { apiRequest } from './client';

let cached: Promise<ReviewParameters> | null = null;

/** One request per page load; a failure is not cached, so the next caller retries. */
export function getReviewParameters(): Promise<ReviewParameters> {
  if (!cached) {
    cached = apiRequest<ReviewParameters>('/api/v1/review-parameters').catch((error: unknown) => {
      cached = null;
      throw error;
    });
  }
  return cached;
}
