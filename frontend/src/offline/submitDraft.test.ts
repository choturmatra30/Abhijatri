import 'fake-indexeddb/auto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, NETWORK_ERROR, parseRetryAfter } from '../api/client';
import { DB_NAME, resetDbForTests } from './db';
import {
  buildDraftExport,
  clearUnsentDrafts,
  createDraft,
  deleteMemberDrafts,
  editedDraft,
  getDraft,
  listDrafts,
  maintainDrafts,
  saveDraft,
  type DraftFields,
  type StoredDraft,
} from './draftStore';
import { classifyFailure, draftRequest, sendDraft } from './submitDraft';
import { GUEST_SCOPE_KEY, META_SCOPE_KEY, syncGuestScope } from './guestScope';
import { withDb } from './db';

const SCOPE_A = 'a'.repeat(64);
const SCOPE_B = 'b'.repeat(64);
const RECEIPT = `abr1_${'r'.repeat(43)}`;

const fields = (over: Partial<DraftFields> = {}): DraftFields => ({
  display_name: 'রহিম',
  language: null,
  traveller_type: 'SOLO',
  comfort_tier: 'STANDARD',
  visit_month: '2026-10',
  overall_rating: 4,
  category_ratings: {},
  title: 'পাহাড়ের পথ',
  body: 'পাহাড়ি পথে সাবধানে চলুন, বর্ষায় পিচ্ছিল থাকে।',
  consent: true,
  ...over,
});

const guestDraft = (over: Partial<StoredDraft> = {}): StoredDraft => ({
  ...createDraft({
    clientDraftId: 'draft-1',
    receipt: RECEIPT,
    destinationId: 'dest-1',
    author: { kind: 'guest' },
    fields: fields(),
    consentVersion: '2026-10-01',
    scopeSecret: SCOPE_A,
    now: '2026-11-09T08:00:00Z',
  }),
  ...over,
});

/** localStorage for the node test environment. */
function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (k) => data.get(k) ?? null,
    key: (i) => [...data.keys()][i] ?? null,
    removeItem: (k) => void data.delete(k),
    setItem: (k, v) => void data.set(k, String(v)),
  };
}

const created = (status = 201, duplicate = false) =>
  new Response(JSON.stringify({ review_id: 'rev-1', status: 'PENDING', version: 1, duplicate_recovered: duplicate }), { status });
const failure = (status: number, code: string, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify({ error: { code, message: code, request_id: 'req-1', field_errors: [] } }), { status, headers });

type Sent = { key: string | null; body: Record<string, unknown> };
let sent: Sent[];
function server(...answers: (Response | Error)[]) {
  const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
    sent.push({ key: (init.headers as Record<string, string>)['Idempotency-Key'] ?? null, body: JSON.parse(String(init.body)) });
    const next = answers.shift();
    if (!next) throw new Error('no answer prepared');
    if (next instanceof Error) throw next;
    return next;
  });
  vi.stubGlobal('fetch', fetchMock);
}

beforeEach(() => {
  sent = [];
  vi.stubGlobal('document', { documentElement: { lang: 'en' } });
  vi.stubGlobal('localStorage', memoryStorage());
});

afterEach(async () => {
  vi.unstubAllGlobals();
  await resetDbForTests();
  await new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
});

