import { describe, expect, it } from 'vitest';
import type { PackAdvisory, PackReview } from '../types';
import type { StoredPack } from './db';
import { advisoryState, daysBetween, dhakaToday } from './advisoryState';
import { isPackExpired, packReviewMedia, packReviewToPublic, packToProfile, packToSummary } from './packAdapter';

const adv = (effective_on: string, valid_until: string, verified_on: string, id = 'a'): PackAdvisory => ({
  id,
  severity: 'CAUTION',
  title_bn: 'শিরোনাম',
  title_en: 'Title',
  text_bn: 'লেখা',
  text_en: 'Text',
  effective_on,
  valid_until,
  provenance: {
    source_type: 'OFFICIAL',
    source_ref: 'x',
    publisher: 'x',
    effective_on,
    verified_on,
    next_review_on: null,
    licence: 'x',
  },
});

describe('dhakaToday', () => {
  it('uses the Asia/Dhaka calendar (UTC+6), not UTC', () => {
    // 17:59 UTC is 23:59 in Dhaka: still the same day.
    expect(dhakaToday(new Date('2026-11-07T17:59:00Z'))).toBe('2026-11-07');
    // 18:00 UTC is midnight in Dhaka: already the next day while UTC is still on the 7th.
    expect(dhakaToday(new Date('2026-11-07T18:00:00Z'))).toBe('2026-11-08');
  });
});

describe('advisoryState (same rules as backend advisory_state)', () => {
  const a = adv('2026-11-05', '2026-11-20', '2026-11-01');
  it('each state', () => {
    expect(advisoryState(a, '2026-11-04', 30)).toBe('NOT_YET_EFFECTIVE');
    expect(advisoryState(a, '2026-11-10', 30)).toBe('CURRENT');
    expect(advisoryState(a, '2026-11-21', 30)).toBe('EXPIRED');
    expect(advisoryState(a, '2026-11-10', 5)).toBe('STALE');
  });
  it('first and last valid day are shown', () => {
    expect(advisoryState(a, '2026-11-05', 30)).toBe('CURRENT');
    expect(advisoryState(a, '2026-11-20', 30)).toBe('CURRENT');
  });
  it('stale only after more than stale_after_days since verification', () => {
    expect(daysBetween('2026-11-01', '2026-12-01')).toBe(30);
    const long = adv('2026-11-01', '2027-01-01', '2026-11-01');
    expect(advisoryState(long, '2026-12-01', 30)).toBe('CURRENT');
    expect(advisoryState(long, '2026-12-02', 30)).toBe('STALE');
  });
  it('not yet effective wins over expired, as on the server', () => {
    expect(advisoryState(adv('2026-11-10', '2026-11-05', '2026-11-01'), '2026-11-08', 30)).toBe('NOT_YET_EFFECTIVE');
  });
  it('around midnight Dhaka the state follows the Dhaka date, not the UTC date', () => {
    const endsToday = adv('2026-11-01', '2026-11-07', '2026-11-01');
    expect(advisoryState(endsToday, dhakaToday(new Date('2026-11-07T17:59:00Z')), 30)).toBe('CURRENT');
    expect(advisoryState(endsToday, dhakaToday(new Date('2026-11-07T18:00:00Z')), 30)).toBe('EXPIRED');
  });
});

const review: PackReview = {
  id: 'r1',
  author_type: 'GUEST',
  guest_tag: '1C669J0TDY',
  author_display_name: null,
  overall_rating: 4,
  category_ratings: { FOOD: 5 },
  published_at: '2026-11-01T00:00:00Z',
  title: 'শিরোনাম',
  body: 'বিবরণ',
  media: [{ id: 'm1', kind: 'image', alt_text: 'Hills', caption: null }],
};

const stored = (advisories: PackAdvisory[]): StoredPack => ({
  destination_id: 'd',
  sha256: 'a'.repeat(64),
  size_bytes: 1,
  downloaded_at: '2026-11-07T00:00:00Z',
  last_checked_at: null,
  update_available: false,
  pack: {
    schema_version: 1,
    destination_id: 'd',
    pack_version: 1,
    content_version: 'c',
    generated_at: '2026-11-07T04:00:00Z',
    generated_on: '2026-11-07',
    expires_at: '2026-11-14T04:00:00Z',
    max_age_seconds: 604800,
    stale_after_days: 30,
    advisories_verified_on: '2026-11-01',
    languages: ['bn', 'en'],
    destination: { id: 'd', name_bn: 'বান্দরবান', name_en: 'Bandarban' } as StoredPack['pack']['destination'],
    guide_items: [],
    advisories,
    advisory_states: advisories.map((x) => ({ id: x.id, state: 'CURRENT' as const })),
    contacts: [],
    reviews: { limit: 20, count: 1, items: [review] },
  },
});

describe('packAdapter', () => {
  const running = adv('2026-11-01', '2026-11-30', '2026-11-01', 'running');
  const upcoming = adv('2026-11-12', '2026-11-30', '2026-11-01', 'upcoming');
  const ending = adv('2026-11-01', '2026-11-09', '2026-11-01', 'ending');

  it('shows only advisories in effect today, recomputed offline', () => {
    const s = stored([running, upcoming, ending]);
    expect(packToProfile(s, '2026-11-08').advisories.map((a) => a.id)).toEqual(['running', 'ending']);
    // Days later with no network: the ended one is gone and the upcoming one has started.
    expect(packToProfile(s, '2026-11-12').advisories.map((a) => a.id)).toEqual(['running', 'upcoming']);
  });

  it('reads stale_after_days from the top of the pack', () => {
    const s = stored([running]);
    s.pack.stale_after_days = 3;
    const profile = packToProfile(s, '2026-11-08');
    expect(profile.stale_after_days).toBe(3);
    expect(profile.advisories[0].state).toBe('STALE');
  });

  it('builds a list summary with the recomputed advisory count', () => {
    expect(packToSummary(stored([running, upcoming]), '2026-11-08')).toMatchObject({ name_bn: 'বান্দরবান', active_advisory_count: 1 });
  });

  it('turns pack reviews into published reviews without media links', () => {
    expect(packReviewToPublic(review)).toMatchObject({ id: 'r1', status: 'PUBLISHED', media: [], title: 'শিরোনাম' });
    expect(packReviewMedia(review)).toEqual([{ id: 'm1', kind: 'image', alt_text: 'Hills', caption: null }]);
  });

  it('marks a pack out of date after expires_at', () => {
    const s = stored([]);
    expect(isPackExpired(s, new Date('2026-11-14T03:59:59Z'))).toBe(false);
    expect(isPackExpired(s, new Date('2026-11-14T04:00:01Z'))).toBe(true);
  });
});
