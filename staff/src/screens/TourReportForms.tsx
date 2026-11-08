import { useState } from 'react';
import { resolveTourReport, type TourReportAction } from '../api';
import type { Lang, QueueItem, TourReportSubject } from '../types';
import { makeT } from '../ui';

type Run = (work: () => Promise<string | void>) => Promise<void>;
interface Lease { token: string; expiresAt: string }

const KIND_LABEL: Record<TourReportSubject['task_type'], [string, string]> = {
  tour_report: ['ট্যুর রিপোর্ট', 'Tour report'],
  chat_report: ['চ্যাট রিপোর্ট', 'Chat report'],
  tour_safety: ['ট্যুর SOS', 'Tour SOS'],
};

export function tourReportTitle(subject: TourReportSubject, t: (bn: string, en: string) => string): string {
  const [bn, en] = KIND_LABEL[subject.task_type];
  return `${t(bn, en)}: ${subject.tour?.title ?? subject.report_id.slice(0, 8)}`;
}

/** What was reported, by whom, and (for chat) the message with the conversation around it as it was when reported. */
export function TourReportBody({ subject, lang }: { subject: TourReportSubject; lang: Lang }) {
  const t = makeT(lang);
  return (
    <div className="content-box stack">
      <div className="row small muted">
        <span className="tag">{subject.state}</span>
        <span className={subject.task_type === 'tour_safety' ? 'tag warn' : 'tag'}>{subject.reason_code}</span>
        <span>{subject.subject_kind}</span>
        <span>{new Date(subject.created_at).toLocaleString()}</span>
      </div>
      {subject.tour && (
        <p className="content-text">
          <strong>{subject.tour.title}</strong> · {subject.tour.public_id} · {subject.tour.lifecycle}
          {subject.tour.suspended && ` · ${t('স্থগিত', 'suspended')}`} · {subject.tour.start_date} → {subject.tour.end_date}
        </p>
      )}
      <p className="small">
        {t('রিপোর্টকারী', 'Reported by')}: {subject.reporter ?? t('অজানা', 'unknown')}
        {subject.reported_user && <> · {t('যার বিষয়ে', 'About')}: <strong>{subject.reported_user.display_name}</strong></>}
      </p>
      {subject.details && <p className="content-text">&ldquo;{subject.details}&rdquo;</p>}
      {subject.context.length > 0 && (
        <div className="stack">
          <p className="small muted">{t('রিপোর্টের সময়ের কথোপকথন', 'Conversation as it was when reported')}</p>
          <ol className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {subject.context.map((line) => (
              <li key={line.seq} style={line.reported ? { borderLeft: '3px solid #e5a50a', paddingLeft: 8 } : { paddingLeft: 11 }}>
                <span className="muted small">#{line.seq} · {line.sender ?? 'system'} · {new Date(line.at).toLocaleTimeString()}</span>
                <div>{line.reported ? <mark>{line.body}</mark> : line.body}</div>
              </li>
            ))}
          </ol>
        </div>
      )}
      {subject.message?.hidden && <p className="small warn-text">{t('বার্তাটি ইতিমধ্যে লুকানো।', 'This message is already hidden.')}</p>}
    </div>
  );
}

export function TourReportForm({ lang, item, subject, lease, busy, run }: { lang: Lang; item: QueueItem; subject: TourReportSubject; lease: Lease; busy: boolean; run: Run }) {
  const t = makeT(lang);
  const [note, setNote] = useState('');
  const [days, setDays] = useState(7);
  if (subject.state === 'actioned' || subject.state === 'dismissed') return null;
  const go = (action: TourReportAction, reason: string) =>
    run(async () => {
      const result = await resolveTourReport(subject.report_id, { action, reason_code: reason, note: note.trim(), days, task_id: item.id, lease_token: lease.token });
      return t(`রিপোর্ট: ${result.state}`, `Report ${result.state} (${result.action})`);
    });
  const message = subject.message && !subject.message.hidden;
  const sos = subject.task_type === 'tour_safety';
  return (
    <fieldset className="stack decision">
      <legend>{t('রিপোর্টের সিদ্ধান্ত', 'Report decision')}</legend>
      <label htmlFor="tour-report-note">{t('নোট (অডিট লগে থাকবে)', 'Note (kept in the audit log)')}</label>
      <textarea id="tour-report-note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="row">
        <button type="button" className="ghost" disabled={busy} onClick={() => void go(sos ? 'noted' : 'dismiss', 'no_violation')}>
          {sos ? t('দেখা হয়েছে, বন্ধ করুন', 'Handled, close') : t('খারিজ (লঙ্ঘন নেই)', 'Dismiss (no violation)')}
        </button>
        {message && (
          <button type="button" className="primary" disabled={busy} onClick={() => void go('hide_message', subject.reason_code)}>
            {t('বার্তা লুকান', 'Hide the message')}
          </button>
        )}
      </div>
      {subject.reported_user && (
        <div className="row">
          <label htmlFor="tour-report-days" className="small">{t('দিন', 'Days')}</label>
          <input id="tour-report-days" type="number" min={1} max={30} value={days} onChange={(e) => setDays(Math.max(1, Math.min(30, Number(e.target.value) || 7)))} style={{ width: '4.5rem' }} />
          <button type="button" className="ghost" disabled={busy} onClick={() => void go('restrict_user', subject.reason_code)}>
            {t(`${subject.reported_user.display_name}-কে ট্যুর থেকে সীমিত করুন`, `Restrict ${subject.reported_user.display_name} from Tours`)}
          </button>
        </div>
      )}
      {subject.tour && !subject.tour.suspended && (
        <div className="row">
          <button type="button" className="ghost" disabled={busy || note.trim().length < 3} onClick={() => void go('suspend_tour', subject.reason_code)}>
            {t('ট্যুর স্থগিত করুন (নোট লাগবে)', 'Suspend the tour (note required)')}
          </button>
        </div>
      )}
    </fieldset>
  );
}
