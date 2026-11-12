import type { CategoryRatings, ComfortTier, ReviewLanguage, ReviewStatus, TravellerType } from '../types';
import { withDb, type DraftRecord, type StoreResult } from './db';

/*
 * Review drafts kept on the device (R15; Offline-Frontend-Guideline 6.1 to 6.6). PF 18.1 allows "the
 * user's own drafts, with the receipt of an unsent draft". Drafts are stored unencrypted; the form
 * says so and offers Delete (Security 7.4).
 *
 * Owner decisions, 7 Nov 2026: one draft per destination; when the sign-in cannot be confirmed
 * (offline), only guest drafts show and a new draft is saved as `pending`, then attached to the
 * member signed in when the app is next online (or to the guest when nobody is signed in).
 *
 * Owner decisions, 9 Nov 2026 (R15 part 2): a draft is sent from the review form (opened from the
 * saved-drafts list), so `READY` of guideline 6.1 is the `DRAFT` state here; nothing is ever sent
 * automatically. Every acknowledged review keeps its receipt on the device until the user confirms
 * they saved it, or for 7 days (guideline 6.5, Decisions 2026-11-08). Export only, no import.
 */

export type DraftAuthor = { kind: 'guest' } | { kind: 'member'; user_id: string } | { kind: 'pending' };

/** Who is looking: a guest, a confirmed member, or someone whose sign-in cannot be checked. */
export type DraftViewer = { kind: 'guest' } | { kind: 'member'; userId: string } | { kind: 'unknown' };

/**
 * Device states (guideline 6.1). `DRAFT` is written or ready to send; `SUBMITTING` is set before the
 * request so a crash mid-send is recovered as a retry; `NEEDS_ATTENTION` needs a change by the user;
 * `ACKNOWLEDGED` means the server has the review and only its receipt is still kept.
 */
export type DraftState = 'DRAFT' | 'SUBMITTING' | 'NEEDS_ATTENTION' | 'ACKNOWLEDGED';

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

export interface DraftError {
  code: string;
  message: string;
  request_id: string | null;
}

export interface AcknowledgedReview {
  review_id: string;
  status: ReviewStatus;
  version: number;
  duplicate_recovered: boolean;
}

export interface StoredDraft extends DraftRecord {
  client_draft_id: string;
  /** '' while no destination is chosen yet. */
  destination_id: string;
  author: DraftAuthor;
  /** Created once with the draft, before any submission (PF 13.5). */
  receipt: string;
  /**
   * Guest and pending drafts: the device's guest scope secret when the draft was created. The draft is
   * always sent with this copy, never the current one, so "Start as a new guest" cannot turn a retry
   * into a second review (guideline 6.2 trap 1, Decisions 2026-11-08). null for member drafts.
   */
  scope_secret: string | null;
  fields: DraftFields;
  /** The consent text version the tick was given for; a newer text needs a new tick. */
  consent_version: string;
  /** Bumped on every saved change. */
  local_revision: number;
  /** `Idempotency-Key` (R16), kept across restarts; renewed only when the request changes. */
  idempotency_key: string;
  /** SHA-256 of the request the key was last sent with; null until first sent. */
  key_signature: string | null;
  /** SHA-256 of the first request ever sent. A later different one means "edited after sending" (trap 2). */
  first_sent_signature: string | null;
  state: DraftState;
  last_error: DraftError | null;
  /** ISO time before which the server asked not to send again (`Retry-After`). */
  retry_after: string | null;
  /** Set when the server acknowledged the review. */
  review: AcknowledgedReview | null;
  acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

/** How long an acknowledged review keeps its receipt on the device without confirmation (guideline 6.5). */
export const RECEIPT_KEEP_DAYS = 7;

/** Fired on `window` whenever drafts change, so lists, the banner and the sidebar count refresh. */
export const DRAFTS_CHANGED_EVENT = 'abhijatri:drafts-changed';

function notify(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(DRAFTS_CHANGED_EVENT));
}

/** Fills the fields added in R15 part 2 for drafts saved by part 1 (7 Nov 2026). */
export function normaliseDraft(raw: StoredDraft): StoredDraft {
  return {
    ...raw,
    scope_secret: raw.scope_secret ?? null,
    idempotency_key: raw.idempotency_key ?? crypto.randomUUID(),
    key_signature: raw.key_signature ?? null,
    first_sent_signature: raw.first_sent_signature ?? null,
    state: raw.state ?? 'DRAFT',
    last_error: raw.last_error ?? null,
    retry_after: raw.retry_after ?? null,
    review: raw.review ?? null,
    acknowledged_at: raw.acknowledged_at ?? null,
  };
}

/** Not yet acknowledged by the server: still a draft to the user. */
export const isUnsent = (draft: StoredDraft): boolean => draft.state !== 'ACKNOWLEDGED';

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

