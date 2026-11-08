import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, BadgeCheck, CalendarDays, MapPin, MessageCircle, Plus, Search, Shield, Users } from 'lucide-react';
import { listAllDestinations } from '../api/destinations';
import {
  acceptInvitation, addExpense, answerCheckin, approveJoinRequest, cancelTour, createTour, declineInvitation,
  declineJoinRequest, findPeople, findTours, getBudget, getItinerary, getMessages, getSafety, getTourAccess,
  getTourByCode, getTourDashboard, getTourSummary, getTourWorkspace, getTravelPreferences, invitePerson,
  leaveTour, markMessagesRead, publishTour, raiseSos, regenerateTourCode, removeTourMember,
  reportTour, requestCheckin, requestToJoin, saveDiscovery, saveSafety, saveTravelPreferences, setMemberRole,
  settleExpense,
  type BudgetView, type ChatView, type ItineraryView, type SafetyView, type TourAccess, type TourCard,
  type TourDashboard, type TourWorkspace,
} from '../api/tours';
import { Notice, accountErrorMessage, primaryButtonClass } from '../components/auth/AccountUi';
import { LoadingState } from '../components/common/StatusViews';
import { useLanguage } from '../context/LanguageContext';
import { cacheChat, cachedChat, flushChatOutbox, pendingChat, queueChat } from '../offline/tourChat';
import type { DestinationSummary } from '../types';

const field = 'w-full rounded-xl border border-surface-muted/40 bg-white/70 dark:bg-dark-surface-2 px-3 py-2.5 text-sm';
const panel = 'tonal-card p-5 flex flex-col gap-3';

function useAccess() {
  const [access, setAccess] = useState<TourAccess | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { void getTourAccess().then(setAccess).catch((reason) => setError(reason instanceof Error ? reason.message : 'Tours could not be loaded.')); }, []);
  return { access, error };
}

function AccessBoundary({ children }: { children: React.ReactNode }) {
  const { t } = useLanguage();
  const { access, error } = useAccess();
  if (!access && !error) return <LoadingState />;
  if (error) return <div className="max-w-xl mx-auto p-8"><Notice tone="error">{error}</Notice></div>;
  if (!access?.access) return <main className="max-w-xl mx-auto p-6 py-10 flex flex-col gap-4"><Shield size={34} /><h1 className="text-2xl font-bold">{t('Tours শুধু যাচাইকৃত প্রাপ্তবয়স্ক সদস্যদের জন্য', 'Tours is for verified adult members')}</h1><p>{access?.reason === 'NOT_VERIFIED' ? t('পরিচয় যাচাই সম্পন্ন করলে ট্যুর তৈরি ও সঙ্গী খুঁজতে পারবেন।', 'Complete identity verification to create tours and find travel companions.') : t('এই অ্যাকাউন্টে Tours এখন উপলভ্য নয়।', 'Tours is not available for this account.')}</p><Link to="/verify" className={`${primaryButtonClass} px-5 self-start`}>{t('যাচাই শুরু করুন', 'Start verification')}</Link></main>;
  return <>{children}</>;
}

function TourCardView({ tour, action }: { tour: TourCard; action?: React.ReactNode }) {
  const { t } = useLanguage();
  return <article className={panel}>
    <div className="flex justify-between gap-3"><div><p className="text-xs font-bold text-forest-primary">{tour.public_id} · {tour.lifecycle}</p><h3 className="text-lg font-bold">{tour.title}</h3></div>{tour.match?.score != null && <span className="rounded-full bg-forest-primary text-white px-3 py-1 h-fit text-sm font-bold">{tour.match.score}%</span>}</div>
    <p className="text-sm flex gap-2"><MapPin size={16} />{tour.destinations.map((item) => t(item.name_bn, item.name_en)).join(' · ')}</p>
    <p className="text-sm flex gap-2"><CalendarDays size={16} />{tour.start_date} → {tour.end_date}</p>
    <p className="text-sm flex gap-2"><Users size={16} />{tour.members.approved}/{tour.members.maximum} · minimum {tour.members.minimum} · {tour.policy}</p>
    {tour.is_at_risk && <Notice tone="info">This tour is at risk of cancellation unless it reaches its minimum.</Notice>}
    <div className="flex flex-wrap gap-2"><Link className={`${primaryButtonClass} px-4`} to={`/tours/${tour.public_id}`}>{t('খুলুন', 'Open')}</Link>{action}</div>
  </article>;
}

