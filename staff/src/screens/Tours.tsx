import { useCallback, useEffect, useState } from 'react';
import {
  StaffError, cancelStaffTour, getStaffTour, getTourPrivateView, grantTourBreakglass,
  removeStaffTourMember, restoreStaffTour, restrictTourUser, searchStaffTours, suspendStaffTour,
} from '../api';
import type { Lang, Role, StaffTourCard, StaffTourDetail } from '../types';
import { Notice, makeT } from '../ui';

const errorText = (error: unknown) => error instanceof StaffError ? error.code : error instanceof Error ? error.message : 'UNKNOWN_ERROR';

/** One staff action waiting for its reason (and note, days or break-glass justification) in the inline panel. */
type Pending =
  | { kind: 'suspend' | 'restore' | 'cancel' }
  | { kind: 'remove'; memberId: string; name: string }
  | { kind: 'restrict'; userId: string; name: string }
  | { kind: 'breakglass'; scope: 'chat' | 'safety' | 'expenses' };

const REASONS: Record<Pending['kind'], string[]> = {
  suspend: ['safety', 'fraud', 'harassment', 'policy_violation', 'legal'],
  restore: ['resolved', 'reported_in_error', 'appeal_upheld'],
  cancel: ['safety', 'fraud', 'legal', 'organiser_unreachable'],
  remove: ['safety', 'harassment', 'fraud', 'policy_violation'],
  restrict: ['tourmate-safety', 'harassment', 'fraud', 'spam'],
  breakglass: [],
};

