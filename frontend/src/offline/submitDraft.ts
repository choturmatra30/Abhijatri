import { ApiError, NETWORK_ERROR, TIMEOUT_ERROR } from '../api/client';
import { stableStringify } from '../api/idempotency';
import {
  buildGuestReviewPayload,
  detectReviewLanguage,
  generateReceipt,
  getGuestScopeSecret,
  submitGuestReview,
  submitMemberReview,
  type MemberReviewCreate,
} from '../api/reviews';
import type { GuestReviewCreate, GuestReviewCreated, ReviewLanguage } from '../types';
import { deleteDraft, saveDraft, updateDraft, type DraftError, type StoredDraft } from './draftStore';

/*
 * Sending one stored draft (R15 task 10; Offline-Frontend-Guideline 6.2 and 6.4). The user presses
 * Submit; nothing here runs by itself. What makes "a retry never creates a duplicate review" true:
 *
 * - the draft's own `client_draft_id`, receipt and guest scope copy are sent on every attempt;
 * - the `Idempotency-Key` is stored on the draft and reused while the request is unchanged, and
 *   renewed when it changes (the server refuses a known key with a different body);
 * - `SUBMITTING` is written before the request, so a crash mid-send comes back as a safe retry.
 *
 * Branch on `code`, never on `message`.
 */

/** What a failed answer means for the draft (guideline 6.4 table). */
export type FailureAction =
  /** Keep the draft ready with the same key; the user can send again (later). */
  | 'retry'
  /** The user must change something (field error, month taken, destination gone, account state). */
  | 'attention'
  /** The key was used for a different request: a bug in the key rules. New key, user sends again. */
  | 'new-key'
  /** Same draft id sent before with a different receipt: this identity is spent. */
  | 'identity-spent';

const RETRY_CODES = new Set([
  NETWORK_ERROR,
  TIMEOUT_ERROR,
  'IDEMPOTENCY_REQUEST_IN_PROGRESS',
  'CHALLENGE_FAILED',
  'CSRF_INVALID',
  'AUTH_REQUIRED',
  'RATE_LIMITED',
  'GUEST_WRITES_PAUSED',
  'SERVICE_UNAVAILABLE',
]);

export function classifyFailure(error: unknown): FailureAction {
  if (!(error instanceof ApiError)) return 'retry'; // not an answer from the server: the draft is safe
  if (error.code === 'IDEMPOTENCY_KEY_REUSED') return 'new-key';
  if (error.code === 'DRAFT_ALREADY_SUBMITTED') return 'identity-spent';
  if (RETRY_CODES.has(error.code)) return 'retry';
  if (error.status === 0 || error.status >= 500 || error.status === 408) return 'retry';
  return 'attention';
}

export type SendOutcome =
  | {
      kind: 'acknowledged';
      created: GuestReviewCreated;
      draft: StoredDraft;
      /** The server kept an earlier version: the local copy was changed after it was first sent (trap 2). */
      editedAfterFirstSend: boolean;
    }
  | { kind: 'failed'; action: FailureAction; error: unknown; draft: StoredDraft; retryAfterSeconds?: number };