export const ToursPage: React.FC = () => <AccessBoundary><ToursDashboard /></AccessBoundary>;

function ToursDashboard() {
  const { t } = useLanguage();
  const [data, setData] = useState<TourDashboard | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => getTourDashboard().then(setData).catch((reason) => setError(accountErrorMessage(reason, t))), [t]);
  useEffect(() => { void load(); }, [load]);
  if (!data && !error) return <LoadingState />;
  return <main className="max-w-6xl mx-auto p-4 sm:p-6 py-8 flex flex-col gap-7">
    <div className="flex flex-wrap justify-between gap-3"><div><h1 className="text-3xl font-bold">{t('Tours ও TourMates', 'Tours & TourMates')}</h1><p>{t('পরিকল্পনা করুন, যাচাইকৃত সঙ্গী খুঁজুন, নিরাপদে সমন্বয় করুন।', 'Plan together, find verified companions, and coordinate safely.')}</p></div><div className="flex gap-2"><Link to="/tours/find" className={`${primaryButtonClass} px-4`}><Search size={16} />Find tours</Link><Link to="/tours/new" className={`${primaryButtonClass} px-4`}><Plus size={16} />Create</Link></div></div>
    {error && <Notice tone="error">{error}</Notice>}
    {data?.alerts.map((item) => <Notice key={`${item.kind}-${item.public_id}`} tone="info"><AlertTriangle size={15} className="inline" /> {item.title}: {item.kind.replace(/_/g, ' ')} {item.count ? `(${item.count})` : ''}</Notice>)}
    <section><h2 className="text-xl font-bold mb-3">{t('আমার ট্যুর', 'My tours')}</h2><div className="grid md:grid-cols-2 gap-4">{data?.my_tours.map((tour) => <TourCardView key={tour.public_id} tour={tour} />)}{!data?.my_tours.length && <p className="text-sm">No active tours yet.</p>}</div></section>
    <section><h2 className="text-xl font-bold mb-3">{t('খসড়া', 'Drafts')}</h2><div className="grid md:grid-cols-2 gap-4">{data?.drafts.map((tour) => <TourCardView key={tour.public_id} tour={tour} />)}</div></section>
    {!!data?.requests.to_review.length && <section><h2 className="text-xl font-bold mb-3">Join requests</h2><div className="grid md:grid-cols-2 gap-3">{data.requests.to_review.map((request) => <div className={panel} key={request.id}><strong>{request.first_name} → {request.title}</strong><p>{request.message || request.answer || 'No message'}</p><div className="flex gap-2"><button className={`${primaryButtonClass} px-4`} disabled={!request.can_be_approved} onClick={() => void approveJoinRequest(request.public_id!, request.id).then(load)}>Approve</button><button className="text-error-alert" onClick={() => void declineJoinRequest(request.public_id!, request.id).then(load)}>Decline</button></div></div>)}</div></section>}
    {!!data?.invitations.length && <section><h2 className="text-xl font-bold mb-3">Invitations</h2>{data.invitations.map((invitation) => <div className={`${panel} mb-3`} key={invitation.id}><strong>{invitation.from} invited you to {invitation.tour.title}</strong><div className="flex gap-3"><button className={`${primaryButtonClass} px-4`} onClick={() => void acceptInvitation(invitation.id).then(load)}>Accept</button><button onClick={() => void declineInvitation(invitation.id).then(load)}>Decline</button></div></div>)}</section>}
    <section><div className="flex justify-between"><h2 className="text-xl font-bold">Suggested</h2><Link to="/tours/preferences" className="font-bold text-forest-primary">Preferences {data?.preferences_completion}%</Link></div><div className="grid md:grid-cols-3 gap-4 mt-3">{data?.suggested.map((tour) => <TourCardView key={tour.public_id} tour={tour} />)}</div></section>
  </main>;
}