/** A new draft record. Guest and pending drafts take a copy of the device's guest scope now (6.2). */
export function createDraft(params: {
  clientDraftId: string;
  receipt: string;
  destinationId: string;
  author: DraftAuthor;
  fields: DraftFields;
  consentVersion: string;
  scopeSecret: string | null;
  now: string;
}): StoredDraft {
  return {
    client_draft_id: params.clientDraftId,
    destination_id: params.destinationId,
    author: params.author,
    receipt: params.receipt,
    scope_secret: params.author.kind === 'member' ? null : params.scopeSecret,
    fields: params.fields,
    consent_version: params.consentVersion,
    local_revision: 1,
    idempotency_key: crypto.randomUUID(),
    key_signature: null,
    first_sent_signature: null,
    state: 'DRAFT',
    last_error: null,
    retry_after: null,
    review: null,
    acknowledged_at: null,
    created_at: params.now,
    updated_at: params.now,
  };
}

/**
 * The record after the user changed the form. Identity, key and scope copy are kept; a draft that
 * needed a change is ready again once changed. A `Retry-After` wait still applies.
 */
export function editedDraft(base: StoredDraft, change: { destinationId: string; fields: DraftFields; consentVersion: string; now: string }): StoredDraft {
  const fixing = base.state === 'NEEDS_ATTENTION';
  return {
    ...base,
    destination_id: change.destinationId,
    fields: change.fields,
    consent_version: change.consentVersion,
    local_revision: base.local_revision + 1,
    state: fixing ? 'DRAFT' : base.state,
    last_error: fixing ? null : base.last_error,
    updated_at: change.now,
  };
}

async function readAll(db: Parameters<Parameters<typeof withDb>[0]>[0]): Promise<StoredDraft[]> {
  return ((await db.getAll('drafts')) as StoredDraft[]).map(normaliseDraft);
}

const newestFirst = (a: StoredDraft, b: StoredDraft) => b.updated_at.localeCompare(a.updated_at);

/** This viewer's unsent draft for one destination ('' = no destination chosen yet), newest first. */
export function findDraft(destinationId: string, viewer: DraftViewer): Promise<StoreResult<StoredDraft | null>> {
  return withDb(async (db) => {
    const mine = (await readAll(db)).filter((d) => d.destination_id === destinationId && isUnsent(d) && canSee(d, viewer)).sort(newestFirst);
    return mine[0] ?? null;
  });
}

export function getDraft(clientDraftId: string): Promise<StoreResult<StoredDraft | null>> {
  return withDb(async (db) => {
    const found = (await db.get('drafts', clientDraftId)) as StoredDraft | undefined;
    return found ? normaliseDraft(found) : null;
  });
}

/** Every draft and kept receipt this viewer may see, newest first. */
export function listDrafts(viewer: DraftViewer): Promise<StoreResult<StoredDraft[]>> {
  return withDb(async (db) => (await readAll(db)).filter((d) => canSee(d, viewer)).sort(newestFirst));
}

export async function saveDraft(draft: StoredDraft): Promise<StoreResult<StoredDraft>> {
  const result = await withDb(async (db) => {
    await db.put('drafts', draft);
    return draft;
  });
  if (result.ok) notify();
  return result;
}

/** Read, change and write one draft in a single transaction; null when it no longer exists. */
export async function updateDraft(clientDraftId: string, change: (draft: StoredDraft) => StoredDraft): Promise<StoreResult<StoredDraft | null>> {
  const result = await withDb(async (db) => {
    const tx = db.transaction('drafts', 'readwrite');
    const found = (await tx.store.get(clientDraftId)) as StoredDraft | undefined;
    if (!found) {
      await tx.done;
      return null;
    }
    const next = change(normaliseDraft(found));
    await tx.store.put(next);
    await tx.done;
    return next;
  });
  if (result.ok) notify();
  return result;
}

export async function deleteDraft(clientDraftId: string): Promise<StoreResult<void>> {
  const result = await withDb((db) => db.delete('drafts', clientDraftId));
  if (result.ok) notify();
  return result;
}

/** "Clear all": every unsent draft this viewer may see. Kept receipts are not touched. Returns how many. */
export async function clearUnsentDrafts(viewer: DraftViewer): Promise<StoreResult<number>> {
  const result = await withDb(async (db) => {
    const tx = db.transaction('drafts', 'readwrite');
    let removed = 0;
    for (const draft of ((await tx.store.getAll()) as StoredDraft[]).map(normaliseDraft)) {
      if (!isUnsent(draft) || !canSee(draft, viewer)) continue;
      await tx.store.delete(draft.client_draft_id);
      removed += 1;
    }
    await tx.done;
    return removed;
  });
  if (result.ok) notify();
  return result;
}

/** This member's own unsent drafts (not pending ones), for the sign-out warning (guideline 6.7). */
export const isMembersUnsent = (draft: StoredDraft, userId: string): boolean =>
  isUnsent(draft) && draft.author.kind === 'member' && draft.author.user_id === userId;

