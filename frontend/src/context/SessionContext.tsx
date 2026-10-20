import React, { createContext, useContext } from 'react';

/**
 * Who is using the app. The interface adapts to it (for example, photo upload is offered only to
 * Verified Members), but it is never an authorization boundary: the API decides every permission
 * server-side (Review.md 1.1, PF 8).
 *
 * Every visitor is a guest until the account service exists (R04). The member and verified
 * states are filled from `GET /api/v1/auth/session` when R04 lands; nothing on the client can
 * set them.
 */
export type Session =
  | { kind: 'guest' }
  | { kind: 'member'; displayName: string; verifiedMember: boolean };

interface SessionContextValue {
  session: Session;
  isVerifiedMember: boolean;
}

const GUEST: SessionContextValue = { session: { kind: 'guest' }, isVerifiedMember: false };

const SessionContext = createContext<SessionContextValue>(GUEST);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <SessionContext.Provider value={GUEST}>{children}</SessionContext.Provider>
);

export const useSession = (): SessionContextValue => useContext(SessionContext);
