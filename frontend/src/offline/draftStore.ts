import type { CategoryRatings, ComfortTier, ReviewLanguage, TravellerType } from '../types';
import { withDb, type DraftRecord, type StoreResult } from './db';

/*
 * Review drafts kept on the device (R15 tasks 8 and 9; Offline-Frontend-Guideline 6.1 to 6.3).
 * PF 18.1 allows "the user's own drafts, with the receipt of an unsent draft". Drafts are stored
 * unencrypted; the form says so and offers Delete (Security 7.4).
 *
 * Not yet here (waiting for question Q1 in Handoff-Backend.md): a copy of the guest scope secret on
 * the draft (guideline 6.2), the stored Idempotency-Key, and sending queued drafts (task 10). Until
 * then a draft is sent from the form, online, exactly as before.
 *
 * Owner decisions, 7 Nov 2026: one draft per destination; when the sign-in cannot be confirmed
 * (offline), only guest drafts show and a new draft is saved as `pending`, then attached to the
 * member signed in when the app is next online (or to the guest when nobody is signed in).
 */

export type DraftAuthor = { kind: 'guest' } | { kind: 'member'; user_id: string } | { kind: 'pending' };

/** Who is looking: a guest, a confirmed member, or someone whose sign-in cannot be checked. */
export type DraftViewer = { kind: 'guest' } | { kind: 'member'; userId: string } | { kind: 'unknown' };

export interface DraftFields {
  display_name: string;
  /** null until the reviewer picks one; until then it follows the script they write in. */
  language: ReviewLanguage | null;
  traveller_type: TravellerType;
  comfort_tier: ComfortTier;
  visit_month: string;
  overall_rating: number;
  category_ratings: CategoryRatings;
  title: string;
  body: string;
  consent: boolean;
}

export interface StoredDraft extends DraftRecord {
  client_draft_id: string;
  /** '' while no destination is chosen yet. */
  destination_id: string;
  author: DraftAuthor;
  /** Created once with the draft, before any submission (PF 13.5). */
  receipt: string;
  fields: DraftFields;
  /** The consent text version the tick was given for; a newer text needs a new tick. */
  consent_version: string;
  /** Bumped on every saved change. */
  local_revision: number;
  state: 'DRAFT';
  created_at: string;
  updated_at: string;
}

/** Visibility (owner decision above): member drafts only to that member; pending only offline or to a member. */
export function canSee(draft: StoredDraft, viewer: DraftViewer): boolean {
  switch (draft.author.kind) {
    case 'guest':
      return viewer.kind !== 'member';
    case 'member':
      return viewer.kind === 'member' && viewer.userId === draft.author.user_id;
    case 'pending':
      return viewer.kind !== 'guest';
  }
}

/** The author a new draft gets for this viewer. */
export function authorFor(viewer: DraftViewer): DraftAuthor {
  if (viewer.kind === 'member') return { kind: 'member', user_id: viewer.userId };
  if (viewer.kind === 'unknown') return { kind: 'pending' };
  return { kind: 'guest' };
}

/** A draft worth keeping: something the reviewer actually wrote or chose. */
export function hasContent(fields: DraftFields): boolean {
  return fields.title.trim() !== '' || fields.body.trim() !== '' || fields.overall_rating > 0 || Object.keys(fields.category_ratings).length > 0;
}

/** This viewer's draft for one destination ('' = no destination chosen yet), newest first. */
export function findDraft(destinationId: string, viewer: DraftViewer): Promise<StoreResult<StoredDraft | null>> {
  return withDb(async (db) => {
    const all = (await db.getAll('drafts')) as StoredDraft[];
    const mine = all
      .filter((d) => d.destination_id === destinationId && canSee(d, viewer))
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return mine[0] ?? null;
  });
}

export function saveDraft(draft: StoredDraft): Promise<StoreResult<StoredDraft>> {
  return withDb(async (db) => {
    await db.put('drafts', draft);
    return draft;
  });
}

export function deleteDraft(clientDraftId: string): Promise<StoreResult<void>> {
  return withDb((db) => db.delete('drafts', clientDraftId));
}

/**
 * Once the sign-in is known online, drafts written while it could not be checked go to whoever is
 * signed in: the member, or the guest when nobody is (owner decision above). Returns how many moved.
 */
export function claimPendingDrafts(owner: Exclude<DraftAuthor, { kind: 'pending' }>): Promise<StoreResult<number>> {
  return withDb(async (db) => {
    const tx = db.transaction('drafts', 'readwrite');
    let claimed = 0;
    for (const draft of (await tx.store.getAll()) as StoredDraft[]) {
      if (draft.author.kind !== 'pending') continue;
      await tx.store.put({ ...draft, author: owner });
      claimed += 1;
    }
    await tx.done;
    return claimed;
  });
}
