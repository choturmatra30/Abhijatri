import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { loadGuestName, normalizeGuestName, registerGuestVisit, saveGuestName } from '../api/guests';

/**
 * Who is using the app. The interface adapts to it (for example, photo upload is offered only to
 * Verified Members), but it is never an authorization boundary: the API decides every permission
 * server-side (Review.md 1.1, PF 8).
 *
 * Every visitor is a guest until the account service exists (R04). A guest may give a name on
 * `/guest`; it stays on this device and the server only returns a stable "Guest #N" (API.md
 * 5.14). The member and verified states are filled from `GET /api/v1/auth/session` when R04
 * lands; nothing on the client can set them.
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
}

const SessionContext = createContext<SessionContextValue>({
  session: { kind: 'guest', displayName: null, guestNumber: null },
  isVerifiedMember: false,
  setGuestName: async () => undefined,
  clearGuestName: () => undefined,
});

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [displayName, setDisplayName] = useState<string | null>(loadGuestName);
  const [guestNumber, setGuestNumber] = useState<number | null>(null);

  // A guest number is only a courtesy; a failed request leaves the welcome without it.
  const fetchNumber = useCallback(async () => {
    try {
      setGuestNumber((await registerGuestVisit()).guest_number);
    } catch {
      setGuestNumber(null);
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

  const value = useMemo<SessionContextValue>(
    () => ({
      session: { kind: 'guest', displayName, guestNumber },
      isVerifiedMember: false,
      setGuestName,
      clearGuestName,
    }),
    [displayName, guestNumber, setGuestName, clearGuestName],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = (): SessionContextValue => useContext(SessionContext);