describe('the answer table (guideline 6.4)', () => {
  const err = (status: number, code: string) => new ApiError(status, code, code);
  it.each([
    [err(0, NETWORK_ERROR), 'retry'],
    [err(0, 'TIMEOUT'), 'retry'],
    [err(409, 'IDEMPOTENCY_REQUEST_IN_PROGRESS'), 'retry'],
    [err(403, 'CHALLENGE_FAILED'), 'retry'],
    [err(401, 'AUTH_REQUIRED'), 'retry'],
    [err(429, 'RATE_LIMITED'), 'retry'],
    [err(503, 'GUEST_WRITES_PAUSED'), 'retry'],
    [err(502, 'HTTP_502'), 'retry'],
    [err(409, 'IDEMPOTENCY_KEY_REUSED'), 'new-key'],
    [err(409, 'DRAFT_ALREADY_SUBMITTED'), 'identity-spent'],
    [err(409, 'MEMBER_REVIEW_EXISTS'), 'attention'],
    [err(409, 'RESERVED_DISPLAY_NAME'), 'attention'],
    [err(422, 'VALIDATION_FAILED'), 'attention'],
    [err(403, 'ACCOUNT_RESTRICTED'), 'attention'],
    [err(404, 'NOT_FOUND'), 'attention'],
    [new TypeError('x'), 'retry'],
  ])('%s → %s', (error, action) => {
    expect(classifyFailure(error)).toBe(action);
  });

  it('reads Retry-After as seconds or as a date', () => {
    expect(parseRetryAfter('120')).toBe(120);
    expect(parseRetryAfter('Mon, 09 Nov 2026 10:00:30 GMT', Date.parse('2026-11-09T10:00:00Z'))).toBe(30);
    expect(parseRetryAfter(null)).toBeUndefined();
    expect(parseRetryAfter('soon')).toBeUndefined();
  });
});

