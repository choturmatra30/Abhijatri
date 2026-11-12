import { useEffect, useState } from 'react';
import { API_BASE, decideAppeal, enforcementAction, evidenceUrl, getVerificationDetails, transitionVerification } from '../api';
import { enforcementActions, verificationMoves, type VerificationMove } from '../logic';
import type { AppealSubject, EnforcementSubject, Lang, QueueItem, Role, VerificationDetails, VerificationSubject } from '../types';
import { Notice, makeT } from '../ui';

type Run = (work: () => Promise<string | void>) => Promise<void>;
interface Lease {
  token: string;
  expiresAt: string;
}

const MOVE_TEXT: Record<VerificationMove, [string, string]> = {
  in_review: ['পর্যালোচনা শুরু', 'Start review'],
  needs_clarification: ['প্রশ্ন করুন', 'Ask a question'],
  approved: ['অনুমোদন', 'Approve'],
  rejected: ['প্রত্যাখ্যান', 'Reject'],
  escalated: ['উপরে পাঠান', 'Escalate'],
};

// ---------------- verification ----------------

export function VerificationBody({ subject, lang, canView, run }: { subject: VerificationSubject; lang: Lang; canView: boolean; run: Run }) {
  const t = makeT(lang);
  const [details, setDetails] = useState<VerificationDetails | null>(null);
  useEffect(() => {
    if (canView) void getVerificationDetails(subject.case_id).then(setDetails).catch(() => setDetails(null));
  }, [canView, subject.case_id]);
  const [preview, setPreview] = useState<{ id: string; kind: string; src: string } | null>(null);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.src); }, [preview]);
  // The image is fetched with the staff session and shown in the panel from memory: no new tab, no file to
  // save (sign-up form 6.1). The server watermarks it with the reviewer's id and audits every view.
  const open = (evidenceId: string, kind: string) =>
    run(async () => {
      const link = await evidenceUrl(subject.case_id, evidenceId);
      const url = new URL(link.url, `${API_BASE}/`).toString();
      const response = await fetch(url, { credentials: 'include', cache: 'no-store' });
      if (!response.ok) throw new Error(`evidence ${response.status}`);
      const blob = await response.blob();
      if (!blob.type.startsWith('image/')) {
        window.open(url, '_blank', 'noopener,noreferrer'); // an old unsealed file (PDF): the 60-second link
        return t('৬০ সেকেন্ডের জন্য গোপন লিংক খোলা হয়েছে (অডিট লগে লেখা হলো)।', 'A private link opened for 60 seconds (recorded in the audit log).');
      }
      setPreview({ id: evidenceId, kind, src: URL.createObjectURL(blob) });
      return t('ছবিটি দেখানো হচ্ছে (অডিট লগে লেখা হলো)।', 'Showing the image (recorded in the audit log).');
    });
  return (
    <div className="content-box">
      <div className="row small muted">
        <span className="tag">{subject.state}</span>
        <span className="tag">{subject.purpose}</span>
        <span>
          {subject.applicant?.display_name} · {subject.applicant?.email}
        </span>
      </div>
      {subject.risk_flags.length > 0 && <Notice tone="error">{t('ঝুঁকি ফ্ল্যাগ', 'Risk flags')}: {subject.risk_flags.join(', ')}</Notice>}
      {subject.legacy && <Notice tone="info">{t('পুরনো ফর্ম: অনুমোদন করা যাবে না; নতুন ফর্ম ব্যবহার করতে বলুন।', 'Legacy form: cannot be approved; ask the applicant to use the new form.')}</Notice>}
      {subject.statement && <p className="content-text">{subject.statement}</p>}
      {details && <div className="grid two">
        <div><strong>{t('আইনি নাম', 'Legal name')}</strong><p>{details.personal.legal_name_en}{details.personal.legal_name_bn ? ` · ${details.personal.legal_name_bn}` : ''}</p></div>
        <div><strong>{t('জন্ম ও লিঙ্গ', 'Birth & gender')}</strong><p>{details.personal.date_of_birth} · {details.personal.gender}</p></div>
        <div><strong>{t('ঠিকানা ও পেশা', 'Home & occupation')}</strong><p>{details.personal.home_district}, {details.personal.home_division} · {details.personal.occupation}</p></div>
        <div><strong>{t('ফোন', 'Phone')}</strong><p>•••• {details.phone?.last4} · {details.phone?.verified ? 'verified' : 'not verified'}</p></div>
        <div><strong>{t('নথি', 'Document')}</strong><p>{details.document?.doc_type} · {details.document?.number || `•••• ${details.document?.last4}`} · {details.document?.expiry || 'no expiry'}</p></div>
        {details.student && <div><strong>{t('শিক্ষার্থী', 'Student')}</strong><p>{details.student.institution} · until {details.student.study_end} · email {details.student.email_verified ? 'verified' : 'not verified'}</p></div>}
        <div><strong>{t('লাইভনেস', 'Liveness')}</strong><p>{details.liveness?.code} · {details.liveness?.gesture_en}</p></div>
        <div><strong>{t('আগের প্রত্যাখ্যান', 'Previous rejections')}</strong><p>{details.previous_rejections}</p></div>
      </div>}
      <div className="row small">
        <strong>{t('প্রমাণ', 'Evidence')}:</strong>
        {subject.evidence.length === 0 && <span className="muted">{t('এখনো কোনো ফাইল নেই', 'no file yet')}</span>}
        {subject.evidence.map((item, index) => (
          <button key={item.id} type="button" className={preview?.id === item.id ? '' : 'ghost'} disabled={!canView} onClick={() => void open(item.id, item.kind || 'FILE')}>
            {item.kind || t('ফাইল', 'File')} {index + 1} ({item.content_type.split('/')[1]}) {item.flags.length ? `⚠ ${item.flags.join(', ')}` : ''}
          </button>
        ))}
      </div>
      {preview && (
        <figure className="evidence-preview" onContextMenu={(event) => event.preventDefault()}>
          <img src={preview.src} alt={`${preview.kind} evidence`} draggable={false} style={{ maxWidth: '100%', maxHeight: 520, borderRadius: 12, display: 'block' }} />
          <figcaption className="muted small">
            {preview.kind} · {t('ওয়াটারমার্কযুক্ত; দেখা অডিট লগে লেখা হয়।', 'Watermarked; every view is in the audit log.')}{' '}
            <button type="button" className="ghost" onClick={() => setPreview(null)}>{t('বন্ধ', 'Close')}</button>
          </figcaption>
        </figure>
      )}
      {!canView && subject.evidence.length > 0 && <p className="muted small">{t('ফাইল দেখতে আগে কাজটি নিন।', 'Claim the task to view the files.')}</p>}
    </div>
  );
}