/** Sign-out with "Delete drafts": removes this member's unsent drafts only. Returns how many. */
export async function deleteMemberDrafts(userId: string): Promise<StoreResult<number>> {
  const result = await withDb(async (db) => {
    const tx = db.transaction('drafts', 'readwrite');
    let removed = 0;
    for (const draft of ((await tx.store.getAll()) as StoredDraft[]).map(normaliseDraft)) {
      if (!isMembersUnsent(draft, userId)) continue;
      await tx.store.delete(draft.client_draft_id);
      removed += 1;
    }
    await tx.done;
    return removed;
  });
  if (result.ok) notify();
  return result;
}

/**
 * Once the sign-in is known online, drafts written while it could not be checked go to whoever is
 * signed in: the member, or the guest when nobody is (owner decision above). Returns how many moved.
 */
export async function claimPendingDrafts(owner: Exclude<DraftAuthor, { kind: 'pending' }>): Promise<StoreResult<number>> {
  const result = await withDb(async (db) => {
    const tx = db.transaction('drafts', 'readwrite');
    let claimed = 0;
    for (const draft of ((await tx.store.getAll()) as StoredDraft[]).map(normaliseDraft)) {
      if (draft.author.kind !== 'pending') continue;
      // A member's review carries no guest scope; a guest keeps the copy taken when it was written.
      await tx.store.put({ ...draft, author: owner, scope_secret: owner.kind === 'member' ? null : draft.scope_secret });
      claimed += 1;
    }
    await tx.done;
    return claimed;
  });
  if (result.ok && result.value > 0) notify();
  return result;
}

/**
 * App start (guideline 6.1 and 6.5): a draft left `SUBMITTING` by a closed tab or a crash goes back to
 * `DRAFT` (its retry is safe: same draft id, receipt and key), and receipts acknowledged more than
 * 7 days ago are deleted. Returns the counts, for tests.
 */
export async function maintainDrafts(now: Date = new Date()): Promise<StoreResult<{ recovered: number; purged: number }>> {
  const cutoff = now.getTime() - RECEIPT_KEEP_DAYS * 24 * 60 * 60 * 1000;
  const result = await withDb(async (db) => {
    const tx = db.transaction('drafts', 'readwrite');
    let recovered = 0;
    let purged = 0;
    for (const draft of ((await tx.store.getAll()) as StoredDraft[]).map(normaliseDraft)) {
      if (draft.state === 'SUBMITTING') {
        await tx.store.put({ ...draft, state: 'DRAFT' });
        recovered += 1;
      } else if (draft.state === 'ACKNOWLEDGED' && Date.parse(draft.acknowledged_at ?? draft.updated_at) < cutoff) {
        await tx.store.delete(draft.client_draft_id);
        purged += 1;
      }
    }
    await tx.done;
    return { recovered, purged };
  });
  if (result.ok && result.value.recovered + result.value.purged > 0) notify();
  return result;
}

let maintained: Promise<unknown> | null = null;
/** `maintainDrafts` once per page load. */
export function maintainDraftsOnce(): Promise<unknown> {
  maintained ??= maintainDrafts();
  return maintained;
}

export interface DraftExport {
  format: 'abhijatri-review-drafts';
  version: 1;
  exported_at: string;
  /** True only when the user explicitly confirmed including receipts (guideline 6.6). */
  includes_receipts: boolean;
  drafts: {
    client_draft_id: string;
    destination_id: string;
    destination_name: string | null;
    author: 'guest' | 'member' | 'pending';
    fields: DraftFields;
    consent_version: string;
    created_at: string;
    updated_at: string;
    receipt?: string;
  }[];
}

/**
 * Export file of unsent drafts (PF 18.2, guideline 6.6). Receipts of acknowledged reviews are never
 * included; an unsent draft's receipt only when `includeReceipts` (explicit confirmation). The guest
 * scope secret and the idempotency key are never exported.
 */
export function buildDraftExport(
  drafts: StoredDraft[],
  options: { includeReceipts: boolean; destinationName: (id: string) => string | null; now?: Date },
): DraftExport {
  return {
    format: 'abhijatri-review-drafts',
    version: 1,
    exported_at: (options.now ?? new Date()).toISOString(),
    includes_receipts: options.includeReceipts,
    drafts: drafts.filter(isUnsent).map((d) => ({
      client_draft_id: d.client_draft_id,
      destination_id: d.destination_id,
      destination_name: d.destination_id ? options.destinationName(d.destination_id) : null,
      author: d.author.kind,
      fields: d.fields,
      consent_version: d.consent_version,
      created_at: d.created_at,
      updated_at: d.updated_at,
      ...(options.includeReceipts ? { receipt: d.receipt } : {}),
    })),
  };
}
