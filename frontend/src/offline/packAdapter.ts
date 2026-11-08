import type { DestinationProfile, DestinationSummary, PackMedia, PackReview, PublicReview } from '../types';
import type { StoredPack } from './db';
import { advisoryState, isShownState } from './advisoryState';

/*
 * Stored pack → the shapes the pages already use (R13; Offline-Frontend-Guideline 5.5).
 * `today` is the current Asia/Dhaka date (`dhakaToday()`); advisories are recomputed on it, so an
 * upcoming advisory appears on its start date and an expired one disappears with no network.
 */

export function packToProfile(stored: StoredPack, today: string, now: Date = new Date()): DestinationProfile {
  const { pack } = stored;
  // Past `expires_at` every advisory is marked, so none is presented as current (Handoff F1).
  const expired = isPackExpired(stored, now);
  return {
    ...pack.destination,
    guide_items: pack.guide_items,
    contacts: pack.contacts,
    advisories: pack.advisories
      .map((a) => ({ ...a, state: advisoryState(a, today, pack.stale_after_days), ...(expired ? { from_expired_pack: true } : {}) }))
      .filter((a) => isShownState(a.state)),
    as_of: today,
    // Read from the top of the pack: it is not inside `destination` (guideline 5.5).
    stale_after_days: pack.stale_after_days,
    last_updated: pack.generated_at,
  };
}

/** For lists (Overview, Destinations, landing), with the advisory count recomputed for today. */
export function packToSummary(stored: StoredPack, today: string): DestinationSummary {
  const profile = packToProfile(stored, today);
  return {
    id: profile.id,
    name_bn: profile.name_bn,
    name_en: profile.name_en,
    region_bn: profile.region_bn,
    region_en: profile.region_en,
    summary_bn: profile.summary_bn,
    summary_en: profile.summary_en,
    latitude: profile.latitude,
    longitude: profile.longitude,
    community_rating: profile.community_rating,
    guest_feedback: profile.guest_feedback,
    active_advisory_count: profile.advisories.length,
    last_updated: profile.last_updated,
  };
}

/** Pack reviews are published by definition. Pack media has no link, so `media` stays empty here. */
export function packReviewToPublic(review: PackReview): PublicReview {
  const { media: _media, ...rest } = review;
  void _media;
  return { ...rest, status: 'PUBLISHED', media: [] };
}

/** The review's photos and videos, described for an "Open when online" note (RV 7.4). */
export const packReviewMedia = (review: PackReview): PackMedia[] => review.media;

/**
 * Past `expires_at` the pack is "Out of date": it is still shown, clearly labelled, and its advisories
 * are never presented as current safety guidance (owner's decision 7 Nov 2026; PF 18.4, Security 7.4).
 */
export function isPackExpired(stored: StoredPack, now: Date = new Date()): boolean {
  return now.getTime() > Date.parse(stored.pack.expires_at);
}
