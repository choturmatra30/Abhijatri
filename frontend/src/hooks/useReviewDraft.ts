import { useCallback, useEffect, useRef, useState } from 'react';
import { CONSENT_VERSION } from '../api/reviews';
import { useSession } from '../context/SessionContext';
import type { StorageFailure } from '../offline/db';
import {
  authorFor,
  claimPendingDrafts,
  deleteDraft,
  findDraft,
  hasContent,
  saveDraft,
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
}

/**
 * Keeps the review form's draft on the device (R15 tasks 8 and 9): one draft per destination,
 * restored when the form opens or the destination changes, saved as the reviewer types.
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
  const { session, status } = useSession();
  const viewer: DraftViewer | null =
    status === 'loading'
      ? null
      : status === 'unreachable'
        ? { kind: 'unknown' }
        : session.kind === 'member'
          ? { kind: 'member', userId: session.userId }
          : { kind: 'guest' };
  const viewerKey = viewer ? (viewer.kind === 'member' ? `member:${viewer.userId}` : viewer.kind) : 'none';

  const [draftStatus, setDraftStatus] = useState<DraftStatus>({ savedAt: null, restored: null, error: null });
  const meta = useRef<{ id: string; created_at: string; local_revision: number } | null>(null);
  const restoreRef = useRef(onRestore);
  restoreRef.current = onRestore;
  const startFresh = useRef(onStartFresh);
  startFresh.current = onStartFresh;
  // The snapshot the next save writes, so a destination change can flush it first.
  const latest = useRef({ destinationId, fields, identity });
  latest.current = { destinationId, fields, identity };
  const timer = useRef<number | undefined>(undefined);
  // What the scheduled save will write, captured when it was scheduled (old destination included).
  const pending = useRef<{ destinationId: string; fields: DraftFields; identity: DraftIdentity } | null>(null);
  // The last content written, so an unchanged form (e.g. right after a restore) is not saved again.
  const lastWritten = useRef<string | null>(null);
  const loadedFor = useRef<string | null>(null);
  // True while the draft for a newly chosen destination is being looked up: autosave waits.
  const looking = useRef(false);

  const write = useCallback(
    async (snapshot: { destinationId: string; fields: DraftFields; identity: DraftIdentity }) => {
      if (!viewer || !hasContent(snapshot.fields)) return;
      const signature = JSON.stringify([snapshot.identity.clientDraftId, snapshot.destinationId, snapshot.fields]);
      if (signature === lastWritten.current) return;
      const now = new Date().toISOString();
      const previous = meta.current?.id === snapshot.identity.clientDraftId ? meta.current : null;
      const draft: StoredDraft = {
        client_draft_id: snapshot.identity.clientDraftId,
        destination_id: snapshot.destinationId,
        author: authorFor(viewer),
        receipt: snapshot.identity.receipt,
        fields: snapshot.fields,
        consent_version: CONSENT_VERSION,
        local_revision: (previous?.local_revision ?? 0) + 1,
        state: 'DRAFT',
        created_at: previous?.created_at ?? now,
        updated_at: now,
      };
      const result = await saveDraft(draft);
      if (result.ok) {
        lastWritten.current = signature;
        meta.current = { id: draft.client_draft_id, created_at: draft.created_at, local_revision: draft.local_revision };
        setDraftStatus((s) => ({ ...s, savedAt: now, error: null }));
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
          meta.current = { id: draft.client_draft_id, created_at: draft.created_at, local_revision: draft.local_revision };
          lastWritten.current = JSON.stringify([draft.client_draft_id, draft.destination_id, draft.fields]);
          restoreRef.current(draft);
          setDraftStatus({ savedAt: draft.updated_at, restored: { destinationId, at: draft.updated_at }, error: null });
        }
        // Otherwise it is the draft already in the form (e.g. only the sign-in became known): keep typing.
      } else if (previousDestination === null || previousDestination === '' || previousDestination === destinationId) {
        // First load, text typed before a destination was chosen, or only the sign-in changed:
        // the text in the form belongs to this destination.
        void write(latest.current);
      } else {
        // A different destination with no draft of its own: the previous one keeps its draft, and
        // this one starts fresh.
        meta.current = null;
        lastWritten.current = null;
        startFresh.current();
        setDraftStatus({ savedAt: null, restored: null, error: null });
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

  /** Removes the current draft from the device (the form clears itself). */
  const discard = useCallback(async () => {
    if (timer.current !== undefined) window.clearTimeout(timer.current);
    timer.current = undefined;
    pending.current = null;
    const result = await deleteDraft(latest.current.identity.clientDraftId);
    meta.current = null;
    lastWritten.current = null;
    setDraftStatus({ savedAt: null, restored: null, error: result.ok ? null : result.reason });
    return result.ok;
  }, []);

  return { draftStatus, discard, ready: viewer !== null };
}
