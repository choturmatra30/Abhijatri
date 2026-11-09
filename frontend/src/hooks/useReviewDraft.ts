import { useCallback, useEffect, useRef, useState } from 'react';
import { CONSENT_VERSION, getGuestScopeSecret } from '../api/reviews';
import { useSession } from '../context/SessionContext';
import type { StorageFailure } from '../offline/db';
import {
  authorFor,
  claimPendingDrafts,
  createDraft,
  deleteDraft,
  DRAFTS_CHANGED_EVENT,
  editedDraft,
  findDraft,
  getDraft,
  hasContent,
  saveDraft,
  type DraftError,
  type DraftFields,
  type DraftViewer,
  type StoredDraft,
} from '../offline/draftStore';

/** Debounce for autosave (Offline-Frontend-Guideline 6.3). */
export const AUTOSAVE_MS = 500;

export interface DraftIdentity {
  clientDraftId: string;
  receipt: string;
}

export interface DraftStatus {
  /** When the current draft was last written to this device. */
  savedAt: string | null;
  /** Set when a saved draft was put back into the form. */
  restored: { destinationId: string; at: string } | null;
  /** Saving is not possible on this device (storage full or unavailable). */
  error: StorageFailure | null;
  /** The answer of the last attempt to send this draft, when it was not accepted. */
  lastSendError: DraftError | null;
  /** The server asked not to send again before this time (`Retry-After`). */
  retryAfter: string | null;
  /** The last attempt needs a change by the reviewer before sending again. */
  needsAttention: boolean;
}

const EMPTY_STATUS: DraftStatus = { savedAt: null, restored: null, error: null, lastSendError: null, retryAfter: null, needsAttention: false };

const sendStatus = (draft: StoredDraft) => ({
  lastSendError: draft.last_error,
  retryAfter: draft.retry_after,
  needsAttention: draft.state === 'NEEDS_ATTENTION',
});

/** Who the drafts belong to right now; null while the sign-in is still being checked. */
export function useDraftViewer(): DraftViewer | null {
  const { session, status } = useSession();
  if (status === 'loading') return null;
  if (status === 'unreachable') return { kind: 'unknown' };
  return session.kind === 'member' ? { kind: 'member', userId: session.userId } : { kind: 'guest' };
}

export const viewerKeyOf = (viewer: DraftViewer | null) =>
  viewer ? (viewer.kind === 'member' ? `member:${viewer.userId}` : viewer.kind) : 'none';

type Snapshot = { destinationId: string; fields: DraftFields; identity: DraftIdentity };
const signatureOf = (id: string, destinationId: string, fields: DraftFields) => JSON.stringify([id, destinationId, fields]);

/**
 * Keeps the review form's draft on the device (R15): one draft per destination, restored when the form
 * opens or the destination changes, saved as the reviewer types. Saving merges into the stored record,
 * so its identity, `Idempotency-Key`, guest scope copy and state survive (guideline 6.2).
 */
