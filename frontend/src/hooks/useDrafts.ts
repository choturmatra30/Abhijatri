import { useEffect, useState } from 'react';
import type { StorageFailure } from '../offline/db';
import { claimPendingDrafts, DRAFTS_CHANGED_EVENT, isUnsent, listDrafts, maintainDraftsOnce, type StoredDraft } from '../offline/draftStore';
import { useDraftViewer, viewerKeyOf } from './useReviewDraft';

export interface DraftsView {
  /** Drafts not yet acknowledged by the server, newest first. */
  unsent: StoredDraft[];
  /** Acknowledged reviews whose receipt the user has not confirmed saving yet (guideline 6.5). */
  unconfirmed: StoredDraft[];
  loaded: boolean;
  error: StorageFailure | null;
}

/**
 * The drafts this viewer may see on this device (R15). Refreshes when drafts change in this tab and
 * when the tab becomes visible again (another tab may have changed them). The first call per page
 * load also recovers interrupted sends and deletes receipts older than 7 days. Once the sign-in is
 * known, drafts written while it could not be checked go to their owner first (owner decision
 * 7 Nov 2026), so a draft written offline is counted on any page, not only after the form opened.
 */
export function useDrafts(): DraftsView {
  const viewer = useDraftViewer();
  const viewerKey = viewerKeyOf(viewer);
  const [view, setView] = useState<DraftsView>({ unsent: [], unconfirmed: [], loaded: false, error: null });

  useEffect(() => {
    if (!viewer) return undefined;
    let cancelled = false;
    const load = async () => {
      await maintainDraftsOnce();
      if (viewer.kind !== 'unknown') {
        await claimPendingDrafts(viewer.kind === 'member' ? { kind: 'member', user_id: viewer.userId } : { kind: 'guest' });
      }
      const result = await listDrafts(viewer);
      if (cancelled) return;
      if (!result.ok) {
        setView({ unsent: [], unconfirmed: [], loaded: true, error: result.reason });
        return;
      }
      setView({
        unsent: result.value.filter(isUnsent),
        unconfirmed: result.value.filter((d) => !isUnsent(d) && d.review !== null),
        loaded: true,
        error: null,
      });
    };
    void load();
    const onChange = () => void load();
    const onVisible = () => {
      if (document.visibilityState === 'visible') void load();
    };
    window.addEventListener(DRAFTS_CHANGED_EVENT, onChange);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      window.removeEventListener(DRAFTS_CHANGED_EVENT, onChange);
      document.removeEventListener('visibilitychange', onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewerKey]);

  return view;
}
