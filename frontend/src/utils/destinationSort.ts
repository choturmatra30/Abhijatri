import type { DestinationSummary, GuideCategory, GuideItem, RatingSummary } from '../types';

export type DestinationSort = 'name' | 'best';

/** Review.md 6.4: a Community Rating exists only from five eligible Verified Member reviews. */
const communityScore = (rating: RatingSummary): number | null => rating.score ?? null;

const guestAverage = (rating: RatingSummary): number | null =>
  rating.average !== null && rating.count > 0 ? rating.average : null;

/** Higher first; a missing value sorts after every present one. */
const byValueDesc = (a: number | null, b: number | null): number => {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return b - a;
};

/**
 * "Best rated" order for the destination list (Phase 1 update, 11 Nov 2026). The two rating claims
 * are never merged into one number (Review.md 6.2), so the order has two steps: destinations with a
 * Community Rating come first, highest score first; the rest follow by Guest Feedback average, then
 * by its review count. Ties keep the server's order (name), because `Array.sort` is stable.
 */
export function sortDestinations(items: DestinationSummary[], sort: DestinationSort): DestinationSummary[] {
  if (sort === 'name') return items;
  return [...items].sort(
    (a, b) =>
      byValueDesc(communityScore(a.community_rating), communityScore(b.community_rating)) ||
      byValueDesc(guestAverage(a.guest_feedback), guestAverage(b.guest_feedback)) ||
      b.guest_feedback.count - a.guest_feedback.count,
  );
}

/** Guide entries whose title or text contains the words typed, in either language. */
export function filterGuideItems(items: GuideItem[], category: GuideCategory | 'ALL', query: string): GuideItem[] {
  const needle = query.trim().toLocaleLowerCase();
  return items.filter(
    (item) =>
      (category === 'ALL' || item.category === category) &&
      (!needle ||
        [item.title_bn, item.title_en, item.body_bn, item.body_en].some((text) => text.toLocaleLowerCase().includes(needle))),
  );
}

/** A Google Maps link for a point. Opens the Maps app on a phone; needs a connection. */
export const googleMapsUrl = (latitude: number, longitude: number): string =>
  `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
