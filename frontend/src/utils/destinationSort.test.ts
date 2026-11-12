import { describe, expect, it } from 'vitest';
import type { DestinationSummary, GuideItem } from '../types';
import { filterGuideItems, googleMapsUrl, sortDestinations } from './destinationSort';

const destination = (
  name: string,
  community: { score: number | null; count: number },
  guest: { average: number | null; count: number },
): DestinationSummary =>
  ({
    id: name,
    name_bn: name,
    name_en: name,
    region_bn: null,
    region_en: null,
    summary_bn: null,
    summary_en: null,
    latitude: null,
    longitude: null,
    active_advisory_count: 0,
    last_updated: '2026-11-11T00:00:00Z',
    community_rating: { average: community.score, count: community.count, score: community.score, category_averages: [] },
    guest_feedback: { average: guest.average, count: guest.count, category_averages: [] },
  }) satisfies DestinationSummary;

const names = (items: DestinationSummary[]) => items.map((d) => d.name_en);

describe('sortDestinations', () => {
  const list = [
    destination('A', { score: null, count: 2 }, { average: 4.9, count: 3 }),
    destination('B', { score: 3.9, count: 6 }, { average: 2.0, count: 1 }),
    destination('C', { score: null, count: 0 }, { average: null, count: 0 }),
    destination('D', { score: 4.4, count: 9 }, { average: null, count: 0 }),
    destination('E', { score: null, count: 0 }, { average: 4.9, count: 8 }),
    destination('F', { score: null, count: 0 }, { average: 3.0, count: 20 }),
  ];

  it('keeps the server order for "name" and does not copy', () => {
    expect(sortDestinations(list, 'name')).toBe(list);
  });

  it('puts Community Rating first, then Guest Feedback, then unrated', () => {
    // D and B have a Community Rating; a high Guest Feedback average never outranks one.
    // E beats A on the review count; C has no rating at all.
    expect(names(sortDestinations(list, 'best'))).toEqual(['D', 'B', 'E', 'A', 'F', 'C']);
  });

  it('does not change the list it was given', () => {
    sortDestinations(list, 'best');
    expect(names(list)).toEqual(['A', 'B', 'C', 'D', 'E', 'F']);
  });

  it('keeps the name order between equal destinations', () => {
    const equal = [
      destination('X', { score: null, count: 0 }, { average: null, count: 0 }),
      destination('Y', { score: null, count: 0 }, { average: null, count: 0 }),
    ];
    expect(names(sortDestinations(equal, 'best'))).toEqual(['X', 'Y']);
  });

  it('treats an older API build without `score` as unrated', () => {
    const old = destination('O', { score: null, count: 7 }, { average: 1, count: 1 });
    delete (old.community_rating as { score?: number | null }).score;
    expect(names(sortDestinations([old, list[1]], 'best'))).toEqual(['B', 'O']);
  });
});

describe('filterGuideItems', () => {
  const item = (id: string, category: 'FOOD' | 'ACCOMMODATION', title_en: string, title_bn: string, body_en = ''): GuideItem =>
    ({ id, category, title_en, title_bn, body_en, body_bn: '' }) as unknown as GuideItem;
  const items = [
    item('1', 'FOOD', 'Seafood stalls', 'সামুদ্রিক খাবার', 'Fresh fish near the beach'),
    item('2', 'ACCOMMODATION', 'Beach resorts', 'সৈকতের রিসোর্ট'),
    item('3', 'FOOD', 'Local sweets', 'স্থানীয় মিষ্টি'),
  ];
  const ids = (found: GuideItem[]) => found.map((i) => i.id);

  it('returns everything for ALL and an empty search', () => {
    expect(ids(filterGuideItems(items, 'ALL', '  '))).toEqual(['1', '2', '3']);
  });

  it('filters by type', () => {
    expect(ids(filterGuideItems(items, 'FOOD', ''))).toEqual(['1', '3']);
  });

  it('searches titles and text in both languages, ignoring case', () => {
    expect(ids(filterGuideItems(items, 'ALL', 'BEACH'))).toEqual(['1', '2']);
    expect(ids(filterGuideItems(items, 'ALL', 'মিষ্টি'))).toEqual(['3']);
  });

  it('combines type and search', () => {
    expect(ids(filterGuideItems(items, 'FOOD', 'beach'))).toEqual(['1']);
    expect(ids(filterGuideItems(items, 'ACCOMMODATION', 'sweets'))).toEqual([]);
  });
});

describe('googleMapsUrl', () => {
  it('builds the documented search link for a point', () => {
    expect(googleMapsUrl(21.4272, 92.0058)).toBe('https://www.google.com/maps/search/?api=1&query=21.4272,92.0058');
  });
});
