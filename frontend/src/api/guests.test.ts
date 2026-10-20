import { afterEach, describe, expect, it, vi } from 'vitest';
import { GUEST_NAME_MAX, loadGuestName, normalizeGuestName, registerGuestVisit, saveGuestName } from './guests';

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
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    });
    expect(() => saveGuestName('Sadia')).not.toThrow();
    expect(loadGuestName()).toBeNull();
  });
});

describe('registerGuestVisit', () => {
  it('sends only the scope secret, never the name', async () => {
    vi.stubGlobal('localStorage', memoryStorage());
    vi.stubGlobal('document', { documentElement: { lang: 'en' } });
    saveGuestName('Sadia');
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ guest_number: 7, total_guests: 9 })));
    vi.stubGlobal('fetch', fetchMock);

    await expect(registerGuestVisit()).resolves.toEqual({ guest_number: 7, total_guests: 9 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/api/v1/guest-visits');
    const body = JSON.parse(String(init.body));
    expect(Object.keys(body)).toEqual(['guest_scope_secret']);
    expect(String(init.body)).not.toContain('Sadia');
  });
});