export function VerificationForm({ lang, role, item, subject, lease, busy, run }: { lang: Lang; role: Role; item: QueueItem; subject: VerificationSubject; lease: Lease; busy: boolean; run: Run }) {
  const t = makeT(lang);
  const [note, setNote] = useState('');
  const [details, setDetails] = useState<VerificationDetails | null>(null);
  const [detailsError, setDetailsError] = useState(false);
  const [detailsAttempt, setDetailsAttempt] = useState(0);
  const [checks, setChecks] = useState<string[]>([]);
  const [clarificationSteps, setClarificationSteps] = useState<string[]>([]);
  const [rejectReason, setRejectReason] = useState('details-mismatch');
  const [clarifyReason, setClarifyReason] = useState('details-check');
  const [gender, setGender] = useState('');
  const [birthYear, setBirthYear] = useState('');
  const [student, setStudent] = useState(false);
  const [studentUntil, setStudentUntil] = useState('');
  useEffect(() => {
    setDetailsError(false);
    void getVerificationDetails(subject.case_id).then((value) => {
      setDetails(value);
      setGender(value.personal.gender || '');
      setBirthYear(value.personal.date_of_birth?.slice(0, 4) || '');
      setStudent(Boolean(value.student));
      setStudentUntil(value.student?.max_student_until || '');
    }).catch(() => { setDetails(null); setDetailsError(true); }); // shown with a Retry, never silently
  }, [subject.case_id, detailsAttempt]);
  const moves = verificationMoves(subject.state, role);
  if (moves.length === 0) return <Notice tone="info">{t('এই অবস্থায় আপনার জন্য কোনো পদক্ষেপ নেই।', 'No action for your role in this state.')}</Notice>;
  const missingChecks = details ? details.required_checks.length - checks.length : 0;
  const approveBlocker = !details
    ? detailsError
      ? t('যাচাইয়ের তথ্য লোড হয়নি, তাই অনুমোদন বন্ধ। নিচে "আবার চেষ্টা করুন" চাপুন।', 'The case details did not load, so Approve is off. Press Retry below.')
      : t('যাচাইয়ের তথ্য লোড হচ্ছে…', 'Loading the case details…')
    : missingChecks > 0
      ? t(`অনুমোদনের আগে চেকলিস্টের আরও ${missingChecks}টি ঘর টিক দিন।`, `Tick ${missingChecks} more checklist item${missingChecks === 1 ? '' : 's'} to approve.`)
      : !gender || !birthYear
        ? t('অনুমোদনের আগে লিঙ্গ ও জন্মসাল দিন।', 'Set gender and birth year to approve.')
        : '';
  const go = (to: VerificationMove) =>
    run(async () => {
      const result = await transitionVerification(subject.case_id, {
        to,
        expectedVersion: subject.version,
        reasonCode: to === 'approved' ? 'documents-ok' : to === 'rejected' ? rejectReason : to === 'needs_clarification' ? clarifyReason : to,
        note,
        taskId: item.id,
        leaseToken: lease.token,
        checklist: to === 'approved' ? checks : undefined,
        attributes: to === 'approved' ? { gender, birth_year: Number(birthYear), is_student: student, student_until: student ? studentUntil : undefined } : undefined,
        steps: to === 'needs_clarification' ? clarificationSteps : undefined,
      });
      return t(`অবস্থা: ${result.state}`, `State: ${result.state}`);
    });
  return (
    <fieldset className="stack decision">
      <legend>{t('যাচাইয়ের সিদ্ধান্ত', 'Verification decision')}</legend>
      <label htmlFor="verify-note">{t('নোট (প্রশ্ন করলে আবশ্যক; আবেদনকারী দেখবেন)', 'Note (required for a question; the applicant sees it)')}</label>
      <textarea id="verify-note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
      <label>{t('প্রত্যাখ্যানের কারণ', 'Rejection reason')}<select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}><option value="document-not-genuine">Document not genuine</option><option value="details-mismatch">Details mismatch</option><option value="face-mismatch">Face mismatch</option><option value="under-18">Under 18</option><option value="duplicate-account">Duplicate account</option><option value="fake-document">Fake document</option><option value="use-new-form">Use new form</option><option value="other">Other</option></select></label>
      <label>{t('ব্যাখ্যা চাওয়ার কারণ', 'Clarification reason')}<select value={clarifyReason} onChange={(e) => setClarifyReason(e.target.value)}><option value="blurry-photo">Blurry photo</option><option value="glare">Glare</option><option value="missing-back">Missing back</option><option value="selfie-code-not-visible">Selfie code/gesture not visible</option><option value="details-check">Check details</option><option value="other">Other</option></select></label>
      <fieldset className="stack inset"><legend>{t('পুনরায় করার ধাপ', 'Steps to redo')}</legend>{['personal', 'phone', 'document', 'student', 'selfie'].map((step) => <label className="row" key={step}><input type="checkbox" checked={clarificationSteps.includes(step)} onChange={(e) => setClarificationSteps(e.target.checked ? [...clarificationSteps, step] : clarificationSteps.filter((value) => value !== step))} />{step}</label>)}</fieldset>
      {!details && detailsError && <div className="row" role="alert"><span className="error">{t('যাচাইয়ের তথ্য লোড করা যায়নি।', 'Could not load the case details.')}</span><button type="button" className="ghost" onClick={() => setDetailsAttempt((n) => n + 1)}>{t('আবার চেষ্টা করুন', 'Retry')}</button></div>}
      {details && <fieldset className="stack inset"><legend>{t('অনুমোদনের চেকলিস্ট ও বৈশিষ্ট্য', 'Approval checklist & attributes')}</legend>{details.required_checks.map((check) => <label className="row" key={check}><input type="checkbox" checked={checks.includes(check)} onChange={(e) => setChecks(e.target.checked ? [...checks, check] : checks.filter((value) => value !== check))} />{check}</label>)}<div className="row wrap"><label>Gender<select value={gender} onChange={(e) => setGender(e.target.value)}><option value="">Choose</option><option value="FEMALE">Female</option><option value="MALE">Male</option><option value="THIRD">Third gender</option></select></label><label>Birth year<input type="number" min="1900" max={new Date().getFullYear() - 18} value={birthYear} onChange={(e) => setBirthYear(e.target.value)} /></label><label className="row"><input type="checkbox" checked={student} onChange={(e) => setStudent(e.target.checked)} />Student</label>{student && <label>Student until<input type="date" value={studentUntil} onChange={(e) => setStudentUntil(e.target.value)} /></label>}</div></fieldset>}
      <div className="row">
        {moves.includes('approved') && approveBlocker && <p className="small muted approve-hint" role="note">{approveBlocker}</p>}
        {moves.map((to) => (
          <button key={to} type="button" className={to === 'approved' ? 'primary' : 'ghost'} disabled={busy || (to === 'needs_clarification' && (note.trim().length < 3 || clarificationSteps.length === 0)) || (to === 'approved' && (!details || checks.length !== details.required_checks.length || !gender || !birthYear))} onClick={() => void go(to)}>
            {t(...MOVE_TEXT[to])}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

// ---------------- appeals ----------------

export function AppealBody({ subject, lang }: { subject: AppealSubject; lang: Lang }) {
  const t = makeT(lang);
  return (
    <div className="content-box">
      <div className="row small muted">
        <span className="tag">{subject.state}</span>
        <span>
          {subject.target_type} {subject.target_id.slice(0, 8)}
        </span>
        <span>
          {t('শেষ সময়', 'Deadline')}: {new Date(subject.deadline_at).toLocaleDateString()}
        </span>
      </div>
      <p className="content-text">{subject.reason}</p>
      {subject.original_decider_is_you && (
        <Notice tone="info">{t('মূল সিদ্ধান্তটি আপনার, তাই এই আপিল অন্য কেউ দেখবেন।', 'You made the original decision, so someone else must decide this appeal.')}</Notice>
      )}
    </div>
  );
}

export function AppealForm({ lang, item, subject, lease, busy, run }: { lang: Lang; item: QueueItem; subject: AppealSubject; lease: Lease; busy: boolean; run: Run }) {
  const t = makeT(lang);
  const [note, setNote] = useState('');
  if (subject.state !== 'received' && subject.state !== 'in_review') return null;
  const decide = (outcome: 'upheld' | 'overturned') =>
    run(async () => {
      const result = await decideAppeal(subject.appeal_id, { outcome, expectedVersion: subject.version, note: note.trim(), taskId: item.id, leaseToken: lease.token });
      return t(`আপিল: ${result.state}`, `Appeal: ${result.state}`);
    });
  return (
    <fieldset className="stack decision">
      <legend>{t('আপিলের সিদ্ধান্ত', 'Appeal decision')}</legend>
      <label htmlFor="appeal-note">{t('কারণ (আবেদনকারী দেখবেন)', 'Reason (the appellant sees it)')}</label>
      <textarea id="appeal-note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="row">
        <button type="button" className="ghost" disabled={busy || note.trim().length < 3} onClick={() => void decide('upheld')}>
          {t('মূল সিদ্ধান্ত বহাল', 'Uphold')}
        </button>
        <button type="button" className="primary" disabled={busy || note.trim().length < 3} onClick={() => void decide('overturned')}>
          {t('মূল সিদ্ধান্ত বাতিল', 'Overturn')}
        </button>
      </div>
    </fieldset>
  );
}

// ---------------- enforcement ----------------

export function EnforcementBody({ subject, lang }: { subject: EnforcementSubject; lang: Lang }) {
  const t = makeT(lang);
  return (
    <div className="content-box">
      <div className="row small muted">
        <span className="tag">{subject.state}</span>
        {subject.emergency && <span className="tag warn">{t('জরুরি', 'Emergency')}</span>}
        <span>{subject.reason_code}</span>
        {subject.follow_up_due_at && (
          <span>
            {t('পর্যালোচনার শেষ সময়', 'Review by')}: {new Date(subject.follow_up_due_at).toLocaleString()}
          </span>
        )}
      </div>
      {subject.review && <p className="content-text">{subject.review.title}</p>}
      {subject.user && (
        <p className="content-text">
          {subject.user.display_name} · {subject.user.email}
        </p>
      )}
      {subject.note && <p className="small muted">{subject.note}</p>}
    </div>
  );
}

export function EnforcementFollowUp({ lang, subject, busy, run }: { lang: Lang; subject: EnforcementSubject; busy: boolean; run: Run }) {
  const t = makeT(lang);
  const actions = enforcementActions(subject.state);
  const act = (action: 'remove' | 'restore' | 'close') =>
    run(async () => {
      const result = await enforcementAction(subject.case_id, { action, expected_version: subject.version, reason_code: action === 'restore' ? 'follow-up-restore' : 'follow-up-confirmed', counts_toward_rating: action === 'remove' ? false : undefined });
      return t(`অবস্থা: ${result.state}`, `State: ${result.state}`);
    });
  return (
    <div className="row">
      {actions.map((action) => (
        <button key={action} type="button" className={action === 'restore' ? 'ghost' : 'primary'} disabled={busy} onClick={() => void act(action)}>
          {action === 'remove' ? t('অপসারণ নিশ্চিত', 'Confirm removal') : action === 'restore' ? t('ফিরিয়ে আনুন', 'Restore') : t('বন্ধ করুন', 'Close')}
        </button>
      ))}
    </div>
  );
}
