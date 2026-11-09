import { lazy, Suspense, useState } from 'react';
import { useSession } from '../../context/SessionContext';
import { deleteMemberDrafts, isMembersUnsent, listDrafts } from '../../offline/draftStore';

const SignOutDraftsDialog = lazy(() => import('./SignOutDraftsDialog'));

/**
 * Sign-out with unsent member drafts (Offline-Frontend-Guideline 6.7, default "warn, then keep or
 * delete"). Kept drafts stay on the device and show only to the same member when they sign in again.
 * Without such drafts it signs out at once, as before.
 */
export function useGuardedSignOut() {
  const { session, signOut } = useSession();
  const [asking, setAsking] = useState<{ count: number; userId: string; after?: () => void } | null>(null);
  const [busy, setBusy] = useState(false);

  const finish = async (after?: () => void) => {
    await signOut();
    after?.();
  };

  const request = async (after?: () => void) => {
    if (session.kind === 'member') {
      const userId = session.userId;
      const listed = await listDrafts({ kind: 'member', userId });
      const count = listed.ok ? listed.value.filter((d) => isMembersUnsent(d, userId)).length : 0;
      if (count > 0) {
        setAsking({ count, userId, after });
        return;
      }
    }
    await finish(after);
  };

  const choose = async (removeDrafts: boolean) => {
    if (!asking) return;
    setBusy(true);
    if (removeDrafts) await deleteMemberDrafts(asking.userId);
    const { after } = asking;
    setAsking(null);
    setBusy(false);
    await finish(after);
  };

  const dialog = asking ? (
    <Suspense fallback={null}>
      <SignOutDraftsDialog count={asking.count} busy={busy} onCancel={() => setAsking(null)} onChoose={(remove) => void choose(remove)} />
    </Suspense>
  ) : null;

  return { request, dialog };
}
