import { useCallback, useEffect, useState } from 'react';
import {
  StaffError, cancelStaffTour, getStaffTour, getTourPrivateView, grantTourBreakglass,
  removeStaffTourMember, restoreStaffTour, restrictTourUser, searchStaffTours, suspendStaffTour,
} from '../api';
import type { Lang, Role, StaffTourCard, StaffTourDetail } from '../types';
import { Notice, makeT } from '../ui';

const errorText = (error: unknown) => error instanceof StaffError ? error.code : error instanceof Error ? error.message : 'UNKNOWN_ERROR';

export function Tours({ lang, role }: { lang: Lang; role: Role }) {
  const t = makeT(lang);
  const [items, setItems] = useState<StaffTourCard[]>([]);
  const [selected, setSelected] = useState<StaffTourDetail | null>(null);
  const [q, setQ] = useState('');
  const [lifecycle, setLifecycle] = useState('');
  const [flag, setFlag] = useState('');
  const [message, setMessage] = useState<{ tone: 'error' | 'success' | 'info'; text: string } | null>(null);
  const [privateView, setPrivateView] = useState<{ scope: string; items: unknown } | null>(null);

  const search = useCallback(async () => {
    try { setItems((await searchStaffTours({ q, lifecycle, flag })).items); }
    catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
  }, [q, lifecycle, flag]);
  const open = useCallback(async (id: string) => {
    try { setSelected(await getStaffTour(id)); setPrivateView(null); }
    catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
  }, []);
  useEffect(() => { void search(); }, []); // initial list; filters are applied by the Search button

  const act = async (work: () => Promise<unknown>, done: string) => {
    if (!selected) return;
    setMessage(null);
    try { await work(); setMessage({ tone: 'success', text: done }); await open(selected.public_id); await search(); }
    catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
  };
  const reason = (fallback: string) => prompt(t('কারণ কোড লিখুন', 'Reason code'), fallback)?.trim() || null;

  const breakglass = async (scope: 'chat' | 'safety' | 'expenses') => {
    if (!selected) return;
    const why = prompt(t('কমপক্ষে ১০ অক্ষরে জরুরি কারণ লিখুন। এটি অডিট হবে।', 'Enter an urgent reason (at least 10 characters). This is audited.'))?.trim();
    if (!why || why.length < 10) return;
    try {
      const grant = await grantTourBreakglass(selected.public_id, why, [scope]);
      setPrivateView(await getTourPrivateView(selected.public_id, scope));
      setMessage({ tone: 'info', text: `${t('ব্যক্তিগত অ্যাক্সেস শেষ হবে', 'Private access expires')} ${new Date(grant.expires_at).toLocaleTimeString()}` });
    } catch (error) { setMessage({ tone: 'error', text: errorText(error) }); }
  };

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
      <div className="split"><div><p className="muted small"><code>{selected.public_id}</code> · {selected.lifecycle}</p><h2>{selected.title}</h2></div><button type="button" className="ghost" onClick={() => setSelected(null)}>×</button></div>
      <div className="row wrap">
        {!selected.suspended ? <button type="button" className="danger" onClick={() => { const code = reason('safety'); if (code) void act(() => suspendStaffTour(selected.public_id, code, prompt('Internal note') || undefined), t('ট্যুর স্থগিত হয়েছে।', 'Tour suspended.')); }}>{t('স্থগিত করুন', 'Suspend')}</button> : <button type="button" onClick={() => { const code = reason('resolved'); if (code) void act(() => restoreStaffTour(selected.public_id, code), t('ট্যুর পুনরুদ্ধার হয়েছে।', 'Tour restored.')); }}>{t('পুনরুদ্ধার', 'Restore')}</button>}
        <button type="button" className="danger" onClick={() => { const code = reason('safety'); if (code && confirm(t('ট্যুর বাতিল করবেন?', 'Cancel this tour?'))) void act(() => cancelStaffTour(selected.public_id, code, prompt('Internal note') || undefined), role === 'superadmin' && selected.lifecycle === 'CONFIRMED' ? t('অনুরোধ/অনুমোদন রেকর্ড হয়েছে।', 'Request/approval recorded.') : t('ট্যুর বাতিল হয়েছে।', 'Tour cancelled.')); }}>{t('স্টাফ বাতিল', 'Staff cancel')}</button>
        <button type="button" onClick={() => void breakglass('chat')}>{t('চ্যাট দেখুন (ব্রেক-গ্লাস)', 'View chat (break-glass)')}</button><button type="button" onClick={() => void breakglass('safety')}>{t('সেফটি দেখুন (ব্রেক-গ্লাস)', 'View safety (break-glass)')}</button><button type="button" onClick={() => void breakglass('expenses')}>{t('খরচ দেখুন (ব্রেক-গ্লাস)', 'View expenses (break-glass)')}</button>
      </div>
      <h3>{t('সদস্য', 'Members')}</h3><div className="table-wrap"><table><thead><tr><th>{t('নাম', 'Name')}</th><th>{t('ভূমিকা', 'Role')}</th><th>{t('অবস্থা', 'State')}</th><th>{t('আসন', 'Seats')}</th><th /></tr></thead><tbody>{selected.members.map((member) => <tr key={member.member_id}><td>{member.name}</td><td>{member.role}</td><td>{member.state}</td><td>{member.seats}</td><td><div className="row wrap">{member.role !== 'CREATOR' && member.state === 'ACTIVE' && <button type="button" className="danger" onClick={() => { const code = reason('safety'); if (code) void act(() => removeStaffTourMember(selected.public_id, member.member_id, code), t('সদস্য সরানো হয়েছে।', 'Member removed.')); }}>{t('সরান', 'Remove')}</button>}<button type="button" className="danger" onClick={() => { const code = reason('tourmate-safety'); const days = Number(prompt(t('কত দিনের জন্য?', 'Restrict for how many days?'), '7')); if (code && Number.isInteger(days) && days > 0) void act(() => restrictTourUser(member.user_id, code, days), t('ট্যুরমেট সীমাবদ্ধতা প্রয়োগ হয়েছে।', 'TourMate restriction applied.')); }}>{t('সীমাবদ্ধ', 'Restrict')}</button></div></td></tr>)}</tbody></table></div>
      <h3>{t('রিপোর্ট', 'Reports')}</h3>{selected.reports.length ? <ul>{selected.reports.map((report) => <li key={report.id}><code>{report.id}</code> · {report.subject_kind} · {report.reason_code} · {report.state}</li>)}</ul> : <p className="muted">{t('কোনো রিপোর্ট নেই।', 'No reports.')}</p>}
      <h3>{t('মূল পরিবর্তন', 'Key changes')}</h3>{selected.changes.length ? <ul>{selected.changes.map((change, index) => <li key={`${change.at}-${index}`}>{new Date(change.at).toLocaleString()} · {change.kind}{change.key_change ? ' · KEY' : ''}</li>)}</ul> : <p className="muted">{t('কোনো পরিবর্তন নেই।', 'No changes.')}</p>}
      {privateView && <div className="card inset"><div className="split"><strong>{privateView.scope.toUpperCase()} · PRIVATE</strong><button className="ghost" onClick={() => setPrivateView(null)}>Close</button></div><pre className="private-json">{JSON.stringify(privateView.items, null, 2)}</pre></div>}
    </section>}
  </main>;
}