export function useReviewDraft({
  destinationId,
  fields,
  identity,
  onRestore,
  onStartFresh,
}: {
  destinationId: string;
  fields: DraftFields;
  identity: DraftIdentity;
  /** Puts a saved draft into the form (its fields and its identity). */
  onRestore: (draft: StoredDraft) => void;
  /** Clears the form with a new identity: a destination with no draft of its own. */
  onStartFresh: () => void;
}) {
  const viewer = useDraftViewer();
  const viewerKey = viewerKeyOf(viewer);

  const [draftStatus, setDraftStatus] = useState<DraftStatus>(EMPTY_STATUS);
  const restoreRef = useRef(onRestore);
  restoreRef.current = onRestore;
  const startFresh = useRef(onStartFresh);
  startFresh.current = onStartFresh;
  // The snapshot the next save writes, so a destination change can flush it first.
  const latest = useRef<Snapshot>({ destinationId, fields, identity });
  latest.current = { destinationId, fields, identity };
  const timer = useRef<number | undefined>(undefined);
  // What the scheduled save will write, captured when it was scheduled (old destination included).
  const pending = useRef<Snapshot | null>(null);
  // The last content written, so an unchanged form (e.g. right after a restore) is not saved again.
  const lastWritten = useRef<string | null>(null);
  const loadedFor = useRef<string | null>(null);
  // True while the draft for a newly chosen destination is being looked up: autosave waits.
  const looking = useRef(false);
  // When the device cannot store drafts: the draft being sent, kept in memory so retries reuse its key.
  const memory = useRef<StoredDraft | null>(null);
  // True from prepareSend until the form settles the attempt: sending replaces and deletes records.
  const sending = useRef(false);

  /** The record this snapshot becomes: the stored one changed, or a new one. */
  const recordFor = (snapshot: Snapshot, base: StoredDraft | null, owner: DraftViewer, now: string): StoredDraft =>
    base
      ? editedDraft(base, { destinationId: snapshot.destinationId, fields: snapshot.fields, consentVersion: CONSENT_VERSION, now })
      : createDraft({
          clientDraftId: snapshot.identity.clientDraftId,
          receipt: snapshot.identity.receipt,
          destinationId: snapshot.destinationId,
          author: authorFor(owner),
          fields: snapshot.fields,
          consentVersion: CONSENT_VERSION,
          scopeSecret: owner.kind === 'member' ? null : getGuestScopeSecret(),
          now,
        });

  const write = useCallback(
    async (snapshot: Snapshot) => {
      if (!viewer || !hasContent(snapshot.fields)) return;
      const signature = signatureOf(snapshot.identity.clientDraftId, snapshot.destinationId, snapshot.fields);
      if (signature === lastWritten.current) return;
      const now = new Date().toISOString();
      const existing = await getDraft(snapshot.identity.clientDraftId);
      if (!existing.ok) {
        setDraftStatus((s) => ({ ...s, error: existing.reason }));
        return;
      }
      // Already acknowledged (a save scheduled just before sending): nothing to keep.
      if (existing.value?.state === 'ACKNOWLEDGED') return;
      const draft = recordFor(snapshot, existing.value, viewer, now);
      const result = await saveDraft(draft);
      if (result.ok) {
        lastWritten.current = signature;
        setDraftStatus((s) => ({ ...s, savedAt: now, error: null, ...sendStatus(draft) }));
      } else {
        setDraftStatus((s) => ({ ...s, error: result.reason }));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [viewerKey],
  );

  // Once the sign-in is known, drafts written while it could not be checked go to whoever is signed in.
  const claimed = useRef<Promise<unknown> | null>(null);
  if (viewer && viewer.kind !== 'unknown' && !claimed.current) {
    claimed.current = claimPendingDrafts(viewer.kind === 'member' ? { kind: 'member', user_id: viewer.userId } : { kind: 'guest' });
  }
  useEffect(() => {
    if (viewer?.kind === 'unknown') claimed.current = null; // claim again when the sign-in is known
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewerKey]);

  // Open the saved draft for this destination; if there is none, the current text moves to it.
  useEffect(() => {
    if (!viewer) return;
    const key = `${viewerKey}|${destinationId}`;
    if (loadedFor.current === key) return;
    const previous = loadedFor.current;
    loadedFor.current = key;
    looking.current = true;
    let cancelled = false;
    void (async () => {
      // Write the text being typed before switching, under the destination it was typed for.
      if (timer.current !== undefined && previous && pending.current) {
        window.clearTimeout(timer.current);
        timer.current = undefined;
        await write(pending.current);
      }
      if (claimed.current) await claimed.current; // look up only after pending drafts have an owner
      const found = await findDraft(destinationId, viewer);
      if (cancelled) return;
      looking.current = false;
      if (!found.ok) {
        setDraftStatus((s) => ({ ...s, error: found.reason }));
        return;
      }
      const draft = found.value;
      const previousDestination = previous === null ? null : previous.slice(previous.indexOf('|') + 1);
      if (draft) {
        if (draft.client_draft_id !== latest.current.identity.clientDraftId) {
          lastWritten.current = signatureOf(draft.client_draft_id, draft.destination_id, draft.fields);
          restoreRef.current(draft);
          setDraftStatus({ ...EMPTY_STATUS, savedAt: draft.updated_at, restored: { destinationId, at: draft.updated_at }, ...sendStatus(draft) });
        }
        // Otherwise it is the draft already in the form (e.g. only the sign-in became known): keep typing.
      } else if (previousDestination === null || previousDestination === '' || previousDestination === destinationId) {
        // First load, text typed before a destination was chosen, or only the sign-in changed:
        // the text in the form belongs to this destination.
        void write(latest.current);
      } else {
        // A different destination with no draft of its own: the previous one keeps its draft, and
        // this one starts fresh.
        lastWritten.current = null;
        startFresh.current();
        setDraftStatus(EMPTY_STATUS);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewerKey, destinationId]);

  // Autosave, 500 ms after the last change.
  const fieldsKey = JSON.stringify(fields);
  useEffect(() => {
    if (!viewer || !hasContent(fields)) return undefined;
    if (timer.current !== undefined) window.clearTimeout(timer.current);
    pending.current = { destinationId, fields, identity };
    timer.current = window.setTimeout(() => {
      timer.current = undefined;
      // While a destination's draft is being looked up, the lookup decides (restore or move).
      if (pending.current && !looking.current) void write(pending.current);
    }, AUTOSAVE_MS);
    return () => {
      if (timer.current !== undefined) window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldsKey, destinationId, identity.clientDraftId, viewerKey]);

  // The draft in the form was deleted elsewhere (Delete or Clear all in the drafts list, another tab):
  // clear the form instead of saving the text again under the deleted identity.
  useEffect(() => {
    const onChange = () => {
      if (lastWritten.current === null || sending.current) return;
      const id = latest.current.identity.clientDraftId;
      void getDraft(id).then((found) => {
        if (found.ok && found.value === null && lastWritten.current !== null && latest.current.identity.clientDraftId === id) {
          stopSaving();
          lastWritten.current = null;
          startFresh.current();
          setDraftStatus(EMPTY_STATUS);
        }
      });
    };
    window.addEventListener(DRAFTS_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(DRAFTS_CHANGED_EVENT, onChange);
  }, []);

  const stopSaving = () => {
    if (timer.current !== undefined) window.clearTimeout(timer.current);
    timer.current = undefined;
    pending.current = null;
  };

  /**
   * Saves the form now and returns the stored draft to send. When the device cannot store drafts, an
   * in-memory draft is returned instead (kept for retries in this page), so sending still works.
   */
  const prepareSend = useCallback(async (): Promise<StoredDraft | null> => {
    if (!viewer) return null;
    stopSaving();
    sending.current = true;
    const snapshot = latest.current;
    await write(snapshot);
    const found = await getDraft(snapshot.identity.clientDraftId);
    if (found.ok && found.value && found.value.state !== 'ACKNOWLEDGED') return found.value;
    const now = new Date().toISOString();
    const base = memory.current?.client_draft_id === snapshot.identity.clientDraftId ? memory.current : null;
    memory.current = recordFor(snapshot, base, viewer, now);
    return memory.current;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewerKey, write]);

  /** The form now holds this draft (after a send attempt): no rewrite of unchanged text, status shown. */
  const adopt = useCallback((draft: StoredDraft) => {
    lastWritten.current = signatureOf(draft.client_draft_id, draft.destination_id, draft.fields);
    if (memory.current) memory.current = draft;
    setDraftStatus((s) => ({ ...s, ...sendStatus(draft) }));
  }, []);

  /** The review was acknowledged: stop saving this draft (its record keeps the receipt for now). */
  const forget = useCallback(() => {
    stopSaving();
    memory.current = null;
    lastWritten.current = null;
    setDraftStatus(EMPTY_STATUS);
  }, []);

  /** The send attempt is over (any outcome): watching for deletions elsewhere resumes. */
  const settle = useCallback(() => {
    sending.current = false;
  }, []);

  /** Removes the current draft from the device (the form clears itself). */
  const discard = useCallback(async () => {
    stopSaving();
    memory.current = null;
    lastWritten.current = null;
    const result = await deleteDraft(latest.current.identity.clientDraftId);
    setDraftStatus({ ...EMPTY_STATUS, error: result.ok ? null : result.reason });
    return result.ok;
  }, []);

  return { draftStatus, discard, prepareSend, adopt, forget, settle, ready: viewer !== null };
}
