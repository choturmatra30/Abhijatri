import 'fake-indexeddb/auto';
import { afterEach, describe, expect, it } from 'vitest';
import { DB_NAME, resetDbForTests } from './db';
import {
  authorFor,
  canSee,
  claimPendingDrafts,
  createDraft,
  deleteDraft,
  findDraft,
  hasContent,
  saveDraft,
  type DraftAuthor,
  type DraftFields,
  type StoredDraft,
} from './draftStore';
import { storeParameters, storedParameters } from './parameters';

const fields = (over: Partial<DraftFields> = {}): DraftFields => ({
  display_name: 'রহিম',
  language: null,
  traveller_type: 'SOLO',
  comfort_tier: 'STANDARD',
  visit_month: '2026-10',
  overall_rating: 0,
  category_ratings: {},
  title: '',
  body: '',
  consent: false,
  ...over,
});

const draft = (id: string, destination: string, author: DraftAuthor, updated = '2026-11-07T10:00:00Z', f = fields({ title: 'শিরোনাম' })): StoredDraft =>
  createDraft({
    clientDraftId: id,
    receipt: `abr1_${id}`,
    destinationId: destination,
    author,
    fields: f,
    consentVersion: '2026-10-01',
    scopeSecret: author.kind === 'member' ? null : 's'.repeat(64),
    now: updated,
  });

afterEach(async () => {
  await resetDbForTests();
  await new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
});

describe('who sees which draft (owner decision 7 Nov 2026)', () => {
  const guest = draft('g', 'd', { kind: 'guest' });
  const mine = draft('m', 'd', { kind: 'member', user_id: 'u1' });
  const pending = draft('p', 'd', { kind: 'pending' });
  it('a guest sees only guest drafts', () => {
    expect([guest, mine, pending].filter((x) => canSee(x, { kind: 'guest' })).map((x) => x.client_draft_id)).toEqual(['g']);
  });
  it('a member sees only their own drafts and pending ones', () => {
    expect([guest, mine, pending].filter((x) => canSee(x, { kind: 'member', userId: 'u1' })).map((x) => x.client_draft_id)).toEqual(['m', 'p']);
    expect(canSee(mine, { kind: 'member', userId: 'u2' })).toBe(false);
  });
  it('with the sign-in unknown (offline), member drafts stay hidden', () => {
    expect([guest, mine, pending].filter((x) => canSee(x, { kind: 'unknown' })).map((x) => x.client_draft_id)).toEqual(['g', 'p']);
  });
  it('a new draft written with the sign-in unknown is pending', () => {
    expect(authorFor({ kind: 'unknown' })).toEqual({ kind: 'pending' });
    expect(authorFor({ kind: 'member', userId: 'u1' })).toEqual({ kind: 'member', user_id: 'u1' });
    expect(authorFor({ kind: 'guest' })).toEqual({ kind: 'guest' });
  });
});

describe('draft store', () => {
  it('finds the newest visible draft for a destination', async () => {
    await saveDraft(draft('old', 'd1', { kind: 'guest' }, '2026-11-07T09:00:00Z'));
    await saveDraft(draft('new', 'd1', { kind: 'guest' }, '2026-11-07T11:00:00Z'));
    await saveDraft(draft('other', 'd2', { kind: 'guest' }));
    await saveDraft(draft('member', 'd1', { kind: 'member', user_id: 'u1' }, '2026-11-07T12:00:00Z'));
    const found = await findDraft('d1', { kind: 'guest' });
    expect(found.ok && found.value?.client_draft_id).toBe('new');
    expect((await findDraft('d3', { kind: 'guest' })).ok && (await findDraft('d3', { kind: 'guest' }))).toEqual({ ok: true, value: null });
  });

  it('keeps Bangla text, receipt and revision exactly', async () => {
    await saveDraft({ ...draft('x', 'd', { kind: 'guest' }, undefined, fields({ body: 'পাহাড়ি পথে সাবধানে চলুন।', overall_rating: 4 })), local_revision: 7 });
    const found = await findDraft('d', { kind: 'guest' });
    expect(found.ok && [found.value?.fields.body, found.value?.receipt, found.value?.local_revision]).toEqual(['পাহাড়ি পথে সাবধানে চলুন।', 'abr1_x', 7]);
  });

  it('back online with nobody signed in, pending drafts go to the guest', async () => {
    await saveDraft(draft('p', 'd', { kind: 'pending' }));
    expect(await claimPendingDrafts({ kind: 'guest' })).toEqual({ ok: true, value: 1 });
    const found = await findDraft('d', { kind: 'guest' });
    expect(found.ok && found.value?.author).toEqual({ kind: 'guest' });
  });

  it('a member confirmed online takes over pending drafts', async () => {
    await saveDraft(draft('p', 'd', { kind: 'pending' }));
    await saveDraft(draft('g', 'd2', { kind: 'guest' }));
    expect(await claimPendingDrafts({ kind: 'member', user_id: 'u1' })).toEqual({ ok: true, value: 1 });
    expect((await findDraft('d', { kind: 'guest' })).ok && (await findDraft('d', { kind: 'guest' }))).toEqual({ ok: true, value: null });
    const theirs = await findDraft('d', { kind: 'member', userId: 'u1' });
    expect(theirs.ok && theirs.value?.author).toEqual({ kind: 'member', user_id: 'u1' });
  });

  it('deletes one draft only', async () => {
    await saveDraft(draft('a', 'd1', { kind: 'guest' }));
    await saveDraft(draft('b', 'd2', { kind: 'guest' }));
    await deleteDraft('a');
    expect((await findDraft('d1', { kind: 'guest' })).ok && (await findDraft('d1', { kind: 'guest' }))).toEqual({ ok: true, value: null });
    expect((await findDraft('d2', { kind: 'guest' })).ok).toBe(true);
  });

  it('keeps only drafts with something written or chosen', () => {
    expect(hasContent(fields())).toBe(false);
    expect(hasContent(fields({ display_name: 'x' }))).toBe(false); // a pre-filled name alone is not a draft
    expect(hasContent(fields({ overall_rating: 3 }))).toBe(true);
    expect(hasContent(fields({ body: 'x' }))).toBe(true);
  });
});

describe('stored review parameters', () => {
  it('round-trips the last answer for offline use', async () => {
    expect(await storedParameters()).toBeNull();
    await storeParameters({ note: { min_length: 20, max_length: 6000 } } as never);
    expect((await storedParameters())?.note.min_length).toBe(20);
  });
});
