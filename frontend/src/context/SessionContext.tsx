import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  loadGuestName,
  loadGuestNumber,
  normalizeGuestName,
  recordDailyVisit,
  saveGuestName,
  signOutGuest,
} from '../api/guests';

/**
 * Who is using the app. The interface adapts to it (for example, photo upload is offered only to
 * Verified Members), but it is never an authorization boundary: the API decides every permission
 * server-side (Review.md 1.1, PF 8).
 *
 * Every visitor is a guest until the account service exists (R04). A guest may give a name on
 * `/guest`; it stays on this device. The server only counts guest visits per day and never
 * learns who visited; "Guest #N" is the number of this browser's first visit (API.md 5.14).
 * The member and verified states are filled from `GET /api/v1/auth/session` when R04 lands;
 * nothing on the client can set them.
 */
export type Session =
  | { kind: 'guest'; displayName: string | null; guestNumber: number | null }
  | { kind: 'member'; displayName: string; verifiedMember: boolean };

interface SessionContextValue {
  session: Session;
  isVerifiedMember: boolean;
  /** Saves the guest's name locally and fetches this device's guest number. */
  setGuestName: (name: string) => Promise<void>;
  /** Forgets the stored name ("Not you?"); the device keeps its guest number. */
  clearGuestName: () => void;
  /**
   * Signs out. A guest has no server session, so this forgets the name on this device and keeps
   * the device's guest number. When member accounts land (R04) a member sign-out will also post
   * `/auth/logout`.
   */
  signOut: () => void;
}

const SessionContext = createContext<SessionContextValue>({
  session: { kind: 'guest', displayName: null, guestNumber: null },
  isVerifiedMember: false,
  setGuestName: async () => undefined,
  clearGuestName: () => undefined,
  signOut: () => undefined,
});

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [displayName, setDisplayName] = useState<string | null>(loadGuestName);
  const [guestNumber, setGuestNumber] = useState<number | null>(loadGuestNumber);

  // Counts this browser once per day (number + time only, API.md 5.14). The guest number is a
  // courtesy: a failed request keeps whatever number is already stored.
  const fetchNumber = useCallback(async () => {
    try {
      setGuestNumber(await recordDailyVisit());
    } catch {
      setGuestNumber(loadGuestNumber());
    }
  }, []);

  useEffect(() => {
    if (displayName) void fetchNumber();
    // Only on first load: setGuestName fetches the number itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setGuestName = useCallback(
    async (name: string) => {
      const normalized = normalizeGuestName(name);
      if (!normalized) return;
      saveGuestName(normalized);
      setDisplayName(normalized);
      await fetchNumber();
    },
    [fetchNumber],
  );

  const clearGuestName = useCallback(() => {
    saveGuestName(null);
    setDisplayName(null);
  }, []);

  const signOut = useCallback(() => {
    signOutGuest();
    setDisplayName(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      session: { kind: 'guest', displayName, guestNumber },
      isVerifiedMember: false,
      setGuestName,
      clearGuestName,
      signOut,
    }),
    [displayName, guestNumber, setGuestName, clearGuestName, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = (): SessionContextValue => useContext(SessionContext);
