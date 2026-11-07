import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getSession, login as loginRequest, logout as logoutRequest } from '../api/auth';
import { AUTH_REQUIRED_EVENT } from '../api/client';
import type { AuthSession, StaffRole } from '../types';
import { ApiError, NETWORK_ERROR, TIMEOUT_ERROR } from '../api/client';
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
 * A visitor is a guest until they sign in (R04). Each browser has a guest tag
 * such as `1C669-J0TDY`, derived on the device from the guest scope secret
 * (Guest-Identity-and-Visits 3.1). A guest may give a name on `/guest`; it stays on this device for
 * 30 days after the last visit. The server only counts visits per day and never learns who visited.
 * The member and verified states are filled from `GET /api/v1/auth/session` when R04 lands;
 * nothing on the client can set them.
 */
export type Session =
  | { kind: 'guest'; displayName: string | null; guestTag: string | null }
  | { kind: 'member'; userId: string; displayName: string; email: string; verifiedMember: boolean; role: StaffRole | null };

interface SessionContextValue {
  session: Session;
  isVerifiedMember: boolean;
  /** loading until the first answer from GET /auth/session; the page renders as a guest meanwhile. */
  /** `unreachable`: the server could not be asked (offline or down), so the sign-in is unknown. */
  status: 'loading' | 'ready' | 'unreachable';
  /** Signs in with the account service; throws ApiError (code INVALID_CREDENTIALS, EMAIL_NOT_VERIFIED, RATE_LIMITED, ...). */
  signIn: (email: string, password: string) => Promise<void>;
  refresh: () => Promise<void>;
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
  signOut: () => Promise<void>;
  /** True after a signed-in member's session ended on the server (expired or revoked). */
  sessionExpired: boolean;
  dismissSessionExpired: () => void;
}

const SessionContext = createContext<SessionContextValue>({
  session: { kind: 'guest', displayName: null, guestTag: null },
  isVerifiedMember: false,
  status: 'loading',
  signIn: async () => undefined,
  refresh: async () => undefined,
  setGuestName: () => undefined,
  clearGuestName: () => undefined,
  startAsNewGuest: async () => undefined,
  signOut: async () => undefined,
  sessionExpired: false,
  dismissSessionExpired: () => undefined,
});

/** True when the server gave no answer: offline, timed out, or a gateway error. */
function isUnreachable(error: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  if (!(error instanceof ApiError)) return false;
  return error.code === NETWORK_ERROR || error.code === TIMEOUT_ERROR || [502, 503, 504].includes(error.status);
}

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [displayName, setDisplayName] = useState<string | null>(() => loadGuestName());
  const [guestTag, setGuestTag] = useState<string | null>(null);
  const [account, setAccount] = useState<Extract<AuthSession, { authenticated: true }> | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'unreachable'>('loading');
  const [sessionExpired, setSessionExpired] = useState(false);

  // Any API call answering 401 AUTH_REQUIRED while we believe a member is signed in means the
  // server session ended (idle or absolute timeout, sign-out elsewhere, revocation). Drop to the
  // guest view at once instead of failing every later request, and say why.
  useEffect(() => {
    const onAuthRequired = () => {
      setAccount((current) => {
        if (current) setSessionExpired(true);
        return null;
      });
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
  }, []);

  useEffect(() => {
    let active = true;
    loadGuestTag()
      .then((tag) => {
        if (active) setGuestTag(tag);
      })
      .catch(() => undefined); // no WebCrypto (insecure origin): the badge shows without a tag
    // Ask the server who this is. A signed-in member is counted by the server (GET /auth/session);
    // everyone else is counted once per Dhaka day as a guest (API.md 5.14). Both are best effort:
    // a failure is retried on the next load and never blocks the page.
    getSession()
      .then((answer) => {
        if (!active) return;
        if (answer.authenticated) setAccount(answer);
        else void recordDailyVisit().catch(() => undefined);
      })
      .then(() => {
        if (active) setStatus('ready');
      })
      .catch((error: unknown) => {
        if (!active) return;
        // No answer at all (offline, timeout, server down): the sign-in is unknown, not "guest".
        if (isUnreachable(error)) return setStatus('unreachable');
        void recordDailyVisit().catch(() => undefined); // accounts unavailable: still a guest
        setStatus('ready');
      });
    return () => {
      active = false;
    };
  }, []);

  /** Re-reads the session, e.g. after a verification was approved or the connection came back. */
  const refresh = useCallback(async () => {
    try {
      const answer = await getSession();
      setAccount(answer.authenticated ? answer : null);
      setStatus('ready');
    } catch (error) {
      if (isUnreachable(error)) setStatus((s) => (s === 'ready' ? s : 'unreachable'));
    }
  }, []);

  // Back online after an unreachable start: ask again, so account pages recover by themselves.
  useEffect(() => {
    if (status !== 'unreachable') return undefined;
    const retry = () => void refresh();
    window.addEventListener('online', retry);
    const timer = window.setInterval(retry, 30_000);
    return () => {
      window.removeEventListener('online', retry);
      window.clearInterval(timer);
    };
  }, [status, refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const answer = await loginRequest(email, password);
    if (answer.authenticated) {
      setAccount(answer);
      setSessionExpired(false);
    }
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

  const signOut = useCallback(async () => {
    if (account) {
      // End the server session; the page returns to the guest view whether or not the call succeeds.
      // Resolves once the guest view is in place, so callers can wait before moving on.
      await logoutRequest().catch(() => undefined);
      setAccount(null);
      return;
    }
    signOutGuest();
    setDisplayName(null);
  }, [account]);

  const dismissSessionExpired = useCallback(() => setSessionExpired(false), []);

  const value = useMemo<SessionContextValue>(
    () => ({
      session: account
        ? {
            kind: 'member',
            userId: account.user.id,
            displayName: account.user.display_name,
            email: account.user.email,
            verifiedMember: account.verified_member, // an approved verification, not email verification alone
            role: account.role,
          }
        : { kind: 'guest', displayName, guestTag },
      isVerifiedMember: Boolean(account?.verified_member),
      status,
      signIn,
      refresh,
      setGuestName,
      clearGuestName,
      startAsNewGuest,
      signOut,
      sessionExpired,
      dismissSessionExpired,
    }),
    [account, displayName, guestTag, status, signIn, refresh, setGuestName, clearGuestName, startAsNewGuest, signOut, sessionExpired, dismissSessionExpired],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = (): SessionContextValue => useContext(SessionContext);