export const FindToursPage: React.FC = () => <AccessBoundary><TourFinder /></AccessBoundary>;
function TourFinder() {
  const [filters, setFilters] = useState({ date_from: '', date_to: '', policy: '', status: '', sort: 'BEST' });
  const [items, setItems] = useState<TourCard[]>([]);
  const [error, setError] = useState('');
  const searchNow = useCallback(() => findTours(filters).then((result) => setItems(result.items)).catch((reason) => setError(reason instanceof Error ? reason.message : 'Search failed')), [filters]);
  useEffect(() => { void searchNow(); }, []); // initial catalogue only; form submit controls later calls
  return <main className="max-w-6xl mx-auto p-4 sm:p-6 py-8"><h1 className="text-3xl font-bold mb-4">Find tours</h1><form className={`${panel} grid sm:grid-cols-3 lg:grid-cols-6 mb-5`} onSubmit={(event) => { event.preventDefault(); void searchNow(); }}><input className={field} type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} /><input className={field} type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} /><select className={field} value={filters.policy} onChange={(e) => setFilters({ ...filters, policy: e.target.value })}><option value="">Any group</option><option value="OPEN">Open</option><option value="WOMEN">Women only</option><option value="MEN">Men only</option><option value="STUDENTS">Students</option><option value="FAMILY">Family</option></select><select className={field} value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">Any status</option><option value="RECRUITING">Recruiting</option><option value="CONFIRMED">Confirmed</option></select><select className={field} value={filters.sort} onChange={(e) => setFilters({ ...filters, sort: e.target.value })}><option value="BEST">Best match</option><option value="SOONEST">Soonest</option><option value="SEATS">Most seats</option><option value="NEWEST">Newest</option></select><button className={`${primaryButtonClass} px-5`}><Search size={16} />Search</button></form>{error && <Notice tone="error">{error}</Notice>}<div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">{items.map((tour) => <TourCardView key={tour.public_id} tour={tour} />)}</div></main>;
}

export const CreateTourPage: React.FC = () => <AccessBoundary><TourCreator /></AccessBoundary>;
function TourCreator() {
  const navigate = useNavigate();
  const [destinations, setDestinations] = useState<DestinationSummary[]>([]);
  const [form, setForm] = useState({ title: '', destination: '', start_date: '', end_date: '', min_members: 2, max_members: 5, policy: 'OPEN', description: '', departure_city: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { void listAllDestinations().then(setDestinations); }, []);
  return <main className="max-w-2xl mx-auto p-4 sm:p-6 py-8"><h1 className="text-3xl font-bold mb-5">Create a tour</h1><form className={panel} onSubmit={(event) => { event.preventDefault(); setBusy(true); void createTour({ ...form, destinations: [form.destination], rules: ['NO_SMOKING', 'NO_ALCOHOL'] }).then((tour) => navigate(`/tours/${tour.public_id}`)).catch((reason) => setError(reason instanceof Error ? reason.message : 'Could not create tour')).finally(() => setBusy(false)); }}>
    {error && <Notice tone="error">{error}</Notice>}<label>Title<input className={`${field} mt-1`} minLength={8} maxLength={80} required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label><label>Destination<select className={`${field} mt-1`} required value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}><option value="">Choose</option>{destinations.map((item) => <option value={item.id} key={item.id}>{item.name_en}</option>)}</select></label><div className="grid sm:grid-cols-2 gap-3"><label>Start<input className={`${field} mt-1`} type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label><label>End<input className={`${field} mt-1`} type="date" required value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></label><label>Minimum members<input className={`${field} mt-1`} type="number" min={2} max={30} value={form.min_members} onChange={(e) => setForm({ ...form, min_members: Number(e.target.value) })} /></label><label>Maximum members<input className={`${field} mt-1`} type="number" min={2} max={30} value={form.max_members} onChange={(e) => setForm({ ...form, max_members: Number(e.target.value) })} /></label></div><select className={field} value={form.policy} onChange={(e) => setForm({ ...form, policy: e.target.value })}><option value="OPEN">Open</option><option value="WOMEN">Women only</option><option value="MEN">Men only</option><option value="STUDENTS">Students</option><option value="FAMILY">Family</option><option value="INVITE_ONLY">Invite only</option></select><input className={field} placeholder="Departure city" value={form.departure_city} onChange={(e) => setForm({ ...form, departure_city: e.target.value })} /><textarea className={field} rows={4} placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /><button disabled={busy} className={`${primaryButtonClass} px-6 self-start`}>Save draft</button></form></main>;
}

export const TourCodePage: React.FC = () => {
  const { code = '' } = useParams(); const navigate = useNavigate(); const [error, setError] = useState('');
  useEffect(() => { void getTourByCode(code).then((tour) => navigate(`/tours/${tour.public_id}?code=${encodeURIComponent(code)}`, { replace: true })).catch((reason) => setError(reason instanceof Error ? reason.message : 'Invalid tour code')); }, [code, navigate]);
  return <AccessBoundary>{error ? <main className="max-w-xl mx-auto p-8"><Notice tone="error">{error}</Notice></main> : <LoadingState />}</AccessBoundary>;
};