export function Tours({ lang, role }: { lang: Lang; role: Role }) {
  const t = makeT(lang);
  const [items, setItems] = useState<StaffTourCard[]>([]);
  const [selected, setSelected] = useState<StaffTourDetail | null>(null);
  const [q, setQ] = useState('');
  const [lifecycle, setLifecycle] = useState('');
  const [flag, setFlag] = useState('');
  const [message, setMessage] = useState<{ tone: 'error' | 'success' | 'info'; text: string } | null>(null);
  const [privateView, setPrivateView] = useState<{ scope: string; items: unknown } | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [code, setCode] = useState('');
  const [note, setNote] = useState('');
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState(false);

  const search = useCallback(async () => {
    try { setItems((await searchStaffTours({ q, lifecycle, flag })).items); }
    catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
  }, [q, lifecycle, flag]);
  const open = useCallback(async (id: string) => {
    try { setSelected(await getStaffTour(id)); setPrivateView(null); setPending(null); }
    catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
  }, []);
  useEffect(() => { void search(); }, []); // initial list; filters are applied by the Search button

  const ask = (next: Pending) => { setPending(next); setCode(REASONS[next.kind][0] ?? ''); setNote(''); setDays(7); setMessage(null); };

  const confirm = async () => {
    if (!selected || !pending) return;
    const id = selected.public_id;
    setBusy(true); setMessage(null);
    try {
      if (pending.kind === 'breakglass') {
        const grant = await grantTourBreakglass(id, note.trim(), [pending.scope]);
        setPrivateView(await getTourPrivateView(id, pending.scope));
        setMessage({ tone: 'info', text: `${t('ব্যক্তিগত অ্যাক্সেস শেষ হবে', 'Private access expires')} ${new Date(grant.expires_at).toLocaleTimeString()}` });
        setPending(null);
        return;
      }
      let done = '';
      if (pending.kind === 'suspend') { await suspendStaffTour(id, code, note.trim() || undefined); done = t('ট্যুর স্থগিত হয়েছে।', 'Tour suspended.'); }
      if (pending.kind === 'restore') { await restoreStaffTour(id, code); done = t('ট্যুর পুনরুদ্ধার হয়েছে।', 'Tour restored.'); }
      if (pending.kind === 'cancel') {
        await cancelStaffTour(id, code, note.trim() || undefined);
        done = role === 'superadmin' && selected.lifecycle === 'CONFIRMED' ? t('অনুরোধ/অনুমোদন রেকর্ড হয়েছে।', 'Request/approval recorded.') : t('ট্যুর বাতিল হয়েছে।', 'Tour cancelled.');
      }
      if (pending.kind === 'remove') { await removeStaffTourMember(id, pending.memberId, code); done = t('সদস্য সরানো হয়েছে।', 'Member removed.'); }
      if (pending.kind === 'restrict') { await restrictTourUser(pending.userId, code, days); done = t('ট্যুরমেট সীমাবদ্ধতা প্রয়োগ হয়েছে।', 'TourMate restriction applied.'); }
      setPending(null);
      await open(id); await search();
      setMessage({ tone: 'success', text: done });
    } catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
    finally { setBusy(false); }
  };

  const title = (p: Pending): string => {
    switch (p.kind) {
      case 'suspend': return t('ট্যুর স্থগিত করুন', 'Suspend this tour');
      case 'restore': return t('ট্যুর পুনরুদ্ধার করুন', 'Restore this tour');
      case 'cancel': return t('ট্যুর বাতিল করুন (সদস্যদের জানানো হবে)', 'Cancel this tour (members are told)');
      case 'remove': return `${t('সদস্য সরান', 'Remove member')}: ${p.name}`;
      case 'restrict': return `${t('ট্যুর থেকে সীমিত করুন', 'Restrict from Tours')}: ${p.name}`;
      case 'breakglass': return `${t('ব্রেক-গ্লাস', 'Break-glass')}: ${p.scope}`;
    }
  };
  const ready = pending?.kind === 'breakglass' ? note.trim().length >= 10 : Boolean(code) && (pending?.kind !== 'cancel' || note.trim().length >= 3);

  return <main className="stack">
    <section className="card stack">
      <div><h2>{t('ট্যুর অপারেশনস', 'Tour Operations')}</h2><p className="muted small">{t('অনুসন্ধান, নিরাপত্তা ব্যবস্থা এবং অডিটেড ব্রেক-গ্লাস অ্যাক্সেস।', 'Search, safety actions and audited break-glass access.')}</p></div>
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); void search(); }}>
        <input value={q} onChange={(event) => setQ(event.target.value)} placeholder={t('আইডি, কোড, শিরোনাম বা আয়োজক', 'ID, code, title or organiser')} />
        <select value={lifecycle} onChange={(event) => setLifecycle(event.target.value)}><option value="">{t('সব অবস্থা', 'All states')}</option>{['DRAFT', 'RECRUITING', 'CONFIRMED', 'ONGOING', 'COMPLETED', 'CANCELLED', 'ARCHIVED'].map((value) => <option key={value}>{value}</option>)}</select>
        <select value={flag} onChange={(event) => setFlag(event.target.value)}><option value="">{t('সব ফ্ল্যাগ', 'All flags')}</option><option value="SUSPENDED">SUSPENDED</option><option value="AT_RISK">AT RISK</option></select>
        <button type="submit">{t('খুঁজুন', 'Search')}</button>
      </form>
      <div className="table-wrap"><table><thead><tr><th>ID</th><th>{t('ট্যুর', 'Tour')}</th><th>{t('অবস্থা', 'State')}</th><th>{t('তারিখ', 'Dates')}</th><th>{t('সদস্য', 'Members')}</th><th /></tr></thead><tbody>{items.map((tour) => { const count = Array.isArray(tour.members) ? tour.members.length : `${tour.members.approved}/${tour.members.maximum}`; return <tr key={tour.public_id}><td><code>{tour.public_id}</code></td><td><strong>{tour.title}</strong><div className="muted small">{tour.policy} · {tour.destinations.map((d) => d.name_en).join(', ')}</div></td><td>{tour.lifecycle}{tour.suspended ? ' · SUSPENDED' : ''}{tour.is_at_risk ? ' · AT RISK' : ''}</td><td>{tour.start_date}<br />{tour.end_date}</td><td>{count}</td><td><button type="button" onClick={() => void open(tour.public_id)}>{t('খুলুন', 'Open')}</button></td></tr>; })}</tbody></table></div>
    </section>

    {selected && <section className="card stack">
      <div className="split"><div><p className="muted small"><code>{selected.public_id}</code> · {selected.lifecycle}{selected.suspended ? ' · SUSPENDED' : ''}</p><h2>{selected.title}</h2></div><button type="button" className="ghost" onClick={() => setSelected(null)}>×</button></div>
      <div className="row wrap">
        {!selected.suspended
          ? <button type="button" className="danger" onClick={() => ask({ kind: 'suspend' })}>{t('স্থগিত করুন', 'Suspend')}</button>
          : <button type="button" onClick={() => ask({ kind: 'restore' })}>{t('পুনরুদ্ধার', 'Restore')}</button>}
        <button type="button" className="danger" onClick={() => ask({ kind: 'cancel' })}>{t('স্টাফ বাতিল', 'Staff cancel')}</button>
        <button type="button" onClick={() => ask({ kind: 'breakglass', scope: 'chat' })}>{t('চ্যাট দেখুন (ব্রেক-গ্লাস)', 'View chat (break-glass)')}</button>
        <button type="button" onClick={() => ask({ kind: 'breakglass', scope: 'safety' })}>{t('সেফটি দেখুন (ব্রেক-গ্লাস)', 'View safety (break-glass)')}</button>
        <button type="button" onClick={() => ask({ kind: 'breakglass', scope: 'expenses' })}>{t('খরচ দেখুন (ব্রেক-গ্লাস)', 'View expenses (break-glass)')}</button>
      </div>

      {pending && <fieldset className="stack decision">
        <legend>{title(pending)}</legend>
        {pending.kind === 'breakglass'
          ? <>
            <label htmlFor="ops-note">{t('জরুরি কারণ (কমপক্ষে ১০ অক্ষর; অডিট হবে, আয়োজককে জানানো হবে)', 'Urgent reason (at least 10 characters; audited, and the organisers are told)')}</label>
            <textarea id="ops-note" rows={2} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
          </>
          : <>
            <label htmlFor="ops-code">{t('কারণ', 'Reason')}</label>
            <select id="ops-code" value={code} onChange={(event) => setCode(event.target.value)}>{REASONS[pending.kind].map((value) => <option key={value} value={value}>{value}</option>)}</select>
            {pending.kind === 'restrict' && <><label htmlFor="ops-days">{t('কত দিন', 'Days')}</label><input id="ops-days" type="number" min={1} max={role === 'superadmin' ? 365 : 30} value={days} onChange={(event) => setDays(Math.max(1, Number(event.target.value) || 1))} /></>}
            {(pending.kind === 'suspend' || pending.kind === 'cancel') && <><label htmlFor="ops-note">{pending.kind === 'cancel' ? t('অভ্যন্তরীণ নোট (আবশ্যক)', 'Internal note (required)') : t('অভ্যন্তরীণ নোট (ঐচ্ছিক)', 'Internal note (optional)')}</label><textarea id="ops-note" rows={2} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></>}
          </>}
        <div className="row">
          <button type="button" className={pending.kind === 'restore' || pending.kind === 'breakglass' ? 'primary' : 'danger'} disabled={busy || !ready} onClick={() => void confirm()}>{t('নিশ্চিত করুন', 'Confirm')}</button>
          <button type="button" className="ghost" disabled={busy} onClick={() => setPending(null)}>{t('বাতিল', 'Back')}</button>
        </div>
      </fieldset>}

      <h3>{t('সদস্য', 'Members')}</h3><div className="table-wrap"><table><thead><tr><th>{t('নাম', 'Name')}</th><th>{t('ভূমিকা', 'Role')}</th><th>{t('অবস্থা', 'State')}</th><th>{t('আসন', 'Seats')}</th><th /></tr></thead><tbody>{selected.members.map((member) => <tr key={member.member_id}><td>{member.name}</td><td>{member.role}</td><td>{member.state}</td><td>{member.seats}</td><td><div className="row wrap">{member.role !== 'CREATOR' && member.state === 'ACTIVE' && <button type="button" className="danger" onClick={() => ask({ kind: 'remove', memberId: member.member_id, name: member.name })}>{t('সরান', 'Remove')}</button>}<button type="button" className="danger" onClick={() => ask({ kind: 'restrict', userId: member.user_id, name: member.name })}>{t('সীমাবদ্ধ', 'Restrict')}</button></div></td></tr>)}</tbody></table></div>
      <h3>{t('রিপোর্ট', 'Reports')}</h3>{selected.reports.length ? <ul>{selected.reports.map((report) => <li key={report.id}><code>{report.id.slice(0, 8)}</code> · {report.subject_kind} · {report.reason_code} · {report.state}</li>)}</ul> : <p className="muted">{t('কোনো রিপোর্ট নেই।', 'No reports.')}</p>}
      <h3>{t('মূল পরিবর্তন', 'Key changes')}</h3>{selected.changes.length ? <ul>{selected.changes.map((change, index) => <li key={`${change.at}-${index}`}>{new Date(change.at).toLocaleString()} · {change.kind}{change.key_change ? ' · KEY' : ''}</li>)}</ul> : <p className="muted">{t('কোনো পরিবর্তন নেই।', 'No changes.')}</p>}
      {privateView && <div className="card inset"><div className="split"><strong>{privateView.scope.toUpperCase()} · PRIVATE</strong><button className="ghost" onClick={() => setPrivateView(null)}>Close</button></div><pre className="private-json">{JSON.stringify(privateView.items, null, 2)}</pre></div>}
    </section>}
  </main>;
}