describe('sending a stored draft', () => {
  it('sends the draft identity and its own key, and keeps the receipt until confirmed', async () => {
    const d = guestDraft();
    await saveDraft(d);
    server(created());
    const outcome = await sendDraft(d, { interfaceLanguage: 'en', turnstileToken: 'tok' });
    expect(outcome.kind).toBe('acknowledged');
    expect(sent[0].body).toMatchObject({ client_draft_id: 'draft-1', receipt_secret: RECEIPT, guest_scope_secret: SCOPE_A, turnstile_token: 'tok' });
    expect(sent[0].key).toBe(d.idempotency_key);
    const stored = await getDraft('draft-1');
    expect(stored.ok && [stored.value?.state, stored.value?.receipt, stored.value?.review?.review_id]).toEqual(['ACKNOWLEDGED', RECEIPT, 'rev-1']);
  });

  it('D7: a lost response keeps the draft ready, and the retry reuses the same key', async () => {
    const first = guestDraft();
    await saveDraft(first);
    server(new TypeError('lost'), created(200, true));
    const lost = await sendDraft(first, { interfaceLanguage: 'en' });
    expect(lost.kind === 'failed' && [lost.action, lost.draft.state]).toEqual(['retry', 'DRAFT']);
    const again = (await getDraft('draft-1')) as { ok: true; value: StoredDraft };
    const retry = await sendDraft(again.value, { interfaceLanguage: 'en' });
    expect(sent.map((s) => s.key)).toEqual([first.idempotency_key, first.idempotency_key]);
    expect(retry.kind === 'acknowledged' && [retry.created.duplicate_recovered, retry.editedAfterFirstSend]).toEqual([true, false]);
  });

  it('D11 (trap 2): an edit after a lost response gets a new key and is reported as not applied', async () => {
    const first = guestDraft();
    await saveDraft(first);
    server(new TypeError('lost'), created(200, true));
    await sendDraft(first, { interfaceLanguage: 'en' });
    const stored = ((await getDraft('draft-1')) as { ok: true; value: StoredDraft }).value;
    const edited = editedDraft(stored, { destinationId: 'dest-1', fields: fields({ title: 'নতুন শিরোনাম' }), consentVersion: '2026-10-01', now: '2026-11-09T09:00:00Z' });
    await saveDraft(edited);
    const outcome = await sendDraft(edited, { interfaceLanguage: 'en' });
    expect(sent[1].key).not.toBe(sent[0].key);
    expect(sent[1].body.client_draft_id).toBe('draft-1');
    expect(outcome.kind === 'acknowledged' && outcome.editedAfterFirstSend).toBe(true);
  });

  it('D10: after "Start as a new guest" the draft still goes with the scope it was written under', async () => {
    localStorage.setItem(GUEST_SCOPE_KEY, SCOPE_B);
    const d = guestDraft();
    await saveDraft(d);
    server(created());
    await sendDraft(d, { interfaceLanguage: 'en' });
    expect(sent[0].body.guest_scope_secret).toBe(SCOPE_A);
  });

  it('a draft saved before the scope copy existed takes the device scope once and keeps it', async () => {
    localStorage.setItem(GUEST_SCOPE_KEY, SCOPE_B);
    const old = guestDraft({ scope_secret: null });
    await saveDraft(old);
    server(new TypeError('lost'));
    await sendDraft(old, { interfaceLanguage: 'en' });
    expect(sent[0].body.guest_scope_secret).toBe(SCOPE_B);
    const stored = await getDraft('draft-1');
    expect(stored.ok && stored.value?.scope_secret).toBe(SCOPE_B);
  });

  it('D22: the daily limit keeps the draft ready and remembers when it can be sent', async () => {
    const d = guestDraft();
    await saveDraft(d);
    server(failure(429, 'RATE_LIMITED', { 'Retry-After': '3600' }));
    const outcome = await sendDraft(d, { interfaceLanguage: 'en', now: () => new Date('2026-11-09T10:00:00Z') });
    expect(outcome.kind === 'failed' && [outcome.draft.state, outcome.draft.retry_after, outcome.draft.last_error?.code]).toEqual([
      'DRAFT',
      '2026-11-09T11:00:00.000Z',
      'RATE_LIMITED',
    ]);
  });

  it('D14: a field error needs a change; editing makes the draft ready again', async () => {
    const d = guestDraft();
    await saveDraft(d);
    server(failure(422, 'VALIDATION_FAILED'));
    const outcome = await sendDraft(d, { interfaceLanguage: 'en' });
    expect(outcome.kind === 'failed' && outcome.draft.state).toBe('NEEDS_ATTENTION');
    const fixed = editedDraft(outcome.draft, { destinationId: 'dest-1', fields: fields({ body: 'x'.repeat(30) }), consentVersion: '2026-10-01', now: '2026-11-09T10:00:00Z' });
    expect([fixed.state, fixed.last_error]).toEqual(['DRAFT', null]);
  });

  it('IDEMPOTENCY_KEY_REUSED gives a new key and keeps the identity', async () => {
    const d = guestDraft();
    await saveDraft(d);
    server(failure(409, 'IDEMPOTENCY_KEY_REUSED'));
    const outcome = await sendDraft(d, { interfaceLanguage: 'en' });
    expect(outcome.kind === 'failed' && [outcome.draft.client_draft_id, outcome.draft.idempotency_key !== d.idempotency_key, outcome.draft.key_signature]).toEqual([
      'draft-1',
      true,
      null,
    ]);
  });

  it('DRAFT_ALREADY_SUBMITTED keeps the text under a new identity and removes the spent one', async () => {
    const d = guestDraft();
    await saveDraft(d);
    server(failure(409, 'DRAFT_ALREADY_SUBMITTED'));
    const outcome = await sendDraft(d, { interfaceLanguage: 'en' });
    expect(outcome.kind).toBe('failed');
    if (outcome.kind !== 'failed') return;
    expect(outcome.draft.client_draft_id).not.toBe('draft-1');
    expect(outcome.draft.receipt).not.toBe(RECEIPT);
    expect(outcome.draft.fields.title).toBe('পাহাড়ের পথ');
    expect((await getDraft('draft-1')).ok && (await getDraft('draft-1'))).toEqual({ ok: true, value: null });
  });

  it('a member request carries no guest scope or name', () => {
    const member = guestDraft({ author: { kind: 'member', user_id: 'u1' }, scope_secret: null });
    const { member: isMember, body } = draftRequest(member, 'en', '');
    expect(isMember).toBe(true);
    expect(body).not.toHaveProperty('guest_scope_secret');
    expect(body).not.toHaveProperty('guest_display_name');
  });
});

describe('start-up maintenance (guideline 6.1, 6.5)', () => {
  it('D9: a send interrupted by a crash comes back as ready; receipts older than 7 days are deleted', async () => {
    await saveDraft(guestDraft({ client_draft_id: 'stuck', state: 'SUBMITTING' }));
    await saveDraft(guestDraft({ client_draft_id: 'old', destination_id: 'd2', state: 'ACKNOWLEDGED', acknowledged_at: '2026-11-01T08:00:00Z' }));
    await saveDraft(guestDraft({ client_draft_id: 'recent', destination_id: 'd3', state: 'ACKNOWLEDGED', acknowledged_at: '2026-11-08T08:00:00Z' }));
    const result = await maintainDrafts(new Date('2026-11-09T09:00:00Z'));
    expect(result).toEqual({ ok: true, value: { recovered: 1, purged: 1 } });
    const all = await listDrafts({ kind: 'guest' });
    expect(all.ok && all.value.map((d) => [d.client_draft_id, d.state]).sort()).toEqual([
      ['recent', 'ACKNOWLEDGED'],
      ['stuck', 'DRAFT'],
    ]);
  });
});

