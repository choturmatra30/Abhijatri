import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  loadGuestName,
  loadGuestTag,
  normalizeGuestName,
  recordDailyVisit,
  saveGuestName,
  signOutGuest,
  startAsNewGuest as resetGuest,
} from '../api/guests';

/**
 * Who is using the app. The interface adapts to it (for example, photo upload is offered only to
 * Verified Members), but it is never an authorization boundary: the API decides every permission
 * server-side (Review.md 1.1, PF 8).
 *
 * Every visitor is a guest until the account service exists (R04). Each browser has a guest tag
 * such as `1C669-J0TDY`, derived on the device from the guest scope secret
 * (Guest-Identity-and-Visits 3.1). A guest may give a name on `/guest`; it stays on this device for
 * 30 days after the last visit. The server only counts visits per day and never learns who visited.
 * The member and verified states are filled from `GET /api/v1/auth/session` when R04 lands;
 * nothing on the client can set them.
 */
export type Session =
  | { kind: 'guest'; displayName: string | null; guestTag: string | null }
  | { kind: 'member'; displayName: string; verifiedMember: boolean };

interface SessionContextValue {
  session: Session;
  isVerifiedMember: boolean;
  /** Saves the guest's name locally (a 30-day session on this device). */
  setGuestName: (name: string) => void;
  /** Forgets the stored name ("Not you?"); the tag and visit dates stay. */
  clearGuestName: () => void;
  /** A new scope secret and so a new tag. Visit dates are kept, so it is not a new visitor. */
  startAsNewGuest: () => Promise<void>;
  /**
   * Signs out. A guest has no server session, so this forgets the name only; the tag and visit
   * dates stay (Decisions 20 Oct 2026). When member accounts land (R04) a member sign-out will
   * also post `/auth/logout`.
   */
  signOut: () => void;
}

const SessionContext = createContext<SessionContextValue>({
  session: { kind: 'guest', displayName: null, guestTag: null },
  isVerifiedMember: false,
  setGuestName: () => undefined,
  clearGuestName: () => undefined,
  startAsNewGuest: async () => undefined,
  signOut: () => undefined,
});

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [displayName, setDisplayName] = useState<string | null>(() => loadGuestName());
  const [guestTag, setGuestTag] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    loadGuestTag()
      .then((tag) => {
        if (active) setGuestTag(tag);
      })
      .catch(() => undefined); // no WebCrypto (insecure origin): the badge shows without a tag
    // Every app load counts this browser once per Dhaka day (API.md 5.14). Counting is best
    // effort: a failure is retried on the next load and never blocks the page.
    void recordDailyVisit().catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const setGuestName = useCallback((name: string) => {
    const normalized = normalizeGuestName(name);
    if (!normalized) return;
    saveGuestName(normalized);
    setDisplayName(normalized);
  }, []);

  const clearGuestName = useCallback(() => {
    saveGuestName(null);
    setDisplayName(null);
  }, []);

  const startAsNewGuest = useCallback(async () => {
    setGuestTag(await resetGuest());
  }, []);

  const signOut = useCallback(() => {
    signOutGuest();
    setDisplayName(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      session: { kind: 'guest', displayName, guestTag },
      isVerifiedMember: false,
      setGuestName,
      clearGuestName,
      startAsNewGuest,
      signOut,
    }),
    [displayName, guestTag, setGuestName, clearGuestName, startAsNewGuest, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = (): SessionContextValue => useContext(SessionContext);