export const TourDetailPage: React.FC = () => <AccessBoundary><TourDetail /></AccessBoundary>;
function TourDetail() {
  const { publicId = '', tab: routeTab = 'overview' } = useParams(); const [params] = useSearchParams(); const [tour, setTour] = useState<TourWorkspace | null>(null); const [tab, setTab] = useState(routeTab); const [error, setError] = useState('');
  const load = useCallback(async () => { try { const summary = params.get('code') ? await getTourByCode(params.get('code')!) : await getTourSummary(publicId); setTour(summary.is_member ? await getTourWorkspace(publicId) : summary); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Tour could not be opened'); } }, [publicId, params]);
  useEffect(() => { void load(); }, [load]);
  if (!tour && !error) return <LoadingState />;
  if (!tour) return <main className="max-w-xl mx-auto p-8"><Notice tone="error">{error}</Notice></main>;
  const tabs = ['overview', 'tourmates', ...(tour.modules?.itinerary ? ['itinerary'] : []), ...(tour.modules?.discussion ? ['discussion'] : []), ...(tour.modules?.budget ? ['budget'] : []), ...(tour.modules?.safety ? ['safety'] : [])];
  return <main className="max-w-5xl mx-auto p-4 sm:p-6 py-8 flex flex-col gap-5"><div><p className="text-xs font-bold text-forest-primary">{tour.public_id} · {tour.lifecycle}</p><h1 className="text-3xl font-bold">{tour.title}</h1><p>{tour.start_date} → {tour.end_date} · {tour.policy} · {tour.members.approved}/{tour.members.maximum}</p></div>{error && <Notice tone="error">{error}</Notice>}<nav className="flex gap-2 overflow-x-auto">{tabs.map((name) => <button key={name} onClick={() => setTab(name)} className={`rounded-full px-4 py-2 text-sm font-bold ${tab === name ? 'bg-forest-primary text-white' : 'bg-surface-container'}`}>{name}</button>)}</nav>
    {tab === 'overview' && <OverviewTab tour={tour} reload={load} setError={setError} />}{tab === 'tourmates' && <TourmatesTab tour={tour} reload={load} />}{tab === 'itinerary' && <ItineraryTab tour={tour} />}{tab === 'discussion' && <ChatTab tour={tour} />}{tab === 'budget' && <BudgetTab tour={tour} />}{tab === 'safety' && <SafetyTab tour={tour} />}
  </main>;
}

function OverviewTab({ tour, reload, setError }: { tour: TourWorkspace; reload: () => Promise<void>; setError: (value: string) => void }) {
  const [message, setMessage] = useState(''); const organiser = ['CREATOR', 'CO_ORGANIZER'].includes(tour.your_role || '');
  return <section className={panel}><p>{tour.description || 'No description yet.'}</p><p><MapPin size={16} className="inline" /> {tour.destinations.map((item) => item.name_en).join(' · ')}</p>{tour.match?.score != null && <p><BadgeCheck size={16} className="inline" /> Match {tour.match.score}% using {tour.match.factors_used} factors</p>}{tour.request_blocker && <Notice tone="info">Request unavailable: {tour.request_blocker}</Notice>}
    {!tour.is_member && tour.can_request && <><textarea className={field} placeholder="Message to the organisers" value={message} onChange={(e) => setMessage(e.target.value)} /><button className={`${primaryButtonClass} px-5 self-start`} onClick={() => void requestToJoin(tour.public_id, { message, answer: '', accept_rules: true }).then(reload).catch((reason) => setError(reason instanceof Error ? reason.message : 'Request failed'))}>Request to join</button></>}
    {tour.your_request && <Notice tone="info">Your request is {tour.your_request.state}.</Notice>}
    {organiser && tour.lifecycle === 'DRAFT' && <button className={`${primaryButtonClass} px-5 self-start`} onClick={() => void publishTour(tour.public_id).then(reload)}>Publish tour</button>}
    {organiser && tour.code && <div className="rounded-xl bg-surface-container p-3"><strong>Private code: {tour.code}</strong><p className="text-xs">{tour.private_link}</p><button className="text-sm font-bold text-forest-primary" onClick={() => void regenerateTourCode(tour.public_id).then(reload)}>Regenerate code</button></div>}
    {tour.is_member && <div className="flex gap-4"><button className="text-error-alert" onClick={() => void leaveTour(tour.public_id, tour.lifecycle === 'ONGOING').then(() => location.assign('/tours'))}>Leave tour</button><button onClick={() => { const details = prompt('What should staff review?'); if (details) void reportTour(tour.public_id, details); }}>Report</button></div>}
    {tour.your_role === 'CREATOR' && <button className="text-error-alert self-start" onClick={() => { const reason = prompt('Cancellation reason'); if (reason) void cancelTour(tour.public_id, reason).then(reload); }}>Cancel tour</button>}
  </section>;
}

function TourmatesTab({ tour, reload }: { tour: TourWorkspace; reload: () => Promise<void> }) {
  return <section className="flex flex-col gap-4"><div className="grid sm:grid-cols-2 gap-3">{tour.members_list.map((member) => <article className={panel} key={member.member_id || member.name}><strong>{member.name} {member.is_you ? '(you)' : ''}</strong><p>{member.role} · {member.seats} seat(s)</p>{!member.is_you && member.member_id && tour.permissions.includes('tour.appoint') && <div className="flex gap-3"><button onClick={() => void setMemberRole(tour.public_id, member.member_id!, member.role === 'TOURMATE' ? 'CO_ORGANIZER' : 'TOURMATE').then(reload)}>Change role</button><button className="text-error-alert" onClick={() => void removeTourMember(tour.public_id, member.member_id!).then(reload)}>Remove</button></div>}</article>)}</div>{tour.pending_requests?.map((request) => <article className={panel} key={request.id}><strong>{request.first_name}</strong><p>{request.message || request.answer}</p><div className="flex gap-3"><button disabled={!request.can_be_approved} className={`${primaryButtonClass} px-4`} onClick={() => void approveJoinRequest(tour.public_id, request.id).then(reload)}>Approve</button><button onClick={() => void declineJoinRequest(tour.public_id, request.id).then(reload)}>Decline</button></div></article>)}</section>;
}

function ItineraryTab({ tour }: { tour: TourWorkspace }) {
  const [data, setData] = useState<ItineraryView | null>(null); useEffect(() => { void getItinerary(tour.public_id).then(setData); }, [tour.public_id]);
  return <section className={panel}><h2 className="text-xl font-bold">Itinerary</h2>{data?.items.map((item) => <div key={item.id}><strong>Day {item.day}: {item.title}</strong><p>{item.starts_at} {item.notes}</p></div>)}{!data?.items.length && <p>No itinerary items yet.</p>}</section>;
}

function ChatTab({ tour }: { tour: TourWorkspace }) {
  const [data, setData] = useState<ChatView | null>(null); const [body, setBody] = useState(''); const [error, setError] = useState(''); const [queued, setQueued] = useState(0);
  const load = useCallback(async () => {
    try {
      if (navigator.onLine) await flushChatOutbox(tour.public_id);
      const result = await getMessages(tour.public_id);
      setData(result); await cacheChat(tour.public_id, result.items);
      if (result.last_seq) void markMessagesRead(tour.public_id, result.last_seq);
      setError('');
    } catch (reason) {
      const saved = await cachedChat(tour.public_id);
      setData((current) => ({ items: saved, last_seq: saved[saved.length - 1]?.seq || 0, writable: true, muted: current?.muted || false, last_read_seq: current?.last_read_seq || 0 }));
      setError('Offline: showing saved messages. New messages will send when the connection returns.');
    }
    setQueued((await pendingChat(tour.public_id)).length);
  }, [tour.public_id]);
  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 5000); const online = () => void load(); window.addEventListener('online', online); return () => { clearInterval(timer); window.removeEventListener('online', online); }; }, [load]);
  const send = async (text: string) => {
    const row = await queueChat(tour.public_id, text);
    if (navigator.onLine) {
      try { await flushChatOutbox(tour.public_id); } catch { /* remains queued */ }
    }
    setQueued((await pendingChat(tour.public_id)).length);
    if (navigator.onLine) await load();
    else setError(`Offline: “${row.body.slice(0, 30)}” is queued.`);
  };
  return <section className={panel}><h2 className="text-xl font-bold flex gap-2"><MessageCircle />Discussion</h2>{queued > 0 && <Notice tone="info">{queued} message(s) waiting to send.</Notice>}{error && <Notice tone="info">{error}</Notice>}<div className="max-h-96 overflow-y-auto flex flex-col gap-2">{data?.items.map((message) => <div key={message.seq} className={`rounded-xl p-3 ${message.is_you ? 'bg-forest-primary/10 ml-8' : 'bg-surface-container mr-8'}`}><strong>{message.sender || message.kind}</strong><p>{message.body || `[${message.status}]`}</p><small>{new Date(message.created_at).toLocaleString()} · seen by {message.seen_by}</small></div>)}</div><form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); if (!body.trim()) return; const text = body; setBody(''); void send(text); }}><input className={field} value={body} onChange={(e) => setBody(e.target.value)} placeholder={data?.writable ? 'Message the tour' : 'Discussion is read only'} disabled={!data?.writable} /><button className={`${primaryButtonClass} px-5`} disabled={!data?.writable}>Send</button></form></section>;
}

