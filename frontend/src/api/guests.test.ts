import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  GUEST_NAME_MAX,
  loadGuestName,
  loadGuestNumber,
  normalizeGuestName,
  recordDailyVisit,
  saveGuestName,
  signOutGuest,
} from './guests';

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => void values.set(key, String(value)),
  };
}

const blockedStorage = {
  getItem: () => {
    throw new Error('blocked');
  },
  setItem: () => {
    throw new Error('blocked');
  },
  removeItem: () => {
    throw new Error('blocked');
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('normalizeGuestName', () => {
  it('trims and NFC-normalises', () => {
    const decomposed = 'সাদিয়া'.normalize('NFD');
    expect(normalizeGuestName(`  ${decomposed}  `)).toBe('সাদিয়া'.normalize('NFC'));
  });

  it('returns null for blank input', () => {
    expect(normalizeGuestName('   ')).toBeNull();
  });

  it('caps the name at 80 code points, counting Bangla correctly', () => {
    const long = 'ক'.repeat(GUEST_NAME_MAX + 10);
    expect([...(normalizeGuestName(long) ?? '')]).toHaveLength(GUEST_NAME_MAX);
  });
});

describe('guest name storage', () => {
  it('round-trips through localStorage and can be cleared', () => {
    vi.stubGlobal('localStorage', memoryStorage());
    saveGuestName('Sadia');
    expect(loadGuestName()).toBe('Sadia');
    saveGuestName(null);
    expect(loadGuestName()).toBeNull();
  });

  it('tolerates blocked storage', () => {
    vi.stubGlobal('localStorage', blockedStorage);
    expect(() => saveGuestName('Sadia')).not.toThrow();
    expect(loadGuestName()).toBeNull();
  });
});

describe('recordDailyVisit', () => {
  // 10:00 UTC is 16:00 in Dhaka on the same date; the next call is a Dhaka day later.
  const day1 = new Date('2026-10-20T10:00:00Z');
  const day2 = new Date('2026-10-21T10:00:00Z');
  let fetchMock: ReturnType<typeof vi.fn>;
  let next: number;

  beforeEach(() => {
    vi.stubGlobal('document', { documentElement: { lang: 'en' } });
    next = 41;
    fetchMock = vi.fn(async () => {
      next += 1;
      return new Response(JSON.stringify({ visit_number: next, visits_today: 1 }));
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  it('sends an empty body: never the name or any device id', async () => {
    vi.stubGlobal('localStorage', memoryStorage());
    saveGuestName('Sadia');
    await recordDailyVisit(day1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/guest-visits');
    expect(init.body).toBe('{}');
  });

  it('counts a browser once per day and keeps its first number', async () => {
    vi.stubGlobal('localStorage', memoryStorage());
    expect(await recordDailyVisit(day1)).toBe(42);
    expect(await recordDailyVisit(day1)).toBe(42); // same day: no request
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(await recordDailyVisit(day2)).toBe(42); // next day: counted again, same number
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('still works with storage blocked (number shown for this visit only)', async () => {
    vi.stubGlobal('localStorage', blockedStorage);
    expect(await recordDailyVisit(day1)).toBe(42);
  });
});

describe('signOutGuest', () => {
  const day1 = new Date('2026-10-20T10:00:00Z');

  beforeEach(() => {
    vi.stubGlobal('document', { documentElement: { lang: 'en' } });
  });

  it('forgets the name, number and last visit but keeps the review scope', async () => {
    const storage = memoryStorage();
    vi.stubGlobal('localStorage', storage);
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ visit_number: 7, visits_today: 1 }))));
    storage.setItem('abhijatri_guest_scope', 'scope-secret');
    saveGuestName('Sadia');
    await recordDailyVisit(day1);

    signOutGuest();

    expect(loadGuestName()).toBeNull();
    expect(loadGuestNumber()).toBeNull();
    expect(storage.getItem('abhijatri_guest_last_visit')).toBeNull();
    expect(storage.getItem('abhijatri_guest_scope')).toBe('scope-secret');
  });

  it('gives the next guest a new, higher number even on the same day', async () => {
    vi.stubGlobal('localStorage', memoryStorage());
    let next = 6;
    const fetchMock = vi.fn(async () => {
      next += 1;
      return new Response(JSON.stringify({ visit_number: next, visits_today: 1 }));
    });
    vi.stubGlobal('fetch', fetchMock);
    saveGuestName('Sadia');
    expect(await recordDailyVisit(day1)).toBe(7);

    signOutGuest();
    saveGuestName('Rafi');

    expect(await recordDailyVisit(day1)).toBe(8);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('tolerates blocked storage', () => {
    vi.stubGlobal('localStorage', blockedStorage);
    expect(() => signOutGuest()).not.toThrow();
  });
});