describe('delete, clear all, export (guideline 6.6, 6.7)', () => {
  it('Clear all removes this viewer’s unsent drafts only, never kept receipts or others’ drafts', async () => {
    await saveDraft(guestDraft({ client_draft_id: 'g1' }));
    await saveDraft(guestDraft({ client_draft_id: 'g2', destination_id: 'd2' }));
    await saveDraft(guestDraft({ client_draft_id: 'ack', destination_id: 'd3', state: 'ACKNOWLEDGED', acknowledged_at: '2026-11-09T08:00:00Z' }));
    await saveDraft(guestDraft({ client_draft_id: 'm1', author: { kind: 'member', user_id: 'u1' }, scope_secret: null }));
    expect(await clearUnsentDrafts({ kind: 'guest' })).toEqual({ ok: true, value: 2 });
    const left = await withDb((db) => db.getAllKeys('drafts'));
    expect(left.ok && [...left.value].sort()).toEqual(['ack', 'm1']);
  });

  it('D20: sign-out with "delete" removes that member’s unsent drafts only', async () => {
    await saveDraft(guestDraft({ client_draft_id: 'm1', author: { kind: 'member', user_id: 'u1' }, scope_secret: null }));
    await saveDraft(guestDraft({ client_draft_id: 'm2', author: { kind: 'member', user_id: 'u2' }, scope_secret: null }));
    await saveDraft(guestDraft({ client_draft_id: 'p', author: { kind: 'pending' } }));
    expect(await deleteMemberDrafts('u1')).toEqual({ ok: true, value: 1 });
    const left = await withDb((db) => db.getAllKeys('drafts'));
    expect(left.ok && [...left.value].sort()).toEqual(['m2', 'p']);
  });

  it('D17: export has receipts only when confirmed, never acknowledged ones, never the scope or key', () => {
    const drafts = [guestDraft(), guestDraft({ client_draft_id: 'ack', state: 'ACKNOWLEDGED' })];
    const plain = buildDraftExport(drafts, { includeReceipts: false, destinationName: () => 'বান্দরবান', now: new Date('2026-11-09T00:00:00Z') });
    expect(plain.drafts).toHaveLength(1);
    expect(plain.drafts[0]).not.toHaveProperty('receipt');
    const text = JSON.stringify(plain);
    expect(text).not.toContain(SCOPE_A);
    expect(text).not.toContain(guestDraft().idempotency_key);
    const withReceipts = buildDraftExport(drafts, { includeReceipts: true, destinationName: () => null });
    expect(withReceipts.drafts.map((d) => d.receipt)).toEqual([RECEIPT]);
    expect(withReceipts.includes_receipts).toBe(true);
  });
});

describe('guest scope write-through (Decisions 2026-11-08)', () => {
  it('copies the existing value to IndexedDB without changing it', async () => {
    localStorage.setItem(GUEST_SCOPE_KEY, SCOPE_A);
    expect(await syncGuestScope()).toBe('copied');
    const stored = await withDb((db) => db.get('meta', META_SCOPE_KEY));
    expect(stored).toEqual({ ok: true, value: SCOPE_A });
    expect(localStorage.getItem(GUEST_SCOPE_KEY)).toBe(SCOPE_A);
  });

  it('restores a lost localStorage value from IndexedDB, so the guest tag stays the same', async () => {
    await withDb((db) => db.put('meta', SCOPE_A, META_SCOPE_KEY));
    expect(await syncGuestScope()).toBe('restored');
    expect(localStorage.getItem(GUEST_SCOPE_KEY)).toBe(SCOPE_A);
  });

  it('makes nothing up when both are empty', async () => {
    expect(await syncGuestScope()).toBe('none');
    expect(localStorage.getItem(GUEST_SCOPE_KEY)).toBeNull();
  });
});
