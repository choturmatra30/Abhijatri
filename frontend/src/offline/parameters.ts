import type { ReviewParameters } from '../types';
import { withDb } from './db';

/*
 * The last review parameters the server sent (API.md 5.15), kept in IndexedDB `meta` so the review
 * form keeps current limits and category prompts offline (Offline-Frontend-Guideline 6.3). Public,
 * non-personal data. Failures are silent: the form then uses its built-in fallback values.
 */

const KEY = 'review_parameters';

export async function storeParameters(parameters: ReviewParameters): Promise<void> {
  await withDb((db) => db.put('meta', parameters, KEY));
}

export async function storedParameters(): Promise<ReviewParameters | null> {
  const read = await withDb((db) => db.get('meta', KEY));
  return read.ok && read.value ? (read.value as ReviewParameters) : null;
}