/** SHA-256 (hex) of the request, keys sorted. Used to tell "same request" from "changed request". */
export async function requestSignature(request: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(stableStringify(request));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** The review language sent: the reviewer's choice, else the script written, else the interface. */
export function draftLanguage(draft: StoredDraft, interfaceLanguage: 'bn' | 'en'): ReviewLanguage {
  const f = draft.fields;
  return f.language ?? detectReviewLanguage(`${f.title} ${f.body}`) ?? (interfaceLanguage === 'en' ? 'EN' : 'BN');
}

/** The request body for this draft, without the single-use Turnstile token. */
export function draftRequest(draft: StoredDraft, interfaceLanguage: 'bn' | 'en', scopeSecret: string): { member: boolean; body: GuestReviewCreate | MemberReviewCreate } {
  const f = draft.fields;
  const payload = buildGuestReviewPayload({
    destinationId: draft.destination_id,
    clientDraftId: draft.client_draft_id,
    receipt: draft.receipt,
    guestScopeSecret: scopeSecret,
    displayName: f.display_name,
    language: draftLanguage(draft, interfaceLanguage),
    travellerType: f.traveller_type,
    comfortTier: f.comfort_tier,
    visitMonth: f.visit_month,
    title: f.title,
    note: f.body,
    overallRating: f.overall_rating,
    categoryRatings: f.category_ratings,
  });
  if (draft.author.kind === 'member') {
    const { guest_scope_secret: _scope, guest_display_name: _name, ...member } = payload;
    return { member: true, body: member };
  }
  return { member: false, body: payload };
}

function asDraftError(error: unknown): DraftError {
  if (error instanceof ApiError) return { code: error.code, message: error.message, request_id: error.requestId ?? null };
  return { code: 'UNKNOWN', message: error instanceof Error ? error.message : String(error), request_id: null };
}

/**
 * Sends one draft. Storage problems never block sending: when the draft cannot be written, the
 * in-memory copy is sent and returned (the form keeps it in memory for retries).
 */
export async function sendDraft(
  input: StoredDraft,
  options: { interfaceLanguage: 'bn' | 'en'; turnstileToken?: string | null; now?: () => Date },
): Promise<SendOutcome> {
  const now = options.now ?? (() => new Date());
  // A guest draft from before 9 Nov 2026 has no scope copy: take the device's now and keep it.
  const scope = input.author.kind === 'member' ? null : (input.scope_secret ?? getGuestScopeSecret());
  const { member, body } = draftRequest(input, options.interfaceLanguage, scope ?? '');
  const signature = await requestSignature(body);
  const sameRequest = input.key_signature === null || input.key_signature === signature;
  const key = sameRequest ? input.idempotency_key : crypto.randomUUID();

  const sending: StoredDraft = {
    ...input,
    scope_secret: scope,
    idempotency_key: key,
    key_signature: signature,
    first_sent_signature: input.first_sent_signature ?? signature,
    state: 'SUBMITTING',
    updated_at: input.updated_at,
  };
  // Written before the request, so a crash mid-send is recovered as a retry (guideline 6.4).
  const stored = await updateDraft(input.client_draft_id, (d) => ({
    ...d,
    scope_secret: sending.scope_secret,
    idempotency_key: key,
    key_signature: signature,
    first_sent_signature: sending.first_sent_signature,
    state: 'SUBMITTING',
  }));
  const persisted = stored.ok && stored.value !== null;

  try {
    const created = member
      ? await submitMemberReview(body as MemberReviewCreate, key)
      : await submitGuestReview(
          { ...(body as GuestReviewCreate), ...(options.turnstileToken ? { turnstile_token: options.turnstileToken } : {}) },
          key,
        );
    const acknowledged: Partial<StoredDraft> = {
      state: 'ACKNOWLEDGED',
      review: { review_id: created.review_id, status: created.status, version: created.version, duplicate_recovered: created.duplicate_recovered },
      acknowledged_at: now().toISOString(),
      last_error: null,
      retry_after: null,
    };
    // The receipt stays with the acknowledged draft until the user confirms saving it, or 7 days.
    const after = persisted ? await updateDraft(input.client_draft_id, (d) => ({ ...d, ...acknowledged })) : null;
    const draft = after && after.ok && after.value ? after.value : { ...sending, ...acknowledged };
    const editedAfterFirstSend = created.duplicate_recovered && input.first_sent_signature !== null && input.first_sent_signature !== signature;
    return { kind: 'acknowledged', created, draft, editedAfterFirstSend };
  } catch (error: unknown) {
    const action = classifyFailure(error);
    const retryAfterSeconds = error instanceof ApiError ? error.retryAfterSeconds : undefined;
    const lastError = asDraftError(error);
    const retryAfter = retryAfterSeconds !== undefined ? new Date(now().getTime() + retryAfterSeconds * 1000).toISOString() : null;

    if (action === 'identity-spent') {
      // Keep the text under a new identity; the old one can never be sent again.
      const fresh: StoredDraft = {
        ...sending,
        client_draft_id: crypto.randomUUID(),
        receipt: generateReceipt(),
        idempotency_key: crypto.randomUUID(),
        key_signature: null,
        first_sent_signature: null,
        state: 'NEEDS_ATTENTION',
        last_error: lastError,
        retry_after: null,
        review: null,
        acknowledged_at: null,
      };
      if (persisted) {
        await saveDraft(fresh);
        await deleteDraft(input.client_draft_id);
      }
      return { kind: 'failed', action, error, draft: fresh, retryAfterSeconds };
    }

    const change = (d: StoredDraft): StoredDraft => ({
      ...d,
      state: action === 'retry' ? 'DRAFT' : 'NEEDS_ATTENTION',
      last_error: lastError,
      retry_after: retryAfter,
      ...(action === 'new-key' ? { idempotency_key: crypto.randomUUID(), key_signature: null } : {}),
    });
    const after = persisted ? await updateDraft(input.client_draft_id, change) : null;
    const draft = after && after.ok && after.value ? after.value : change(sending);
    return { kind: 'failed', action, error, draft, retryAfterSeconds };
  }
}