function BudgetTab({ tour }: { tour: TourWorkspace }) {
  const [data, setData] = useState<BudgetView | null>(null); const [description, setDescription] = useState(''); const [amount, setAmount] = useState('');
  const load = useCallback(() => getBudget(tour.public_id).then(setData), [tour.public_id]); useEffect(() => { void load(); }, [load]);
  return <section className={panel}><h2 className="text-xl font-bold">Budget</h2>{data && <Notice tone="info">{data.notice.en}</Notice>}<p className="text-2xl font-bold">Total ৳{((data?.total_paisa || 0) / 100).toFixed(2)}</p>{data?.expenses.map((item) => <div key={item.id}><strong>{item.description}: ৳{(item.amount_paisa / 100).toFixed(2)}</strong><p>Paid by {item.paid_by_name}</p></div>)}<form className="grid sm:grid-cols-3 gap-2" onSubmit={(event) => { event.preventDefault(); void addExpense(tour.public_id, { description, amount_bdt: Number(amount), category: 'OTHER' }).then((result) => { setData(result); setDescription(''); setAmount(''); }); }}><input className={field} required placeholder="Expense" value={description} onChange={(e) => setDescription(e.target.value)} /><input className={field} required type="number" min="0.01" step="0.01" placeholder="BDT" value={amount} onChange={(e) => setAmount(e.target.value)} /><button className={`${primaryButtonClass} px-4`}>Add</button></form>{data?.transfers.map((transfer) => <div className="flex justify-between gap-3" key={`${transfer.from}-${transfer.to}`}><span>{transfer.from_name} owes {transfer.to_name} ৳{(transfer.amount_paisa / 100).toFixed(2)}</span>{transfer.is_from_you && <button onClick={() => void settleExpense(tour.public_id, transfer.to, transfer.amount_paisa).then(setData)}>Mark settled</button>}</div>)}</section>;
}

function SafetyTab({ tour }: { tour: TourWorkspace }) {
  const [data, setData] = useState<SafetyView | null>(null); const [contact, setContact] = useState({ name: '', relationship: '', phone: '' }); const [notes, setNotes] = useState('');
  const load = useCallback(() => getSafety(tour.public_id).then(setData), [tour.public_id]); useEffect(() => { void load(); }, [load]);
  return <section className={panel}><h2 className="text-xl font-bold">Safety</h2><Notice tone="info">Call Bangladesh emergency service at <a href="tel:999" className="font-bold">999</a>. Abhijatri is not an emergency service.</Notice><div className="grid sm:grid-cols-3 gap-2"><input className={field} placeholder="Emergency contact" value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} /><input className={field} placeholder="Relationship" value={contact.relationship} onChange={(e) => setContact({ ...contact, relationship: e.target.value })} /><input className={field} placeholder="Phone" value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} /></div><textarea className={field} placeholder="Medical notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} /><button className={`${primaryButtonClass} px-4 self-start`} onClick={() => void saveSafety(tour.public_id, { contact, medical_notes: notes }).then(setData)}>Save my private safety details</button>{data?.checkins.map((item) => <div key={item.id} className="rounded-xl bg-surface-container p-3"><strong>{item.message}</strong><p>{item.answered}/{item.total} checked in</p>{!item.you_answered && <button onClick={() => void answerCheckin(tour.public_id, item.id).then(setData)}>I am safe</button>}</div>)}{data?.can_manage && <button onClick={() => void requestCheckin(tour.public_id, 'Everyone OK?').then(setData)}>Request check-in</button>}<button className="rounded-xl bg-error-alert text-white p-4 text-lg font-bold" onClick={() => { if (confirm('Raise SOS for this tour? Also call 999 for immediate danger.')) void raiseSos(tour.public_id, 'Member raised SOS').then(setData); }}>SOS — alert tour and safety staff</button></section>;
}

export const TourPreferencesPage: React.FC = () => <AccessBoundary><Preferences /></AccessBoundary>;
function Preferences() {
  const [form, setForm] = useState({ budget_min_bdt: '', budget_max_bdt: '', style: '', pace: '', languages: ['BN'], flexible_dates: true, discoverable: false, audience: 'ALL' }); const [notice, setNotice] = useState('');
  useEffect(() => { void getTravelPreferences().then((data) => setForm((old) => ({ ...old, ...data, budget_min_bdt: String(data.budget_min_bdt || ''), budget_max_bdt: String(data.budget_max_bdt || '') }) as typeof old)); }, []);
  return <main className="max-w-2xl mx-auto p-6 py-8"><h1 className="text-3xl font-bold mb-4">Travel preferences</h1><form className={panel} onSubmit={(event) => { event.preventDefault(); const body = { ...form, budget_min_bdt: form.budget_min_bdt ? Number(form.budget_min_bdt) : null, budget_max_bdt: form.budget_max_bdt ? Number(form.budget_max_bdt) : null }; void saveTravelPreferences(body).then(() => saveDiscovery(form.discoverable, form.audience)).then(() => setNotice('Preferences saved.')); }}><div className="grid sm:grid-cols-2 gap-3"><input className={field} type="number" placeholder="Minimum daily BDT" value={form.budget_min_bdt} onChange={(e) => setForm({ ...form, budget_min_bdt: e.target.value })} /><input className={field} type="number" placeholder="Maximum daily BDT" value={form.budget_max_bdt} onChange={(e) => setForm({ ...form, budget_max_bdt: e.target.value })} /><select className={field} value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })}><option value="">Any comfort</option><option value="BUDGET">Budget</option><option value="BALANCED">Balanced</option><option value="COMFORT">Comfort</option></select><select className={field} value={form.pace} onChange={(e) => setForm({ ...form, pace: e.target.value })}><option value="">Any pace</option><option value="RELAXED">Relaxed</option><option value="BALANCED">Balanced</option><option value="FAST">Fast</option></select></div><label className="flex gap-2"><input type="checkbox" checked={form.discoverable} onChange={(e) => setForm({ ...form, discoverable: e.target.checked })} />Let verified members find my coarse profile</label><select className={field} value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })}><option value="ALL">All eligible members</option><option value="WOMEN">Women only</option><option value="MEN">Men only</option></select>{notice && <Notice tone="success">{notice}</Notice>}<button className={`${primaryButtonClass} px-5 self-start`}>Save preferences</button></form></main>;
}

export const FindPeoplePage: React.FC = () => {
  const [items, setItems] = useState<Awaited<ReturnType<typeof findPeople>>['items']>([]); const [tourId, setTourId] = useState('');
  const run = () => findPeople({ tour_id: tourId }).then((result) => setItems(result.items));
  useEffect(() => { void run(); }, []);
  return <AccessBoundary><main className="max-w-5xl mx-auto p-6 py-8"><h1 className="text-3xl font-bold">Find people</h1><p className="mb-4">Only verified members who opted in appear here. Exact age, dates and contact details are never shown.</p><div className="flex gap-2 mb-5"><input className={field} placeholder="Your tour public ID (optional)" value={tourId} onChange={(e) => setTourId(e.target.value)} /><button className={`${primaryButtonClass} px-5`} onClick={() => void run()}>Search</button></div><div className="grid md:grid-cols-2 gap-4">{items.map((person) => <article className={panel} key={person.user_id}><strong>{person.first_name} ✓ · {person.age_band}</strong><p>{person.division} · {person.style || 'Any style'} · {person.pace || 'Any pace'}</p><p>{person.destinations.join(' · ')}</p>{tourId && <button className={`${primaryButtonClass} px-4 self-start`} onClick={() => void invitePerson(tourId, person.user_id)}>Invite</button>}</article>)}</div></main></AccessBoundary>;
};

export const TourRequestsPage: React.FC = () => <ToursPage />;
export const TourInvitationsPage: React.FC = () => <ToursPage />;
